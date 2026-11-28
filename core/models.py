"""
Core Domain Models.

Defines the 12 interrelated entities:
1. User (UUID pk, email-based auth, role-based access)
2. Workspace (Workspaces / Organizations owned by Users)
3. WorkspaceMember (Membership and role assignment per Workspace)
4. Project (Workspaces grouping Tasks, optionally scoped to a Workspace)
5. Tag (Taxonomy tags with hex color validation)
6. Task (Tasks belonging to Projects, assigned to Users, tagged with Tags)
7. TaskComment (Discussion thread comments on Tasks)
8. Subtask (Actionable checklists belonging to Tasks)
9. AuditLog (Security and operational audit trail)
10. Tool (Tool catalog with live warehouse stock)
11. ToolRequest (Field orders linked to a Task and a Tool)
12. ToolReturn (Numbered return receipts that replenish stock on reception)
"""

import uuid
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, RegexValidator
from django.db import IntegrityError, models, transaction
from django.db.models import Max
from core.managers import UserManager


class RoleChoices(models.TextChoices):
    """User system role choices."""
    ADMIN = 'ADMIN', 'Admin'
    MANAGER = 'MANAGER', 'Manager'
    MEMBER = 'MEMBER', 'Member'


class WorkspaceMemberRoleChoices(models.TextChoices):
    """Workspace membership role choices."""
    OWNER = 'OWNER', 'Owner'
    ADMIN = 'ADMIN', 'Admin'
    COLLABORATOR = 'COLLABORATOR', 'Collaborator'
    VIEWER = 'VIEWER', 'Viewer'


class TaskStatusChoices(models.TextChoices):
    """Task progress status choices."""
    PENDING = 'PENDING', 'Pending'
    IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
    COMPLETED = 'COMPLETED', 'Completed'


class TaskPriorityChoices(models.TextChoices):
    """Task urgency priority choices."""
    LOW = 'LOW', 'Low'
    MEDIUM = 'MEDIUM', 'Medium'
    HIGH = 'HIGH', 'High'


class AuditActionChoices(models.TextChoices):
    """Audit action choices for security tracking."""
    CREATE = 'CREATE', 'Create'
    UPDATE = 'UPDATE', 'Update'
    DELETE = 'DELETE', 'Delete'
    LOGIN = 'LOGIN', 'Login'


class ToolRequestStatusChoices(models.TextChoices):
    """Lifecycle states for a tool request."""
    PENDIENTE = 'PENDIENTE', 'Pendiente'
    APROBADA = 'APROBADA', 'Aprobada'
    ENTREGADA = 'ENTREGADA', 'Entregada'
    RECHAZADA = 'RECHAZADA', 'Rechazada'


class ToolConditionChoices(models.TextChoices):
    """Physical condition recorded when tools come back from the field."""
    BUEN_ESTADO = 'BUEN_ESTADO', 'Buen estado'
    CON_DESGASTE = 'CON_DESGASTE', 'Con desgaste'
    DANADA = 'DANADA', 'Dañada'


class ToolReturnStatusChoices(models.TextChoices):
    """Warehouse verification states for a tool return."""
    PENDIENTE_REVISION = 'PENDIENTE_REVISION', 'Pendiente revisión'
    RECEPCIONADA = 'RECEPCIONADA', 'Recepcionada'


# ==============================================================================
# 1. USER MODEL
# ==============================================================================
class User(AbstractUser):
    """
    Custom User model extending AbstractUser.
    Uses UUID as primary key, email as USERNAME_FIELD, and includes role-based access.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, verbose_name="Email Address")
    username = models.CharField(max_length=150, unique=True, verbose_name="Username")
    role = models.CharField(
        max_length=10,
        choices=RoleChoices.choices,
        default=RoleChoices.MEMBER,
        verbose_name="User Role"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    objects = UserManager()

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.email} ({self.role})"


# ==============================================================================
# 2. WORKSPACE MODEL
# ==============================================================================
class Workspace(models.Model):
    """
    Workspace / Organization entity grouping projects, members, and resources.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, verbose_name="Workspace Name")
    slug = models.SlugField(max_length=140, unique=True, verbose_name="Slug")
    description = models.TextField(blank=True, default="", verbose_name="Description")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='created_workspaces',
        on_delete=models.CASCADE,
        verbose_name="Created By"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")

    class Meta:
        verbose_name = "Workspace"
        verbose_name_plural = "Workspaces"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.slug})"


# ==============================================================================
# 3. WORKSPACE MEMBER MODEL
# ==============================================================================
class WorkspaceMember(models.Model):
    """
    Membership and role assignment for users within a Workspace.
    """
    id = models.AutoField(primary_key=True)
    workspace = models.ForeignKey(
        Workspace,
        related_name='members',
        on_delete=models.CASCADE,
        verbose_name="Workspace"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='workspace_memberships',
        on_delete=models.CASCADE,
        verbose_name="User"
    )
    role = models.CharField(
        max_length=20,
        choices=WorkspaceMemberRoleChoices.choices,
        default=WorkspaceMemberRoleChoices.COLLABORATOR,
        verbose_name="Role"
    )
    joined_at = models.DateTimeField(auto_now_add=True, verbose_name="Joined At")

    class Meta:
        verbose_name = "Workspace Member"
        verbose_name_plural = "Workspace Members"
        unique_together = ('workspace', 'user')
        ordering = ['-joined_at']

    def __str__(self):
        return f"{self.user.email} in {self.workspace.name} as {self.role}"


# ==============================================================================
# 4. PROJECT MODEL
# ==============================================================================
class Project(models.Model):
    """
    Project / Workspace entity grouping tasks under an owner,
    optionally associated with an overarching Workspace organization.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150, verbose_name="Project Name")
    description = models.TextField(blank=True, default="", verbose_name="Description")
    workspace = models.ForeignKey(
        Workspace,
        related_name='projects',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Workspace"
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='owned_projects',
        on_delete=models.CASCADE,
        verbose_name="Owner"
    )
    is_active = models.BooleanField(default=True, verbose_name="Is Active")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")

    class Meta:
        verbose_name = "Project"
        verbose_name_plural = "Projects"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} (Owner: {self.owner.email})"


# ==============================================================================
# 5. TAG MODEL
# ==============================================================================
class Tag(models.Model):
    """
    Tag / Category entity for classifying tasks with validated hex colors.
    """
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=50, unique=True, verbose_name="Tag Name")
    color_hex = models.CharField(
        max_length=7,
        validators=[
            RegexValidator(
                regex=r'^#[0-9A-Fa-f]{6}$',
                message='Color must be a valid 6-character hex code, e.g. #3B82F6.'
            )
        ],
        verbose_name="Hex Color Code"
    )

    class Meta:
        verbose_name = "Tag"
        verbose_name_plural = "Tags"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.color_hex})"


# ==============================================================================
# 6. TASK MODEL
# ==============================================================================
class Task(models.Model):
    """
    Task entity belonging to a Project, optionally assigned to a User,
    tagged with Tags, and supporting S3 file attachments.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, verbose_name="Task Title")
    description = models.TextField(blank=True, default="", verbose_name="Description")
    status = models.CharField(
        max_length=20,
        choices=TaskStatusChoices.choices,
        default=TaskStatusChoices.PENDING,
        verbose_name="Status"
    )
    priority = models.CharField(
        max_length=10,
        choices=TaskPriorityChoices.choices,
        default=TaskPriorityChoices.MEDIUM,
        verbose_name="Priority"
    )
    due_date = models.DateTimeField(null=True, blank=True, verbose_name="Due Date")
    project = models.ForeignKey(
        Project,
        related_name='tasks',
        on_delete=models.CASCADE,
        verbose_name="Project"
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='assigned_tasks',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Assigned User"
    )
    tags = models.ManyToManyField(
        Tag,
        related_name='tasks',
        blank=True,
        verbose_name="Tags"
    )
    attachment = models.FileField(
        upload_to='attachments/',
        null=True,
        blank=True,
        verbose_name="Attachment File"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")

    class Meta:
        verbose_name = "Task"
        verbose_name_plural = "Tasks"
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.status}] {self.title} ({self.project.name})"


# ==============================================================================
# 7. TASK COMMENT MODEL
# ==============================================================================
class TaskComment(models.Model):
    """
    Discussion comments attached to a specific Task.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(
        Task,
        related_name='comments',
        on_delete=models.CASCADE,
        verbose_name="Task"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='comments',
        on_delete=models.CASCADE,
        verbose_name="Author"
    )
    content = models.TextField(verbose_name="Comment Content")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")

    class Meta:
        verbose_name = "Task Comment"
        verbose_name_plural = "Task Comments"
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.author.email} on Task {self.task.title}"


# ==============================================================================
# 8. SUBTASK MODEL
# ==============================================================================
class Subtask(models.Model):
    """
    Actionable checklist item belonging to a parent Task.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(
        Task,
        related_name='subtasks',
        on_delete=models.CASCADE,
        verbose_name="Task"
    )
    title = models.CharField(max_length=200, verbose_name="Subtask Title")
    is_completed = models.BooleanField(default=False, verbose_name="Is Completed")
    order = models.PositiveIntegerField(default=0, verbose_name="Display Order")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")

    class Meta:
        verbose_name = "Subtask"
        verbose_name_plural = "Subtasks"
        ordering = ['order', 'created_at']

    def __str__(self):
        status_symbol = "✓" if self.is_completed else "○"
        return f"[{status_symbol}] {self.title} ({self.task.title})"


# ==============================================================================
# 9. AUDIT LOG MODEL
# ==============================================================================
class AuditLog(models.Model):
    """
    Security and operational audit trail tracking critical create, update, delete,
    and login events across the backend.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='audit_logs',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Triggering User"
    )
    action = models.CharField(
        max_length=20,
        choices=AuditActionChoices.choices,
        verbose_name="Action"
    )
    entity_name = models.CharField(max_length=50, verbose_name="Entity Name")
    entity_id = models.CharField(max_length=64, verbose_name="Entity ID")
    details = models.JSONField(default=dict, blank=True, verbose_name="Details Payload")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP Address")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Timestamp")

    class Meta:
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
        ordering = ['-timestamp']

    def __str__(self):
        user_str = self.user.email if self.user else "System/Anonymous"
        return f"[{self.action}] {self.entity_name} ({self.entity_id}) by {user_str}"


# ==============================================================================
# 10. TOOL MODEL (CATALOG & INVENTORY)
# ==============================================================================
class Tool(models.Model):
    """
    Construction tool catalog with live warehouse stock.

    Read access is granted to every authenticated user; catalog mutations are
    restricted to ADMIN at the permission layer.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, unique=True, verbose_name="Tool Name")
    description = models.TextField(verbose_name="Technical Capacity")
    stock = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Available Stock"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")

    class Meta:
        verbose_name = "Tool"
        verbose_name_plural = "Tools"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} (Stock: {self.stock})"


# ==============================================================================
# 11. TOOL REQUEST MODEL (FIELD ORDERS)
# ==============================================================================
class ToolRequest(models.Model):
    """
    Tool order placed by a MEMBER for a concrete construction task.

    Stock is deducted exactly once when ADMIN moves PENDIENTE -> APROBADA or
    PENDIENTE -> ENTREGADA. The movement is performed by the ViewSet inside an
    atomic transaction with a row lock on the related Tool.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tool = models.ForeignKey(
        Tool,
        related_name='requests',
        on_delete=models.PROTECT,
        verbose_name="Tool"
    )
    task = models.ForeignKey(
        Task,
        related_name='tool_requests',
        on_delete=models.CASCADE,
        verbose_name="Task"
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='tool_requests',
        on_delete=models.CASCADE,
        verbose_name="Requested By"
    )
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="Quantity"
    )
    priority = models.CharField(
        max_length=10,
        choices=TaskPriorityChoices.choices,
        default=TaskPriorityChoices.MEDIUM,
        verbose_name="Priority"
    )
    notes = models.TextField(blank=True, default="", verbose_name="Field Notes")
    status = models.CharField(
        max_length=20,
        choices=ToolRequestStatusChoices.choices,
        default=ToolRequestStatusChoices.PENDIENTE,
        verbose_name="Status"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")

    class Meta:
        verbose_name = "Tool Request"
        verbose_name_plural = "Tool Requests"
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.status}] {self.quantity} x {self.tool.name} - {self.task.title}"


# ==============================================================================
# 12. TOOL RETURN MODEL (NUMBERED WAREHOUSE RETURNS)
# ==============================================================================
class ToolReturn(models.Model):
    """
    Numbered return receipt for a delivered ToolRequest.

    ``return_number`` is a correlative 1, 2, 3... generated safely on save.
    Stock is added back only when ADMIN marks the return as RECEPCIONADA.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    return_number = models.PositiveIntegerField(
        unique=True,
        editable=False,
        null=True,
        blank=True,
        verbose_name="Return Number"
    )
    tool_request = models.ForeignKey(
        ToolRequest,
        related_name='returns',
        on_delete=models.PROTECT,
        verbose_name="Tool Request"
    )
    returned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='tool_returns',
        on_delete=models.CASCADE,
        verbose_name="Returned By"
    )
    quantity_returned = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="Quantity Returned"
    )
    condition = models.CharField(
        max_length=20,
        choices=ToolConditionChoices.choices,
        default=ToolConditionChoices.BUEN_ESTADO,
        verbose_name="Physical Condition"
    )
    observations = models.TextField(blank=True, default="", verbose_name="Observations")
    status = models.CharField(
        max_length=20,
        choices=ToolReturnStatusChoices.choices,
        default=ToolReturnStatusChoices.PENDIENTE_REVISION,
        verbose_name="Warehouse Status"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")

    class Meta:
        verbose_name = "Tool Return"
        verbose_name_plural = "Tool Returns"
        # Most recent receipt first (#003, #002, #001).
        ordering = ['-return_number']

    def __str__(self):
        return f"#{self.return_number:03d} - {self.tool_request.tool.name}"

    def save(self, *args, **kwargs):
        """Assign the next correlative return number atomically.

        PostgreSQL does not allow SELECT FOR UPDATE on an aggregate query, so
        the unique constraint on ``return_number`` is used as the final guard:
        if two requests calculate the same number, the loser retries with a
        freshly calculated value instead of returning a 500.
        """
        if self.return_number is None:
            for attempt in range(5):
                try:
                    with transaction.atomic():
                        last_number = (
                            ToolReturn.objects.aggregate(
                                Max('return_number')
                            )['return_number__max'] or 0
                        )
                        self.return_number = last_number + 1
                        super().save(*args, **kwargs)
                    return
                except IntegrityError:
                    self.return_number = None
                    if attempt == 4:
                        raise
            return
        super().save(*args, **kwargs)
