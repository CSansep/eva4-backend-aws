"""
Django admin configuration for all 9 core entities.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from core.models import (
    AuditLog,
    Project,
    Subtask,
    Tag,
    Task,
    TaskComment,
    User,
    Workspace,
    WorkspaceMember,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin configuration for custom User model."""
    list_display = ('email', 'username', 'role', 'is_staff', 'is_active', 'created_at')
    list_filter = ('role', 'is_staff', 'is_active')
    search_fields = ('email', 'username')
    ordering = ('-created_at',)
    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    """Admin configuration for Workspace model."""
    list_display = ('name', 'slug', 'created_by', 'created_at')
    search_fields = ('name', 'slug', 'created_by__email')
    ordering = ('-created_at',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(WorkspaceMember)
class WorkspaceMemberAdmin(admin.ModelAdmin):
    """Admin configuration for WorkspaceMember model."""
    list_display = ('workspace', 'user', 'role', 'joined_at')
    list_filter = ('role', 'workspace')
    search_fields = ('workspace__name', 'user__email')
    ordering = ('-joined_at',)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    """Admin configuration for Project model."""
    list_display = ('name', 'workspace', 'owner', 'is_active', 'created_at')
    list_filter = ('is_active', 'workspace', 'created_at')
    search_fields = ('name', 'owner__email', 'owner__username')
    ordering = ('-created_at',)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    """Admin configuration for Tag model."""
    list_display = ('name', 'color_hex')
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    """Admin configuration for Task model."""
    list_display = ('title', 'project', 'assigned_to', 'status', 'priority', 'due_date', 'created_at')
    list_filter = ('status', 'priority', 'created_at')
    search_fields = ('title', 'project__name', 'assigned_to__email')
    ordering = ('-created_at',)
    filter_horizontal = ('tags',)


@admin.register(TaskComment)
class TaskCommentAdmin(admin.ModelAdmin):
    """Admin configuration for TaskComment model."""
    list_display = ('task', 'author', 'created_at')
    search_fields = ('task__title', 'author__email', 'content')
    ordering = ('-created_at',)


@admin.register(Subtask)
class SubtaskAdmin(admin.ModelAdmin):
    """Admin configuration for Subtask model."""
    list_display = ('title', 'task', 'is_completed', 'order', 'created_at')
    list_filter = ('is_completed',)
    search_fields = ('title', 'task__title')
    ordering = ('task', 'order')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Admin configuration for read-only security AuditLog."""
    list_display = ('action', 'entity_name', 'entity_id', 'user', 'ip_address', 'timestamp')
    list_filter = ('action', 'entity_name', 'timestamp')
    search_fields = ('entity_name', 'entity_id', 'user__email', 'ip_address')
    ordering = ('-timestamp',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
