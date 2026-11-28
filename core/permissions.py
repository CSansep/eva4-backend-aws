"""
Authorization and custom permission classes for DRF views.

Implements IsOwnerOrAdmin to enforce secure multi-tenant object-level access across all entities:
- Authenticated users can list, retrieve, and create resources.
- Only the resource owner (or ADMIN) can modify (PUT, PATCH) or delete (DELETE).
- Immutable resources like AuditLog prevent modification or deletion.
- Tool / ToolRequest / ToolReturn use dedicated strict ADMIN/MEMBER policies.
"""

from rest_framework import permissions


def is_admin_user(user) -> bool:
    """Single source of truth for administrative role resolution."""
    return bool(
        user
        and user.is_authenticated
        and (
            getattr(user, 'role', None) == 'ADMIN'
            or getattr(user, 'is_staff', False)
            or getattr(user, 'is_superuser', False)
        )
    )


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Object-level permission allowing:
    - Safe methods (GET, HEAD, OPTIONS) to any authenticated user.
    - POST methods to any authenticated user.
    - PUT, PATCH, DELETE only to:
      1. Users with role == 'ADMIN', is_staff, or is_superuser.
      2. The creator of the Workspace (workspace.created_by).
      3. The member or workspace creator in WorkspaceMember.
      4. The owner of the Project (project.owner).
      5. The owner of the Project associated with the Task (task.project.owner).
      6. The author of the TaskComment (comment.author) or parent project owner.
      7. The owner of the Project associated with the Subtask (subtask.task.project.owner).
    Rejects any unauthenticated access with 401 Unauthorized, and unauthorized
    modifications with 403 Forbidden.
    """

    def has_permission(self, request, view):
        """Verify that the requesting user is authenticated."""
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        """Enforce ownership or administrator privileges on object modification/deletion."""
        # Read-only safe methods are allowed for any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return True

        # System administrators and staff have full authorization
        is_admin_user = (
            getattr(request.user, 'role', None) == 'ADMIN'
            or bool(getattr(request.user, 'is_staff', False))
            or bool(getattr(request.user, 'is_superuser', False))
        )
        if is_admin_user:
            return True

        # AuditLog is strictly immutable: no updates or deletes permitted
        if obj.__class__.__name__ == 'AuditLog':
            return False

        # Workspace ownership
        if hasattr(obj, 'created_by'):
            return obj.created_by == request.user

        # WorkspaceMember: workspace creator or member themselves can manage membership
        if hasattr(obj, 'workspace') and hasattr(obj, 'user'):
            return obj.workspace.created_by == request.user or obj.user == request.user

        # Project ownership check
        if hasattr(obj, 'owner'):
            return obj.owner == request.user

        # TaskComment: comment author or project owner can modify/delete
        if hasattr(obj, 'author') and hasattr(obj, 'task'):
            return obj.author == request.user or obj.task.project.owner == request.user

        # Subtask: task project owner
        if hasattr(obj, 'task') and hasattr(obj.task, 'project'):
            return obj.task.project.owner == request.user

        # Task ownership or field execution check
        if hasattr(obj, 'project') and hasattr(obj.project, 'owner'):
            if obj.project.owner == request.user or getattr(obj, 'assigned_to', None) == request.user:
                return True
            # MEMBER en terreno: único PATCH permitido es avance de estado o evidencia S3.
            # Cualquier otro campo, PUT o DELETE termina en 403 Forbidden.
            if request.method == 'PATCH' and set(request.data.keys()).issubset({'status', 'attachment'}):
                return True
            return False

        # Models without direct ownership (e.g. Tag) cannot be modified by non-admins
        return False


class ToolPermission(permissions.BasePermission):
    """
    Tool catalog is readable by any authenticated user, but only ADMIN may
    create, update or delete tools.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return is_admin_user(request.user)

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class ToolRequestPermission(permissions.BasePermission):
    """
    MEMBER may list their own/field requests and create new ones, and may only
    cancel their own PENDIENTE requests. ADMIN has full control.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.method in ('POST', 'DELETE'):
            # Object-level check decides whether this DELETE belongs to the user.
            return True
        return is_admin_user(request.user)

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if is_admin_user(request.user):
            return True
        return (
            request.method == 'DELETE'
            and obj.requested_by_id == request.user.id
            and obj.status == 'PENDIENTE'
        )


class ToolReturnPermission(permissions.BasePermission):
    """
    Both roles can create and read return receipts. Only ADMIN may verify
    (PATCH to RECEPCIONADA) or delete them.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS or request.method == 'POST':
            return True
        return is_admin_user(request.user)

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return is_admin_user(request.user)
