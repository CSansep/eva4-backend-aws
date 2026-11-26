"""
Regression tests for the EVA4 RBAC contract used by the frontend.

Covers:
- MEMBER may PATCH a task only with {status, attachment}.
- MEMBER may not PUT/DELETE Workspace, Project or Task owned by another user.
- ADMIN may PATCH all three entities and a workspace PATCH preserves its slug.
- TaskComment uses the single text field `content`.
- /auth/me/ exposes `is_superuser` so the UI resolves roles identically to DRF.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Project, RoleChoices, Task, Workspace

User = get_user_model()


class RBACRegressionAPITestCase(APITestCase):
    def setUp(self):
        self.member = User.objects.create_user(
            email='contratista@buildcorp.cl',
            username='contratista1',
            password='MemberPassword123!',
            role=RoleChoices.MEMBER,
        )
        self.admin = User.objects.create_user(
            email='admin@gmail.com',
            username='Admin',
            password='AdminPassword123!',
            role=RoleChoices.ADMIN,
        )
        self.workspace = Workspace.objects.create(
            name='Sede Temuco', slug='sede-temuco', created_by=self.admin
        )
        self.project = Project.objects.create(
            name='Edificio Costanera Sur', owner=self.admin, workspace=self.workspace
        )
        self.task = Task.objects.create(
            title='Hormigonado losa', project=self.project
        )

    @staticmethod
    def _detail(basename, obj):
        return reverse(f'{basename}-detail', kwargs={'pk': obj.id})

    def test_member_can_patch_only_status_or_attachment(self):
        self.client.force_authenticate(self.member)
        url = self._detail('task', self.task)

        response = self.client.patch(url, {'status': 'IN_PROGRESS'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.patch(url, {'priority': 'HIGH'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_member_cannot_delete_or_put_admin_entities(self):
        self.client.force_authenticate(self.member)

        for basename, obj in (
            ('workspace', self.workspace),
            ('project', self.project),
            ('task', self.task),
        ):
            url = self._detail(basename, obj)
            self.assertEqual(
                self.client.delete(url).status_code,
                status.HTTP_403_FORBIDDEN,
            )
            self.assertEqual(
                self.client.put(url, {}, format='json').status_code,
                status.HTTP_403_FORBIDDEN,
            )

    def test_admin_can_patch_all_entities_and_slug_is_stable(self):
        self.client.force_authenticate(self.admin)

        ws_response = self.client.patch(
            self._detail('workspace', self.workspace),
            {'description': 'Sede actualizada'},
            format='json',
        )
        self.assertEqual(ws_response.status_code, status.HTTP_200_OK)
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.slug, 'sede-temuco')

        project_response = self.client.patch(
            self._detail('project', self.project),
            {'is_active': False},
            format='json',
        )
        self.assertEqual(project_response.status_code, status.HTTP_200_OK)

        task_response = self.client.patch(
            self._detail('task', self.task),
            {'title': 'Hormigonado losa 2'},
            format='json',
        )
        self.assertEqual(task_response.status_code, status.HTTP_200_OK)

    def test_comment_uses_content_field(self):
        self.client.force_authenticate(self.member)
        response = self.client.post(
            reverse('comment-list'),
            {'task': str(self.task.id), 'content': 'Nota de terreno'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['content'], 'Nota de terreno')

    def test_auth_me_exposes_is_superuser_for_role_resolution(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse('auth-me'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('is_superuser', response.data)
