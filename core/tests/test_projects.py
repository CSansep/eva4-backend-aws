"""
Tests for Project CRUD endpoints, serializer validation, and owner assignment.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from core.models import Project

User = get_user_model()


class ProjectAPITestCase(APITestCase):
    """Tests for /api/v1/projects/ ViewSet."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='developer@example.com',
            username='developer',
            password='StrongPassword123!'
        )
        self.list_url = reverse('project-list')
        self.client.force_authenticate(user=self.user)

    def test_create_project_auto_assigns_owner(self):
        """Creating a project must automatically assign request.user as owner."""
        payload = {
            'name': 'API Gateway Integration',
            'description': 'Setting up AWS API Gateway with EC2 Backend'
        }
        response = self.client.post(self.list_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'API Gateway Integration')
        self.assertEqual(response.data['owner_email'], self.user.email)

        # Check DB
        project = Project.objects.get(id=response.data['id'])
        self.assertEqual(project.owner, self.user)

    def test_project_name_too_short_rejected(self):
        """Project names with less than 3 characters must return 400 Bad Request."""
        payload = {'name': 'AB'}
        response = self.client.post(self.list_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data)

    def test_list_projects(self):
        """Authenticated users can list projects."""
        Project.objects.create(name='Project 1', owner=self.user)
        Project.objects.create(name='Project 2', owner=self.user)

        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Handle paginated or direct list response
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 2)
