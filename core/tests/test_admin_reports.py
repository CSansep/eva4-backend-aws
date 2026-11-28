"""
Tests for the ADMIN dashboard and CSV-ready report endpoints.

These endpoints are read-only aggregations: they must never expose operational
data to MEMBER users and must not mutate stock or domain entities.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import (
    Project,
    RoleChoices,
    Task,
    Tool,
    ToolConditionChoices,
    ToolRequest,
    ToolRequestStatusChoices,
    ToolReturn,
    ToolReturnStatusChoices,
)

User = get_user_model()


class AdminDashboardAndReportTestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email='panel.admin@example.com',
            username='panel_admin',
            password='AdminPassword123!',
            role=RoleChoices.ADMIN,
        )
        self.member = User.objects.create_user(
            email='panel.member@example.com',
            username='panel_member',
            password='MemberPassword123!',
            role=RoleChoices.MEMBER,
        )
        self.project = Project.objects.create(name='Obra Panel', owner=self.admin)
        self.task = Task.objects.create(
            title='Faena vencida',
            project=self.project,
            due_date=timezone.now() - timedelta(days=2),
        )
        self.tool = Tool.objects.create(
            name='Taladro Demoledor',
            description='Demolición ligera, 1100W.',
            category='Eléctrico',
            location='Bodega Norte',
            minimum_stock=3,
            is_active=True,
            stock=1,
        )

    def test_member_cannot_access_admin_dashboard_or_reports(self):
        self.client.force_authenticate(self.member)
        urls = [
            'admin-dashboard',
            'report-inventory',
            'report-tool-requests',
            'report-tool-returns',
        ]
        for name in urls:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, name)

    def test_admin_dashboard_aggregates_low_stock_pending_work_and_overdue_tasks(self):
        delivered = ToolRequest.objects.create(
            requested_by=self.member,
            tool=self.tool,
            task=self.task,
            quantity=1,
            status=ToolRequestStatusChoices.ENTREGADA,
        )
        ToolRequest.objects.create(
            requested_by=self.member,
            tool=self.tool,
            task=self.task,
            quantity=1,
            status=ToolRequestStatusChoices.PENDIENTE,
        )
        ToolReturn.objects.create(
            tool_request=delivered,
            returned_by=self.member,
            quantity_returned=1,
            condition=ToolConditionChoices.BUEN_ESTADO,
            status=ToolReturnStatusChoices.PENDIENTE_REVISION,
        )

        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse('admin-dashboard'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        totals = response.data['totals']
        self.assertEqual(totals['tools_low_stock'], 1)
        self.assertEqual(totals['pending_requests'], 1)
        self.assertEqual(totals['pending_returns'], 1)
        self.assertEqual(totals['tasks_overdue'], 1)
        self.assertEqual(response.data['low_stock_tools'][0]['name'], self.tool.name)
        self.assertEqual(response.data['low_stock_tools'][0]['minimum_stock'], 3)

    def test_tool_serializer_exposes_catalog_fields(self):
        self.client.force_authenticate(self.member)
        response = self.client.get(
            reverse('tool-detail', kwargs={'pk': self.tool.id})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['category'], 'Eléctrico')
        self.assertEqual(response.data['location'], 'Bodega Norte')
        self.assertEqual(response.data['minimum_stock'], 3)
        self.assertTrue(response.data['is_active'])
        self.assertTrue(response.data['low_stock'])

    def test_admin_can_create_tool_with_catalog_fields(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(reverse('tool-list'), {
            'name': 'Compactador de Piso',
            'description': 'Compactación de pavimento, 5.5HP.',
            'category': 'Maquinaria',
            'location': 'Bodega Sur',
            'minimum_stock': 2,
            'is_active': True,
            'stock': 4,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['category'], 'Maquinaria')
        self.assertEqual(response.data['location'], 'Bodega Sur')
        self.assertEqual(response.data['minimum_stock'], 2)
        self.assertFalse(response.data['low_stock'])

    def test_inventory_report_contains_full_catalog_for_admin(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse('report-inventory'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        row = response.data[0]
        self.assertEqual(row['category'], 'Eléctrico')
        self.assertEqual(row['stock'], 1)
        self.assertTrue(row['low_stock'])

    def test_request_report_supports_status_filter(self):
        pending = ToolRequest.objects.create(
            requested_by=self.member,
            tool=self.tool,
            task=self.task,
            quantity=1,
            status=ToolRequestStatusChoices.PENDIENTE,
        )
        ToolRequest.objects.create(
            requested_by=self.member,
            tool=self.tool,
            task=self.task,
            quantity=1,
            status=ToolRequestStatusChoices.RECHAZADA,
        )

        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse('report-tool-requests'), {'status': 'PENDIENTE'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], str(pending.id))
        self.assertEqual(response.data[0]['requested_by_email'], self.member.email)

    def test_return_report_contains_correlative_number(self):
        delivered = ToolRequest.objects.create(
            requested_by=self.member,
            tool=self.tool,
            task=self.task,
            quantity=1,
            status=ToolRequestStatusChoices.ENTREGADA,
        )
        ToolReturn.objects.create(
            tool_request=delivered,
            returned_by=self.member,
            quantity_returned=1,
        )

        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse('report-tool-returns'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['return_number_display'], '#001')
