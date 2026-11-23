"""
Tests for IsOwnerOrAdmin authorization permissions.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from core.models import Project, Task, RoleChoices

User = get_user_model()


class PermissionsAPITestCase(APITestCase):
    """
    Validates that:
    - Non-owners cannot modify or delete resources owned by another user (403 Forbidden).
    - Owners can modify and delete their own resources (200 / 204).
    - Admins can modify and delete any resource (200 / 204).
    """

    def setUp(self):
        self.owner = User.objects.create_user(
            email='owner@company.com',
            username='project_owner',
            password='OwnerPassword123!',
            role=RoleChoices.MEMBER
        )
        self.other_member = User.objects.create_user(
            email='other@company.com',
            username='other_member',
            password='MemberPassword123!',
            role=RoleChoices.MEMBER
        )
        self.admin_user = User.objects.create_user(
            email='sysadmin@company.com',
            username='sysadmin',
            password='AdminPassword123!',
            role=RoleChoices.ADMIN
        )

        self.project = Project.objects.create(
            name='Secret Security Initiative',
            owner=self.owner
        )
        self.task = Task.objects.create(
            title='Configure AWS WAF Rules',
            project=self.project
        )

        self.project_detail_url = reverse('project-detail', kwargs={'pk': self.project.id})
        self.task_detail_url = reverse('task-detail', kwargs={'pk': self.task.id})

    def test_non_owner_cannot_update_project(self):
        """A user who is not the project owner or ADMIN must receive 403 Forbidden on PUT/PATCH."""
        self.client.force_authenticate(user=self.other_member)
        response = self.client.patch(
            self.project_detail_url,
            {'name': 'Hacked Project Name'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_owner_cannot_delete_project(self):
        """A non-owner must receive 403 Forbidden when attempting to delete a project."""
        self.client.force_authenticate(user=self.other_member)
        response = self.client.delete(self.project_detail_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_update_project(self):
        """The project owner can successfully update the project."""
        self.client.force_authenticate(user=self.owner)
        response = self.client.patch(
            self.project_detail_url,
            {'name': 'Updated Project Name'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.project.refresh_from_db()
        self.assertEqual(self.project.name, 'Updated Project Name')

    def test_admin_can_update_and_delete_any_project(self):
        """An ADMIN user can update and delete any user's project."""
        self.client.force_authenticate(user=self.admin_user)
        # Update
        patch_resp = self.client.patch(
            self.project_detail_url,
            {'description': 'Admin audit completed'},
            format='json'
        )
        self.assertEqual(patch_resp.status_code, status.HTTP_200_OK)

        # Delete
        delete_resp = self.client.delete(self.project_detail_url)
        self.assertEqual(delete_resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Project.objects.filter(id=self.project.id).exists())

    def test_non_owner_cannot_modify_task(self):
        """A user cannot modify a task in a project they do not own."""
        self.client.force_authenticate(user=self.other_member)
        response = self.client.patch(
            self.task_detail_url,
            {'title': 'Unauthorized Modification'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
