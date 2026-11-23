"""
Serializers for EVA4 REST API entities (9 Relational Models).

Includes:
- UserRegistrationSerializer & UserResponseSerializer
- WorkspaceSerializer & WorkspaceMemberSerializer
- ProjectSerializer (supports workspace scoping and task counts)
- TagSerializer (hex color regex & length validation)
- TaskSerializer (nested subtasks count, comments count, due_date future validation)
- TaskCommentSerializer (comment threads on tasks)
- SubtaskSerializer (actionable checklists)
- AuditLogSerializer (read-only audit trail representation)
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import serializers

from core.models import (
    AuditLog,
    Project,
    RoleChoices,
    Subtask,
    Tag,
    Task,
    TaskComment,
    TaskPriorityChoices,
    TaskStatusChoices,
    Workspace,
    WorkspaceMember,
    WorkspaceMemberRoleChoices,
)

User = get_user_model()


# ==============================================================================
# 1. USER SERIALIZERS
# ==============================================================================
class UserResponseSerializer(serializers.ModelSerializer):
    """
    Safe output serializer for User details.
    Never exposes passwords or sensitive authentication tokens.
    """
    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'username',
            'role',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for public user registration.
    Validates password strength, email format, and uniqueness.
    """
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        help_text="Strong password compliant with Django validation standards."
    )
    role = serializers.ChoiceField(
        choices=RoleChoices.choices,
        default=RoleChoices.MEMBER,
        required=False
    )

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'username',
            'password',
            'role',
        ]
        read_only_fields = ['id']

    def validate_password(self, value):
        """Run Django's native password validators."""
        validate_password(value)
        return value

    def validate_email(self, value):
        """Ensure email is normalized and unique."""
        normalized = value.strip().lower()
        if User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError("A user with this email address already exists.")
        return normalized

    def validate_username(self, value):
        """Validate username minimum length and uniqueness."""
        clean_name = value.strip()
        if len(clean_name) < 3:
            raise serializers.ValidationError("Username must contain at least 3 characters.")
        if User.objects.filter(username__iexact=clean_name).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return clean_name

    def create(self, validated_data):
        """Create user safely using UserManager's create_user method."""
        return User.objects.create_user(**validated_data)


# ==============================================================================
# 2. WORKSPACE & WORKSPACE MEMBER SERIALIZERS
# ==============================================================================
class WorkspaceSerializer(serializers.ModelSerializer):
    """
    Serializer for Workspace / Organization entities.
    """
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)
    members_count = serializers.SerializerMethodField(read_only=True)
    projects_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Workspace
        fields = [
            'id',
            'name',
            'slug',
            'description',
            'created_by',
            'created_by_email',
            'created_at',
            'members_count',
            'projects_count',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'members_count', 'projects_count']

    def get_members_count(self, obj) -> int:
        """Return the number of registered members in this workspace."""
        return obj.members.count()

    def get_projects_count(self, obj) -> int:
        """Return the number of projects associated with this workspace."""
        return obj.projects.count()

    def validate_name(self, value):
        """Ensure workspace name has at least 3 characters."""
        clean_name = value.strip()
        if len(clean_name) < 3:
            raise serializers.ValidationError("Workspace name must contain at least 3 characters.")
        return clean_name

    def validate(self, attrs):
        """Auto-generate slug if not explicitly provided."""
        if not attrs.get('slug'):
            name = attrs.get('name', '')
            base_slug = slugify(name)
            slug = base_slug
            counter = 1
            while Workspace.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            attrs['slug'] = slug
        return attrs


class WorkspaceMemberSerializer(serializers.ModelSerializer):
    """
    Serializer for WorkspaceMember entity with role management.
    """
    workspace_name = serializers.CharField(source='workspace.name', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = WorkspaceMember
        fields = [
            'id',
            'workspace',
            'workspace_name',
            'user',
            'user_email',
            'user_username',
            'role',
            'joined_at',
        ]
        read_only_fields = ['id', 'joined_at', 'workspace_name', 'user_email', 'user_username']

    def validate(self, attrs):
        """Enforce uniqueness of user per workspace."""
        workspace = attrs.get('workspace')
        user = attrs.get('user')
        instance = getattr(self, 'instance', None)

        if not instance and WorkspaceMember.objects.filter(workspace=workspace, user=user).exists():
            raise serializers.ValidationError("This user is already a member of the specified workspace.")
        return attrs


# ==============================================================================
# 3. TAG SERIALIZER
# ==============================================================================
class TagSerializer(serializers.ModelSerializer):
    """
    Serializer for classification Tag entities.
    """
    class Meta:
        model = Tag
        fields = [
            'id',
            'name',
            'color_hex',
        ]

    def validate_name(self, value):
        """Ensure tag name has at least 3 characters."""
        clean_name = value.strip()
        if len(clean_name) < 3:
            raise serializers.ValidationError("Tag name must contain at least 3 characters.")
        return clean_name


# ==============================================================================
# 4. PROJECT SERIALIZER
# ==============================================================================
class ProjectSerializer(serializers.ModelSerializer):
    """
    Serializer for Project / Workspace entities.
    """
    owner = serializers.PrimaryKeyRelatedField(read_only=True)
    owner_email = serializers.EmailField(source='owner.email', read_only=True)
    owner_username = serializers.CharField(source='owner.username', read_only=True)
    workspace_name = serializers.CharField(source='workspace.name', read_only=True)
    tasks_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Project
        fields = [
            'id',
            'name',
            'description',
            'workspace',
            'workspace_name',
            'owner',
            'owner_email',
            'owner_username',
            'is_active',
            'created_at',
            'tasks_count',
        ]
        read_only_fields = ['id', 'owner', 'created_at', 'tasks_count', 'workspace_name']

    def get_tasks_count(self, obj) -> int:
        """Return the total number of tasks belonging to this project."""
        return obj.tasks.count()

    def validate_name(self, value):
        """Ensure project name has at least 3 characters."""
        clean_name = value.strip()
        if len(clean_name) < 3:
            raise serializers.ValidationError("Project name must contain at least 3 characters.")
        return clean_name


# ==============================================================================
# 5. SUBTASK & COMMENT SERIALIZERS
# ==============================================================================
class SubtaskSerializer(serializers.ModelSerializer):
    """
    Serializer for Task Checklist Subtasks.
    """
    task_title = serializers.CharField(source='task.title', read_only=True)

    class Meta:
        model = Subtask
        fields = [
            'id',
            'task',
            'task_title',
            'title',
            'is_completed',
            'order',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'task_title']

    def validate_title(self, value):
        """Ensure subtask title has at least 3 characters."""
        clean_title = value.strip()
        if len(clean_title) < 3:
            raise serializers.ValidationError("Subtask title must contain at least 3 characters.")
        return clean_title


class TaskCommentSerializer(serializers.ModelSerializer):
    """
    Serializer for Task discussion comments.
    """
    task_title = serializers.CharField(source='task.title', read_only=True)
    author = serializers.PrimaryKeyRelatedField(read_only=True)
    author_email = serializers.EmailField(source='author.email', read_only=True)
    author_username = serializers.CharField(source='author.username', read_only=True)

    class Meta:
        model = TaskComment
        fields = [
            'id',
            'task',
            'task_title',
            'author',
            'author_email',
            'author_username',
            'content',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'author', 'created_at', 'updated_at', 'task_title', 'author_email', 'author_username']

    def validate_content(self, value):
        """Ensure comment content is not empty."""
        clean_content = value.strip()
        if not clean_content:
            raise serializers.ValidationError("Comment content cannot be empty.")
        return clean_content


# ==============================================================================
# 6. TASK SERIALIZER
# ==============================================================================
class TaskSerializer(serializers.ModelSerializer):
    """
    Serializer for Task entities with validation and relation expansion.
    """
    project_name = serializers.CharField(source='project.name', read_only=True)
    assigned_to_email = serializers.EmailField(source='assigned_to.email', read_only=True)
    assigned_to_username = serializers.CharField(source='assigned_to.username', read_only=True)
    tag_details = TagSerializer(source='tags', many=True, read_only=True)
    subtasks_count = serializers.SerializerMethodField(read_only=True)
    comments_count = serializers.SerializerMethodField(read_only=True)
    subtask_list = SubtaskSerializer(source='subtasks', many=True, read_only=True)

    class Meta:
        model = Task
        fields = [
            'id',
            'title',
            'description',
            'status',
            'priority',
            'due_date',
            'project',
            'project_name',
            'assigned_to',
            'assigned_to_email',
            'assigned_to_username',
            'tags',
            'tag_details',
            'attachment',
            'subtasks_count',
            'comments_count',
            'subtask_list',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'subtasks_count', 'comments_count', 'subtask_list']

    def get_subtasks_count(self, obj) -> int:
        """Return the number of subtasks in this task."""
        return obj.subtasks.count()

    def get_comments_count(self, obj) -> int:
        """Return the number of comments posted on this task."""
        return obj.comments.count()

    def validate_title(self, value):
        """Ensure task title has at least 3 characters."""
        clean_title = value.strip()
        if len(clean_title) < 3:
            raise serializers.ValidationError("Task title must contain at least 3 characters.")
        return clean_title

    def validate_due_date(self, value):
        """
        Validate that due_date cannot be in the past upon creation or update.
        """
        if value is not None and value < timezone.now():
            raise serializers.ValidationError("Due date cannot be set in the past.")
        return value


# ==============================================================================
# 7. AUDIT LOG SERIALIZER
# ==============================================================================
class AuditLogSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for security Audit Log events.
    """
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id',
            'user',
            'user_email',
            'action',
            'entity_name',
            'entity_id',
            'details',
            'ip_address',
            'timestamp',
        ]
        read_only_fields = fields
