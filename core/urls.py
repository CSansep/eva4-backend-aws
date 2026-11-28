"""
URL routing configuration for the core application (12 Relational Entities).

Registers ViewSets with DefaultRouter under /api/v1/ and exposes authentication,
health check, and OpenAPI documentation endpoints.
"""

from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from core.views import (
    AuditLogViewSet,
    HealthCheckView,
    ProjectViewSet,
    RegisterView,
    SubtaskViewSet,
    TagViewSet,
    TaskCommentViewSet,
    TaskViewSet,
    ToolRequestViewSet,
    ToolReturnViewSet,
    ToolViewSet,
    UserProfileView,
    WorkspaceMemberViewSet,
    WorkspaceViewSet,
)

router = DefaultRouter()
# Workspaces and Memberships
router.register(r'workspaces', WorkspaceViewSet, basename='workspace')
router.register(r'workspace-members', WorkspaceMemberViewSet, basename='workspace-member')

# Projects and Tags
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'tags', TagViewSet, basename='tag')

# Tasks, Comments, and Subtasks
router.register(r'tasks', TaskViewSet, basename='task')
router.register(r'comments', TaskCommentViewSet, basename='comment')
router.register(r'subtasks', SubtaskViewSet, basename='subtask')

# Tool inventory, field requests and numbered returns
router.register(r'tools', ToolViewSet, basename='tool')
router.register(r'tool-requests', ToolRequestViewSet, basename='tool-request')
router.register(r'tool-returns', ToolReturnViewSet, basename='tool-return')

# Security Audit Logs (Read-only)
router.register(r'audit-logs', AuditLogViewSet, basename='audit-log')

urlpatterns = [
    # Router endpoints
    path('', include(router.urls)),

    # Authentication endpoints
    path('auth/register/', RegisterView.as_view(), name='auth-register'),
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/me/', UserProfileView.as_view(), name='auth-me'),

    # Infrastructure Health Check (AWS API Gateway / ALB)
    path('health/', HealthCheckView.as_view(), name='health-check'),

    # OpenAPI 3.0 Schema and Interactive Swagger UI
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]
