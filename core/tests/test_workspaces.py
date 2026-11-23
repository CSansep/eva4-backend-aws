"""
Tests for Workspace & WorkspaceMember CRUD endpoints.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from core.models import Workspace, WorkspaceMember, WorkspaceMemberRoleChoices

User = get_user_model()


class WorkspaceAPITestCase(APITestCase):
    """Tests for /api/v1/workspaces/ and /api/v1/workspace-members/ endpoints."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='owner@workspace.com',
            username='wsowner',
            password='StrongPassword123!'
        )
        self.collab = User.objects.create_user(
            email='collab@workspace.com',
            username='wscollab',
            password='StrongPassword123!'
        )
        self.workspace_list_url = reverse('workspace-list')
        self.member_list_url = reverse('workspace-member-list')
        self.client.force_authenticate(user=self.user)

    def test_create_workspace_auto_assigns_creator_and_owner_role(self):
        """Creating a workspace must assign created_by and add creator as OWNER member."""
        payload = {
            'name': 'Enterprise Engineering',
            'slug': 'enterprise-eng',
            'description': 'Main engineering workspace'
        }
        response = self.client.post(self.workspace_list_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Enterprise Engineering')
        self.assertEqual(response.data['created_by_email'], self.user.email)

        # Check membership
        workspace_id = response.data['id']
        membership = WorkspaceMember.objects.filter(workspace_id=workspace_id, user=self.user).first()
        self.assertIsNotNone(membership)
        self.assertEqual(membership.role, WorkspaceMemberRoleChoices.OWNER)

    def test_workspace_name_under_three_chars_rejected(self):
        """Workspace name with less than 3 characters must return 400."""
        payload = {'name': 'AB'}
        response = self.client.post(self.workspace_list_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_add_member_to_workspace(self):
        """Add collaborator to workspace via /api/v1/workspace-members/."""
        ws = Workspace.objects.create(name='Design System', slug='design-sys', created_by=self.user)
        payload = {
            'workspace': str(ws.id),
            'user': str(self.collab.id),
            'role': WorkspaceMemberRoleChoices.COLLABORATOR
        }
        response = self.client.post(self.member_list_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['role'], WorkspaceMemberRoleChoices.COLLABORATOR)

    def test_duplicate_member_rejected(self):
        """Adding same member twice must return 400 Bad Request."""
        ws = Workspace.objects.create(name='Finance', slug='finance', created_by=self.user)
        WorkspaceMember.objects.create(workspace=ws, user=self.collab, role=WorkspaceMemberRoleChoices.VIEWER)

        payload = {
            'workspace': str(ws.id),
            'user': str(self.collab.id),
            'role': WorkspaceMemberRoleChoices.ADMIN
        }
        response = self.client.post(self.member_list_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
