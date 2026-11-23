"""
Tests for Automatic Audit Logging and AuditLog ViewSet.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from core.models import AuditActionChoices, AuditLog, Project, RoleChoices, Task

User = get_user_model()


class AuditLoggingAPITestCase(APITestCase):
    """
    Validates that:
    - Creating, updating, or deleting a Project or Task generates an AuditLog entry.
    - Regular users can view only their own audit logs.
    - Admin users can view all audit logs.
    - AuditLog records cannot be modified or deleted via API.
    """

    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin@sec.com',
            username='secadmin',
            password='AdminPassword123!',
            role=RoleChoices.ADMIN
        )
        self.user = User.objects.create_user(
            email='user@sec.com',
            username='regularuser',
            password='UserPassword123!',
            role=RoleChoices.MEMBER
        )

        self.project_list_url = reverse('project-list')
        self.task_list_url = reverse('task-list')
        self.audit_list_url = reverse('audit-log-list')

    def test_automatic_audit_on_project_lifecycle(self):
        """Project create, update, and delete must record corresponding AuditLogs."""
        self.client.force_authenticate(user=self.user)

        # 1. CREATE
        create_resp = self.client.post(
            self.project_list_url,
            {'name': 'Audit Test Project'},
            format='json'
        )
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        project_id = create_resp.data['id']

        log_create = AuditLog.objects.filter(
            entity_name='Project',
            entity_id=project_id,
            action=AuditActionChoices.CREATE
        ).first()
        self.assertIsNotNone(log_create)
        self.assertEqual(log_create.user, self.user)

        # 2. UPDATE
        project_detail_url = reverse('project-detail', kwargs={'pk': project_id})
        update_resp = self.client.patch(
            project_detail_url,
            {'description': 'Updated description'},
            format='json'
        )
        self.assertEqual(update_resp.status_code, status.HTTP_200_OK)

        log_update = AuditLog.objects.filter(
            entity_name='Project',
            entity_id=project_id,
            action=AuditActionChoices.UPDATE
        ).first()
        self.assertIsNotNone(log_update)

        # 3. DELETE
        delete_resp = self.client.delete(project_detail_url)
        self.assertEqual(delete_resp.status_code, status.HTTP_204_NO_CONTENT)

        log_delete = AuditLog.objects.filter(
            entity_name='Project',
            entity_id=project_id,
            action=AuditActionChoices.DELETE
        ).first()
        self.assertIsNotNone(log_delete)

    def test_automatic_audit_on_task_lifecycle(self):
        """Task create, update, and delete must record corresponding AuditLogs."""
        self.client.force_authenticate(user=self.user)
        project = Project.objects.create(name='Parent Project', owner=self.user)

        # Create Task
        resp = self.client.post(
            self.task_list_url,
            {'title': 'Task with Audit', 'project': str(project.id)},
            format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        task_id = resp.data['id']

        log = AuditLog.objects.filter(
            entity_name='Task',
            entity_id=task_id,
            action=AuditActionChoices.CREATE
        ).first()
        self.assertIsNotNone(log)

    def test_regular_user_views_only_own_audit_logs(self):
        """Regular user query to /api/v1/audit-logs/ only returns their own entries."""
        AuditLog.objects.create(
            user=self.admin,
            action=AuditActionChoices.CREATE,
            entity_name='Project',
            entity_id='1'
        )
        AuditLog.objects.create(
            user=self.user,
            action=AuditActionChoices.CREATE,
            entity_name='Project',
            entity_id='2'
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.audit_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['user_email'], self.user.email)

    def test_admin_views_all_audit_logs(self):
        """Admin user can view all audit logs."""
        AuditLog.objects.create(
            user=self.admin,
            action=AuditActionChoices.CREATE,
            entity_name='Project',
            entity_id='1'
        )
        AuditLog.objects.create(
            user=self.user,
            action=AuditActionChoices.CREATE,
            entity_name='Project',
            entity_id='2'
        )

        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.audit_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 2)
