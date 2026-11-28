"""
Views and ViewSets for EVA4 REST API.

Provides:
- User registration & Profile (Public & Authenticated)
- Workspace & WorkspaceMember CRUD
- Project CRUD (with automatic AuditLog tracking)
- Tag CRUD
- Task CRUD (with query filtering and automatic AuditLog tracking)
- TaskComment & Subtask CRUD
- Tool catalog, ToolRequest & ToolReturn CRUD with atomic stock movements
- AuditLog ReadOnly endpoint (scoped to ADMIN or own logs)
- Health check (Public, verifies DB connectivity for AWS / API Gateway)
"""

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from rest_framework import generics, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import get_client_ip, record_audit_log
from core.models import (
    AuditActionChoices,
    AuditLog,
    Project,
    Subtask,
    Tag,
    Task,
    TaskComment,
    Tool,
    ToolRequest,
    ToolRequestStatusChoices,
    ToolReturn,
    ToolReturnStatusChoices,
    Workspace,
    WorkspaceMember,
    WorkspaceMemberRoleChoices,
)
from core.permissions import (
    IsOwnerOrAdmin,
    ToolPermission,
    ToolRequestPermission,
    ToolReturnPermission,
    is_admin_user,
)
from core.serializers import (
    AuditLogSerializer,
    ProjectSerializer,
    SubtaskSerializer,
    TagSerializer,
    TaskCommentSerializer,
    TaskSerializer,
    ToolRequestSerializer,
    ToolReturnSerializer,
    ToolSerializer,
    UserRegistrationSerializer,
    UserResponseSerializer,
    WorkspaceMemberSerializer,
    WorkspaceSerializer,
)

User = get_user_model()


# ==============================================================================
# AUTHENTICATION & HEALTH
# ==============================================================================
class RegisterView(generics.CreateAPIView):
    """
    Public user registration endpoint.
    Accepts email, username, password, and optional role.
    Returns 201 Created with safe user profile data (never returns password).
    """
    permission_classes = [AllowAny]
    serializer_class = UserRegistrationSerializer

    @extend_schema(
        summary="Register a new user account",
        description="Public registration endpoint. Validates password strength and creates an active user.",
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                response=UserResponseSerializer,
                description="User successfully registered."
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(description="Validation errors (weak password, duplicate email)."),
        }
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        output_serializer = UserResponseSerializer(user)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class UserProfileView(generics.RetrieveAPIView):
    """
    Endpoint returning profile data for the currently authenticated user.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserResponseSerializer

    @extend_schema(
        summary="Get current user profile",
        description="Returns detailed profile information for the authenticated user making the request.",
        responses={
            status.HTTP_200_OK: UserResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: OpenApiResponse(description="Invalid or missing JWT token."),
        }
    )
    def get_object(self):
        return self.request.user


class HealthCheckView(APIView):
    """
    Lightweight health check endpoint for AWS Application Load Balancer,
    Amazon API Gateway, and monitoring systems.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Service Health Check",
        description="Validates database connectivity and service readiness for AWS load balancers.",
        responses={
            status.HTTP_200_OK: OpenApiResponse(description="Service and database operational."),
            status.HTTP_503_SERVICE_UNAVAILABLE: OpenApiResponse(description="Database unavailable."),
        }
    )
    def get(self, request, *args, **kwargs):
        database_status = "connected"
        http_code = status.HTTP_200_OK

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
                cursor.fetchone()
        except Exception as exc:
            database_status = f"disconnected: {str(exc)}"
            http_code = status.HTTP_503_SERVICE_UNAVAILABLE

        response_data = {
            "status": "ok" if http_code == status.HTTP_200_OK else "unhealthy",
            "database": "connected" if http_code == status.HTTP_200_OK else "disconnected",
            "timestamp": timezone.now().isoformat(),
            "service": "eva4-backend",
        }
        return Response(response_data, status=http_code)


# ==============================================================================
# WORKSPACE & MEMBERS VIEWSETS
# ==============================================================================
class WorkspaceViewSet(viewsets.ModelViewSet):
    """
    CRUD ViewSet for Workspace / Organization entities.
    Authenticated users can list and create workspaces.
    Only the workspace creator or an ADMIN can update or delete.
    """
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    serializer_class = WorkspaceSerializer
    queryset = Workspace.objects.select_related('created_by').prefetch_related('members', 'projects').all()

    def perform_create(self, serializer):
        """Save workspace and add creator as OWNER in WorkspaceMember."""
        workspace = serializer.save(created_by=self.request.user)
        WorkspaceMember.objects.create(
            workspace=workspace,
            user=self.request.user,
            role=WorkspaceMemberRoleChoices.OWNER
        )


class WorkspaceMemberViewSet(viewsets.ModelViewSet):
    """
    CRUD ViewSet for managing Workspace members.
    Supports ?workspace=<UUID> filtering.
    """
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    serializer_class = WorkspaceMemberSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='workspace',
                description='Filter members by Workspace UUID',
                required=False,
                type=str
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        queryset = WorkspaceMember.objects.select_related('workspace', 'user').all()
        workspace_param = self.request.query_params.get('workspace')
        if workspace_param:
            queryset = queryset.filter(workspace_id=workspace_param.strip())
        return queryset


# ==============================================================================
# PROJECT VIEWSET (WITH AUTOMATIC AUDITING)
# ==============================================================================
class ProjectViewSet(viewsets.ModelViewSet):
    """
    CRUD ViewSet for Project entities.
    Automatically generates AuditLog entries on create, update, and delete.
    """
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    serializer_class = ProjectSerializer
    queryset = Project.objects.select_related('owner', 'workspace').prefetch_related('tasks').all()

    def perform_create(self, serializer):
        """Automatically set the authenticated user as owner and log audit event."""
        project = serializer.save(owner=self.request.user)
        record_audit_log(
            user=self.request.user,
            action=AuditActionChoices.CREATE,
            entity_name='Project',
            entity_id=project.id,
            details={'name': project.name},
            ip_address=get_client_ip(self.request)
        )

    def perform_update(self, serializer):
        """Update project and log audit event."""
        project = serializer.save()
        record_audit_log(
            user=self.request.user,
            action=AuditActionChoices.UPDATE,
            entity_name='Project',
            entity_id=project.id,
            details={'name': project.name, 'is_active': project.is_active},
            ip_address=get_client_ip(self.request)
        )

    def perform_destroy(self, instance):
        """Record audit event before deleting project."""
        record_audit_log(
            user=self.request.user,
            action=AuditActionChoices.DELETE,
            entity_name='Project',
            entity_id=instance.id,
            details={'name': instance.name},
            ip_address=get_client_ip(self.request)
        )
        instance.delete()


# ==============================================================================
# TAG VIEWSET
# ==============================================================================
class TagViewSet(viewsets.ModelViewSet):
    """
    CRUD ViewSet for Tag classification entities.
    """
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    serializer_class = TagSerializer
    queryset = Tag.objects.all()


# ==============================================================================
# TASK VIEWSET (WITH AUTOMATIC AUDITING)
# ==============================================================================
class TaskViewSet(viewsets.ModelViewSet):
    """
    CRUD ViewSet for Task entities.
    Supports query parameter filtering:
    - ?status=PENDING|IN_PROGRESS|COMPLETED
    - ?priority=LOW|MEDIUM|HIGH
    - ?project=<UUID>
    Automatically logs AuditLog records on create, update, and delete.
    """
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    serializer_class = TaskSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='status',
                description='Filter tasks by status (PENDING, IN_PROGRESS, COMPLETED)',
                required=False,
                type=str
            ),
            OpenApiParameter(
                name='priority',
                description='Filter tasks by priority (LOW, MEDIUM, HIGH)',
                required=False,
                type=str
            ),
            OpenApiParameter(
                name='project',
                description='Filter tasks by Project UUID',
                required=False,
                type=str
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Task.objects.select_related(
            'project',
            'project__owner',
            'assigned_to'
        ).prefetch_related('tags', 'subtasks', 'comments').all()

        status_param = self.request.query_params.get('status')
        priority_param = self.request.query_params.get('priority')
        project_param = self.request.query_params.get('project')

        if status_param:
            queryset = queryset.filter(status__iexact=status_param.strip())
        if priority_param:
            queryset = queryset.filter(priority__iexact=priority_param.strip())
        if project_param:
            queryset = queryset.filter(project_id=project_param.strip())

        return queryset

    def perform_create(self, serializer):
        """Create task and log audit event."""
        task = serializer.save()
        record_audit_log(
            user=self.request.user,
            action=AuditActionChoices.CREATE,
            entity_name='Task',
            entity_id=task.id,
            details={'title': task.title, 'project_id': str(task.project.id)},
            ip_address=get_client_ip(self.request)
        )

    def perform_update(self, serializer):
        """Update task and log audit event."""
        task = serializer.save()
        record_audit_log(
            user=self.request.user,
            action=AuditActionChoices.UPDATE,
            entity_name='Task',
            entity_id=task.id,
            details={'title': task.title, 'status': task.status, 'priority': task.priority},
            ip_address=get_client_ip(self.request)
        )

    def perform_destroy(self, instance):
        """Record audit event before deleting task."""
        record_audit_log(
            user=self.request.user,
            action=AuditActionChoices.DELETE,
            entity_name='Task',
            entity_id=instance.id,
            details={'title': instance.title, 'project_id': str(instance.project.id)},
            ip_address=get_client_ip(self.request)
        )
        instance.delete()


# ==============================================================================
# TASK COMMENT & SUBTASK VIEWSETS
# ==============================================================================
class TaskCommentViewSet(viewsets.ModelViewSet):
    """
    CRUD ViewSet for Task Comments.
    Supports ?task=<UUID> filtering.
    """
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    serializer_class = TaskCommentSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='task',
                description='Filter comments by Task UUID',
                required=False,
                type=str
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        queryset = TaskComment.objects.select_related('task', 'author').all()
        task_param = self.request.query_params.get('task')
        if task_param:
            queryset = queryset.filter(task_id=task_param.strip())
        return queryset

    def perform_create(self, serializer):
        """Assign authenticated user as comment author."""
        serializer.save(author=self.request.user)


class SubtaskViewSet(viewsets.ModelViewSet):
    """
    CRUD ViewSet for Subtasks / Checklist items.
    Supports ?task=<UUID> filtering.
    """
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    serializer_class = SubtaskSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='task',
                description='Filter subtasks by parent Task UUID',
                required=False,
                type=str
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Subtask.objects.select_related('task', 'task__project').all()
        task_param = self.request.query_params.get('task')
        if task_param:
            queryset = queryset.filter(task_id=task_param.strip())
        return queryset


# ==============================================================================
# AUDIT LOG VIEWSET (READ-ONLY)
# ==============================================================================
class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for security Audit Logs.
    Administrators can view all logs; regular users can view only their own logs.
    Supports ?action=, ?entity_name=, and ?entity_id= filtering.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = AuditLogSerializer
    queryset = AuditLog.objects.all()

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='action',
                description='Filter by action (CREATE, UPDATE, DELETE, LOGIN)',
                required=False,
                type=str
            ),
            OpenApiParameter(
                name='entity_name',
                description='Filter by entity name (Project, Task, etc.)',
                required=False,
                type=str
            ),
            OpenApiParameter(
                name='entity_id',
                description='Filter by specific entity ID',
                required=False,
                type=str
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        if getattr(user, 'role', None) == 'ADMIN' or user.is_staff or user.is_superuser:
            queryset = AuditLog.objects.select_related('user').all()
        else:
            queryset = AuditLog.objects.select_related('user').filter(user=user)

        action_param = self.request.query_params.get('action')
        entity_name_param = self.request.query_params.get('entity_name')
        entity_id_param = self.request.query_params.get('entity_id')

        if action_param:
            queryset = queryset.filter(action__iexact=action_param.strip())
        if entity_name_param:
            queryset = queryset.filter(entity_name__iexact=entity_name_param.strip())
        if entity_id_param:
            queryset = queryset.filter(entity_id=entity_id_param.strip())

        return queryset


# ==============================================================================
# TOOL INVENTORY / REQUESTS / RETURNS
# ==============================================================================
class ToolViewSet(viewsets.ModelViewSet):
    """
    CRUD for the tool catalog. GET is available to every authenticated user;
    mutations are ADMIN-only via ToolPermission.
    """
    permission_classes = [IsAuthenticated, ToolPermission]
    serializer_class = ToolSerializer
    queryset = Tool.objects.all()

    def perform_create(self, serializer):
        tool = serializer.save()
        record_audit_log(
            user=self.request.user,
            action=AuditActionChoices.CREATE,
            entity_name='Tool',
            entity_id=tool.id,
            details={'name': tool.name, 'stock': tool.stock},
            ip_address=get_client_ip(self.request)
        )

    def perform_update(self, serializer):
        tool = serializer.save()
        record_audit_log(
            user=self.request.user,
            action=AuditActionChoices.UPDATE,
            entity_name='Tool',
            entity_id=tool.id,
            details={'name': tool.name, 'stock': tool.stock},
            ip_address=get_client_ip(self.request)
        )

    def perform_destroy(self, instance):
        entity_id = instance.id
        details = {'name': instance.name, 'stock': instance.stock}
        try:
            instance.delete()
        except ProtectedError:
            raise ValidationError(
                "No se puede eliminar la herramienta porque tiene pedidos o devoluciones asociados."
            )
        record_audit_log(
            user=self.request.user,
            action=AuditActionChoices.DELETE,
            entity_name='Tool',
            entity_id=entity_id,
            details=details,
            ip_address=get_client_ip(self.request)
        )


class ToolRequestViewSet(viewsets.ModelViewSet):
    """
    Tool orders. MEMBER sees own / assigned-field requests and can cancel only
    PENDIENTE ones. ADMIN sees all, changes status and deletes.
    """
    permission_classes = [IsAuthenticated, ToolRequestPermission]
    serializer_class = ToolRequestSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(name='status', description='Filter by tool request status', required=False, type=str),
            OpenApiParameter(name='tool', description='Filter by Tool UUID', required=False, type=str),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        queryset = ToolRequest.objects.select_related(
            'tool', 'task', 'task__project', 'requested_by'
        ).all()

        if not is_admin_user(self.request.user):
            queryset = queryset.filter(
                Q(requested_by=self.request.user)
                | Q(task__assigned_to=self.request.user)
                | Q(task__project__owner=self.request.user)
            ).distinct()

        status_param = self.request.query_params.get('status')
        tool_param = self.request.query_params.get('tool')
        if status_param:
            queryset = queryset.filter(status__iexact=status_param.strip())
        if tool_param:
            queryset = queryset.filter(tool_id=tool_param.strip())
        return queryset

    def perform_create(self, serializer):
        with transaction.atomic():
            tool_request = serializer.save(requested_by=self.request.user)
            record_audit_log(
                user=self.request.user,
                action=AuditActionChoices.CREATE,
                entity_name='ToolRequest',
                entity_id=tool_request.id,
                details={
                    'tool': tool_request.tool.name,
                    'quantity': tool_request.quantity,
                    'status': tool_request.status,
                },
                ip_address=get_client_ip(self.request)
            )

    def perform_update(self, serializer):
        tool_request = serializer.instance
        old_status = tool_request.status

        with transaction.atomic():
            tool_request = serializer.save()
            new_status = tool_request.status

            if (
                old_status == ToolRequestStatusChoices.PENDIENTE
                and new_status in (ToolRequestStatusChoices.APROBADA, ToolRequestStatusChoices.ENTREGADA)
            ):
                tool = Tool.objects.select_for_update().get(pk=tool_request.tool_id)
                if tool.stock < tool_request.quantity:
                    raise ValidationError({
                        'quantity': (
                            f"Stock insuficiente al aprobar: solicita {tool_request.quantity}, "
                            f"disponible {tool.stock}."
                        )
                    })
                tool.stock -= tool_request.quantity
                tool.save(update_fields=['stock', 'updated_at'])

            if (
                old_status == ToolRequestStatusChoices.APROBADA
                and new_status == ToolRequestStatusChoices.RECHAZADA
            ):
                # An approved order had already consumed stock; rejecting it
                # must give that stock back exactly once.
                tool = Tool.objects.select_for_update().get(pk=tool_request.tool_id)
                tool.stock += tool_request.quantity
                tool.save(update_fields=['stock', 'updated_at'])

            if new_status != old_status:
                record_audit_log(
                    user=self.request.user,
                    action=AuditActionChoices.UPDATE,
                    entity_name='ToolRequest',
                    entity_id=tool_request.id,
                    details={
                        'tool': tool_request.tool.name,
                        'from_status': old_status,
                        'to_status': new_status,
                        'quantity': tool_request.quantity,
                    },
                    ip_address=get_client_ip(self.request)
                )

    def perform_destroy(self, instance):
        entity_id = instance.id
        details = {'tool': instance.tool.name, 'quantity': instance.quantity, 'status': instance.status}
        tool_id = instance.tool_id

        with transaction.atomic():
            if instance.status in (ToolRequestStatusChoices.APROBADA, ToolRequestStatusChoices.ENTREGADA):
                tool = Tool.objects.select_for_update().get(pk=tool_id)
                tool.stock += instance.quantity
                tool.save(update_fields=['stock', 'updated_at'])
                details['stock_restored'] = instance.quantity

            try:
                instance.delete()
            except ProtectedError:
                raise ValidationError(
                    "No se puede cancelar el pedido porque ya tiene devoluciones registradas."
                )

            record_audit_log(
                user=self.request.user,
                action=AuditActionChoices.DELETE,
                entity_name='ToolRequest',
                entity_id=entity_id,
                details=details,
                ip_address=get_client_ip(self.request)
            )


class ToolReturnViewSet(viewsets.ModelViewSet):
    """
    Numbered return receipts. Both roles can register and read them; only ADMIN
    may verify a receipt, which atomically replenishes the tool stock.
    """
    permission_classes = [IsAuthenticated, ToolReturnPermission]
    serializer_class = ToolReturnSerializer

    def get_queryset(self):
        queryset = ToolReturn.objects.select_related(
            'tool_request',
            'tool_request__tool',
            'tool_request__task',
            'tool_request__task__project',
            'tool_request__requested_by',
            'returned_by',
        ).all()

        if not is_admin_user(self.request.user):
            queryset = queryset.filter(
                Q(returned_by=self.request.user)
                | Q(tool_request__requested_by=self.request.user)
            ).distinct()
        return queryset

    def perform_create(self, serializer):
        with transaction.atomic():
            tool_return = serializer.save(returned_by=self.request.user)
            record_audit_log(
                user=self.request.user,
                action=AuditActionChoices.CREATE,
                entity_name='ToolReturn',
                entity_id=tool_return.id,
                details={
                    'return_number': tool_return.return_number,
                    'quantity_returned': tool_return.quantity_returned,
                    'condition': tool_return.condition,
                },
                ip_address=get_client_ip(self.request)
            )

    def perform_update(self, serializer):
        tool_return = serializer.instance
        old_status = tool_return.status

        with transaction.atomic():
            tool_return = serializer.save()
            new_status = tool_return.status

            if (
                old_status != ToolReturnStatusChoices.RECEPCIONADA
                and new_status == ToolReturnStatusChoices.RECEPCIONADA
            ):
                tool = Tool.objects.select_for_update().get(pk=tool_return.tool_request.tool_id)
                tool.stock += tool_return.quantity_returned
                tool.save(update_fields=['stock', 'updated_at'])

                record_audit_log(
                    user=self.request.user,
                    action=AuditActionChoices.UPDATE,
                    entity_name='ToolReturn',
                    entity_id=tool_return.id,
                    details={
                        'return_number': tool_return.return_number,
                        'status': new_status,
                        'quantity_restocked': tool_return.quantity_returned,
                        'tool': tool_return.tool_request.tool.name,
                        'condition': tool_return.condition,
                        'stock_after': tool.stock,
                    },
                    ip_address=get_client_ip(self.request)
                )

    def perform_destroy(self, instance):
        entity_id = instance.id
        details = {
            'return_number': instance.return_number,
            'quantity_returned': instance.quantity_returned,
            'status': instance.status,
        }

        with transaction.atomic():
            if instance.status == ToolReturnStatusChoices.RECEPCIONADA:
                tool = Tool.objects.select_for_update().get(pk=instance.tool_request.tool_id)
                if tool.stock < instance.quantity_returned:
                    raise ValidationError(
                        "No se puede eliminar: el stock ya fue consumido y no se puede revertir."
                    )
                tool.stock -= instance.quantity_returned
                tool.save(update_fields=['stock', 'updated_at'])
                details['stock_reverted'] = instance.quantity_returned

            instance.delete()
            record_audit_log(
                user=self.request.user,
                action=AuditActionChoices.DELETE,
                entity_name='ToolReturn',
                entity_id=entity_id,
                details=details,
                ip_address=get_client_ip(self.request)
            )
