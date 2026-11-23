"""
Unit tests for Core Data Models (9 Relational Entities).
"""

import uuid
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from core.models import (
    AuditActionChoices,
    AuditLog,
    Project,
    RoleChoices,
    Subtask,
    Tag,
    Task,
    TaskComment,
    TaskPriorityChoices,
    TaskStatusChoices,
    Workspace,
    WorkspaceMember,
    WorkspaceMemberRoleChoices,
)

User = get_user_model()


class UserModelTestCase(TestCase):
    """Tests for custom User model with UUID and email authentication."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='testuser@example.com',
            username='testuser',
            password='ComplexPassword123!',
            role=RoleChoices.MEMBER
        )

    def test_user_creation_with_uuid(self):
        """User primary key must be a valid UUID."""
        self.assertIsInstance(self.user.id, uuid.UUID)
        self.assertEqual(self.user.email, 'testuser@example.com')
        self.assertEqual(self.user.username, 'testuser')
        self.assertEqual(self.user.role, RoleChoices.MEMBER)
        self.assertTrue(self.user.is_active)
        self.assertFalse(self.user.is_staff)

    def test_user_password_hashing(self):
        """Password must be securely hashed and verifiable via check_password."""
        self.assertTrue(self.user.check_password('ComplexPassword123!'))
        self.assertFalse(self.user.check_password('WrongPassword!'))
        self.assertNotEqual(self.user.password, 'ComplexPassword123!')
        self.assertTrue(self.user.password.startswith('pbkdf2_sha256$'))

    def test_create_superuser(self):
        """Superuser creation must enforce is_staff, is_superuser, and ADMIN role."""
        admin_user = User.objects.create_superuser(
            email='admin@example.com',
            username='admin',
            password='AdminPassword123!'
        )
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)
        self.assertEqual(admin_user.role, RoleChoices.ADMIN)


class WorkspaceAndMembershipModelTestCase(TestCase):
    """Tests for Workspace and WorkspaceMember models."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='founder@example.com',
            username='founder',
            password='Password123!'
        )
        self.workspace = Workspace.objects.create(
            name='Acme Cloud',
            slug='acme-cloud',
            created_by=self.user
        )

    def test_workspace_creation(self):
        """Workspace must have UUID pk and correct slug."""
        self.assertIsInstance(self.workspace.id, uuid.UUID)
        self.assertEqual(self.workspace.slug, 'acme-cloud')
        self.assertEqual(self.workspace.created_by, self.user)

    def test_workspace_member_unique_together(self):
        """Same user cannot be added twice to the same workspace."""
        WorkspaceMember.objects.create(
            workspace=self.workspace,
            user=self.user,
            role=WorkspaceMemberRoleChoices.OWNER
        )
        with self.assertRaises(IntegrityError):
            WorkspaceMember.objects.create(
                workspace=self.workspace,
                user=self.user,
                role=WorkspaceMemberRoleChoices.COLLABORATOR
            )


class ProjectAndTaskModelTestCase(TestCase):
    """Tests for Project, Task, Subtask, and TaskComment models."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='techlead@example.com',
            username='techlead',
            password='Password123!'
        )
        self.workspace = Workspace.objects.create(
            name='DevOps Org',
            slug='devops-org',
            created_by=self.user
        )
        self.project = Project.objects.create(
            name='Multi-Cloud Architecture',
            workspace=self.workspace,
            owner=self.user
        )
        self.task = Task.objects.create(
            title='Setup Amazon RDS PostgreSQL',
            project=self.project
        )

    def test_project_workspace_link(self):
        """Project can be linked to a Workspace."""
        self.assertEqual(self.project.workspace, self.workspace)
        self.assertIn(self.project, self.workspace.projects.all())

    def test_subtask_creation(self):
        """Subtask must link to Task with completion toggle."""
        subtask = Subtask.objects.create(
            task=self.task,
            title='Enable Multi-AZ replication',
            order=1
        )
        self.assertIsInstance(subtask.id, uuid.UUID)
        self.assertFalse(subtask.is_completed)
        self.assertEqual(subtask.task, self.task)

    def test_task_comment_creation(self):
        """TaskComment links author and task."""
        comment = TaskComment.objects.create(
            task=self.task,
            author=self.user,
            content='Security Group ingress on port 5432 configured.'
        )
        self.assertIsInstance(comment.id, uuid.UUID)
        self.assertEqual(comment.author, self.user)
        self.assertEqual(comment.task, self.task)


class AuditLogModelTestCase(TestCase):
    """Tests for AuditLog security logging entity."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='auditor@example.com',
            username='auditor',
            password='Password123!'
        )

    def test_audit_log_record(self):
        """AuditLog must store structured details and user references."""
        log = AuditLog.objects.create(
            user=self.user,
            action=AuditActionChoices.CREATE,
            entity_name='Project',
            entity_id=str(uuid.uuid4()),
            details={'name': 'Audited Project'},
            ip_address='192.168.1.1'
        )
        self.assertIsInstance(log.id, uuid.UUID)
        self.assertEqual(log.action, AuditActionChoices.CREATE)
        self.assertEqual(log.ip_address, '192.168.1.1')
        self.assertIn('Audited Project', log.details.get('name'))
