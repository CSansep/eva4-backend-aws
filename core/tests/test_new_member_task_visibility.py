"""
Regression test: a freshly registered MEMBER must see available tasks so the
tool-request selector is never empty, even without a Workspace membership.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Project, RoleChoices, Task, Tool

User = get_user_model()


class NewMemberTaskVisibilityTestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email='visibility.admin@example.com',
            username='visibility_admin',
            password='AdminPassword123!',
            role=RoleChoices.ADMIN,
        )
        self.project = Project.objects.create(name='Obra Visible', owner=self.admin)
        self.task = Task.objects.create(title='Faena disponible', project=self.project)
        self.tool = Tool.objects.create(
            name='Martillo Neumático',
            description='Demolición de muros, 28mm.',
            stock=5,
        )

    def test_new_registered_member_sees_tasks_and_can_request_a_tool(self):
        register_response = self.client.post(reverse('auth-register'), {
            'email': 'nuevo.member@example.com',
            'username': 'nuevo_member',
            'password': 'MemberPassword123!',
        }, format='json')
        self.assertEqual(register_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(register_response.data['role'], RoleChoices.MEMBER)

        new_member = User.objects.get(email='nuevo.member@example.com')
        self.assertEqual(new_member.workspace_memberships.count(), 0)

        self.client.force_authenticate(new_member)
        tasks_response = self.client.get(reverse('task-list'))
        self.assertEqual(tasks_response.status_code, status.HTTP_200_OK)
        tasks = tasks_response.data.get('results', tasks_response.data)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['id'], str(self.task.id))

        tools_response = self.client.get(reverse('tool-list'))
        self.assertEqual(tools_response.status_code, status.HTTP_200_OK)
        tools = tools_response.data.get('results', tools_response.data)
        self.assertEqual(len(tools), 1)

        request_response = self.client.post(reverse('tool-request-list'), {
            'tool': str(self.tool.id),
            'task': str(self.task.id),
            'quantity': 1,
        }, format='json')
        self.assertEqual(request_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(request_response.data['status'], 'PENDIENTE')
