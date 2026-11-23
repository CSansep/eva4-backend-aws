"""
Tests for TaskComment and Subtask CRUD endpoints.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from core.models import Project, Task, TaskComment, Subtask

User = get_user_model()


class CommentsAndSubtasksAPITestCase(APITestCase):
    """Tests for /api/v1/comments/ and /api/v1/subtasks/ endpoints."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='lead@example.com',
            username='leaddev',
            password='Password123!'
        )
        self.project = Project.objects.create(name='Sprint 44', owner=self.user)
        self.task = Task.objects.create(title='Implement CloudWatch Alarms', project=self.project)

        self.comment_url = reverse('comment-list')
        self.subtask_url = reverse('subtask-list')
        self.task_detail_url = reverse('task-detail', kwargs={'pk': self.task.id})
        self.client.force_authenticate(user=self.user)

    def test_create_task_comment(self):
        """Creating a comment automatically sets author to request.user."""
        payload = {
            'task': str(self.task.id),
            'content': 'Configured SNS topic and subscription.'
        }
        response = self.client.post(self.comment_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['author_email'], self.user.email)
        self.assertEqual(response.data['content'], 'Configured SNS topic and subscription.')

    def test_create_subtask(self):
        """Creating a subtask links to task."""
        payload = {
            'task': str(self.task.id),
            'title': 'Test 5xx Error Alarm',
            'order': 1
        }
        response = self.client.post(self.subtask_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'Test 5xx Error Alarm')
        self.assertFalse(response.data['is_completed'])

    def test_task_detail_includes_subtasks_and_comments_count(self):
        """Task detail endpoint returns nested counts."""
        TaskComment.objects.create(task=self.task, author=self.user, content='C1')
        TaskComment.objects.create(task=self.task, author=self.user, content='C2')
        Subtask.objects.create(task=self.task, title='Subtask 1')

        response = self.client.get(self.task_detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['comments_count'], 2)
        self.assertEqual(response.data['subtasks_count'], 1)
