"""
Tests for Task CRUD endpoints, due_date validation, and query parameter filtering.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from core.models import Project, Task, Tag, TaskStatusChoices, TaskPriorityChoices

User = get_user_model()


class TaskAPITestCase(APITestCase):
    """Tests for /api/v1/tasks/ ViewSet."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='lead@example.com',
            username='teamlead',
            password='StrongPassword123!'
        )
        self.project = Project.objects.create(
            name='Core Infrastructure',
            owner=self.user
        )
        self.tag = Tag.objects.create(name='DevSecOps', color_hex='#2563EB')
        self.list_url = reverse('task-list')
        self.client.force_authenticate(user=self.user)

    def test_create_task_with_future_due_date(self):
        """Creating a task with a valid future due date succeeds."""
        future_date = (timezone.now() + timezone.timedelta(days=5)).isoformat()
        payload = {
            'title': 'Deploy PostgreSQL RDS',
            'description': 'Configure Multi-AZ RDS instance',
            'status': TaskStatusChoices.PENDING,
            'priority': TaskPriorityChoices.HIGH,
            'due_date': future_date,
            'project': str(self.project.id),
            'tags': [self.tag.id]
        }
        response = self.client.post(self.list_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'Deploy PostgreSQL RDS')
        self.assertEqual(response.data['priority'], TaskPriorityChoices.HIGH)

    def test_create_task_with_past_due_date_rejected(self):
        """Creating a task with a past due date must return 400 Bad Request."""
        past_date = (timezone.now() - timezone.timedelta(days=2)).isoformat()
        payload = {
            'title': 'Outdated Task',
            'project': str(self.project.id),
            'due_date': past_date
        }
        response = self.client.post(self.list_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('due_date', response.data)

    def test_task_title_under_three_chars_rejected(self):
        """Task title with less than 3 characters must return 400 Bad Request."""
        payload = {
            'title': 'No',
            'project': str(self.project.id)
        }
        response = self.client.post(self.list_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('title', response.data)

    def test_task_filtering_by_query_params(self):
        """Tasks can be filtered via ?status=, ?priority=, and ?project= query params."""
        t1 = Task.objects.create(
            title='Pending Low Task',
            project=self.project,
            status=TaskStatusChoices.PENDING,
            priority=TaskPriorityChoices.LOW
        )
        t2 = Task.objects.create(
            title='Completed High Task',
            project=self.project,
            status=TaskStatusChoices.COMPLETED,
            priority=TaskPriorityChoices.HIGH
        )

        # Filter by status
        resp_status = self.client.get(f"{self.list_url}?status=COMPLETED")
        results = resp_status.data.get('results', resp_status.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], str(t2.id))

        # Filter by priority
        resp_priority = self.client.get(f"{self.list_url}?priority=LOW")
        results = resp_priority.data.get('results', resp_priority.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], str(t1.id))

        # Filter by project
        resp_proj = self.client.get(f"{self.list_url}?project={self.project.id}")
        results = resp_proj.data.get('results', resp_proj.data)
        self.assertEqual(len(results), 2)
