"""
Authorization and custom permission classes for DRF views.

Implements IsOwnerOrAdmin to enforce secure multi-tenant object-level access across all entities:
- Authenticated users can list, retrieve, and create resources.
- Only the resource owner (or ADMIN) can modify (PUT, PATCH) or delete (DELETE).
- Immutable resources like AuditLog prevent modification or deletion.
"""

from rest_framework import permissions


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

        # Task ownership check via project parent
        if hasattr(obj, 'project') and hasattr(obj.project, 'owner'):
            return obj.project.owner == request.user

        # Models without direct ownership (e.g. Tag) cannot be modified by non-admins
        return False
