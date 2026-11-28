"""
Tests for the Tool Inventory module.

Covers the strict ADMIN/MEMBER split, stock validation and movements,
correlative return numbering and warehouse reception auditing.
"""

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import (
    AuditActionChoices,
    AuditLog,
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


class ToolModuleAPITestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email='inventario.admin@example.com',
            username='inventario_admin',
            password='AdminPassword123!',
            role=RoleChoices.ADMIN,
        )
        self.member = User.objects.create_user(
            email='contratista@example.com',
            username='contratista_inventario',
            password='MemberPassword123!',
            role=RoleChoices.MEMBER,
        )
        self.project = Project.objects.create(
            name='Obra Inventario', owner=self.admin
        )
        self.task = Task.objects.create(
            title='Hormigonado losa', project=self.project
        )
        self.tool = Tool.objects.create(
            name='Rotomartillo SDS Plus',
            description='Perforación en hormigón armado hasta 28mm, 850W, 3.2J.',
            stock=10,
        )

    def _request_payload(self, quantity=2, **extra):
        payload = {
            'tool': str(self.tool.id),
            'task': str(self.task.id),
            'quantity': quantity,
            'priority': 'HIGH',
            'notes': 'Pedido de prueba',
        }
        payload.update(extra)
        return payload

    def test_admin_can_create_tool(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(reverse('tool-list'), {
            'name': 'Esmeril Angular 7"',
            'description': 'Corte y desbaste de acero, 180mm, 1200W.',
            'stock': 6,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Tool.objects.filter(name='Esmeril Angular 7"').exists())
        self.assertEqual(response.data['stock'], 6)
        self.assertEqual(response.data['requests_count'], 0)

    def test_member_cannot_mutate_tool_but_can_read_it(self):
        self.client.force_authenticate(self.member)

        list_response = self.client.get(reverse('tool-list'))
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        tools = list_response.data.get('results', list_response.data)
        self.assertEqual(len(tools), 1)

        create_response = self.client.post(reverse('tool-list'), {
            'name': 'Herramienta Prohibida',
            'description': 'Intento de creación por MEMBER.',
            'stock': 99,
        }, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)

        detail_url = reverse('tool-detail', kwargs={'pk': self.tool.id})
        self.assertEqual(
            self.client.patch(detail_url, {'stock': 0}, format='json').status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.delete(detail_url).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_request_over_available_stock_is_rejected(self):
        self.client.force_authenticate(self.member)
        response = self.client.post(
            reverse('tool-request-list'),
            self._request_payload(quantity=11),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('quantity', response.data)
        self.assertIn('Stock insuficiente', str(response.data['quantity']))
        self.assertEqual(ToolRequest.objects.count(), 0)

    def test_member_request_is_forced_to_pending_and_scoped(self):
        self.client.force_authenticate(self.member)
        response = self.client.post(
            reverse('tool-request-list'),
            self._request_payload(quantity=2, status='ENTREGADA'),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], ToolRequestStatusChoices.PENDIENTE)
        self.assertEqual(response.data['requested_by'], self.member.id)

        list_response = self.client.get(reverse('tool-request-list'))
        requests_data = list_response.data.get('results', list_response.data)
        self.assertEqual(len(requests_data), 1)

    def test_admin_delivery_deducts_stock_exactly_once(self):
        self.client.force_authenticate(self.member)
        created = self.client.post(
            reverse('tool-request-list'),
            self._request_payload(quantity=3),
            format='json',
        )
        request_id = created.data['id']
        detail_url = reverse('tool-request-detail', kwargs={'pk': request_id})

        self.client.force_authenticate(self.admin)
        approved = self.client.patch(
            detail_url, {'status': ToolRequestStatusChoices.APROBADA}, format='json'
        )
        self.assertEqual(approved.status_code, status.HTTP_200_OK)
        self.tool.refresh_from_db()
        self.assertEqual(self.tool.stock, 7)

        delivered = self.client.patch(
            detail_url, {'status': ToolRequestStatusChoices.ENTREGADA}, format='json'
        )
        self.assertEqual(delivered.status_code, status.HTTP_200_OK)
        self.tool.refresh_from_db()
        self.assertEqual(self.tool.stock, 7)
        self.assertEqual(ToolRequest.objects.get(pk=request_id).status, 'ENTREGADA')

    def test_returns_are_numbered_correlatively(self):
        delivered_request = ToolRequest.objects.create(
            tool=self.tool,
            task=self.task,
            requested_by=self.member,
            quantity=4,
            status=ToolRequestStatusChoices.ENTREGADA,
        )

        for _ in range(3):
            ToolReturn.objects.create(
                tool_request=delivered_request,
                returned_by=self.member,
                quantity_returned=1,
                condition=ToolConditionChoices.BUEN_ESTADO,
            )

        numbers = list(
            ToolReturn.objects.order_by('return_number')
            .values_list('return_number', flat=True)
        )
        self.assertEqual(numbers, [1, 2, 3])

        serialized = self.client.get(reverse('tool-return-list'))
        # Anonymous read is rejected; authenticate to inspect the formatted label.
        self.assertEqual(serialized.status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.force_authenticate(self.member)
        serialized = self.client.get(reverse('tool-return-list'))
        returns_data = serialized.data.get('results', serialized.data)
        labels = {item['return_number_display'] for item in returns_data}
        self.assertEqual(labels, {'#001', '#002', '#003'})

    def test_receiving_return_restores_stock_and_writes_audit(self):
        delivered_request = ToolRequest.objects.create(
            tool=self.tool,
            task=self.task,
            requested_by=self.member,
            quantity=4,
            status=ToolRequestStatusChoices.ENTREGADA,
        )
        self.tool.stock = 6
        self.tool.save(update_fields=['stock'])

        self.client.force_authenticate(self.member)
        created = self.client.post(reverse('tool-return-list'), {
            'tool_request': str(delivered_request.id),
            'quantity_returned': 2,
            'condition': ToolConditionChoices.BUEN_ESTADO,
            'observations': 'Devuelta tras hormigonado.',
        }, format='json')
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(created.data['return_number_display'], '#001')
        self.assertEqual(created.data['status'], ToolReturnStatusChoices.PENDIENTE_REVISION)

        detail_url = reverse('tool-return-detail', kwargs={'pk': created.data['id']})
        forbidden = self.client.patch(
            detail_url, {'status': ToolReturnStatusChoices.RECEPCIONADA}, format='json'
        )
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.admin)
        received = self.client.patch(
            detail_url, {'status': ToolReturnStatusChoices.RECEPCIONADA}, format='json'
        )
        self.assertEqual(received.status_code, status.HTTP_200_OK)

        self.tool.refresh_from_db()
        self.assertEqual(self.tool.stock, 8)
        self.assertTrue(AuditLog.objects.filter(
            entity_name='ToolReturn',
            action=AuditActionChoices.UPDATE,
            entity_id=str(created.data['id']),
        ).exists())

    def test_rejecting_approved_request_restores_stock(self):
        self.client.force_authenticate(self.member)
        created = self.client.post(
            reverse('tool-request-list'),
            self._request_payload(quantity=3),
            format='json',
        )
        detail_url = reverse('tool-request-detail', kwargs={'pk': created.data['id']})

        self.client.force_authenticate(self.admin)
        self.assertEqual(
            self.client.patch(
                detail_url, {'status': ToolRequestStatusChoices.APROBADA}, format='json'
            ).status_code,
            status.HTTP_200_OK,
        )
        self.tool.refresh_from_db()
        self.assertEqual(self.tool.stock, 7)

        rejected = self.client.patch(
            detail_url, {'status': ToolRequestStatusChoices.RECHAZADA}, format='json'
        )
        self.assertEqual(rejected.status_code, status.HTTP_200_OK)
        self.tool.refresh_from_db()
        self.assertEqual(self.tool.stock, 10)

    def test_member_can_cancel_only_own_pending_request(self):
        pending = ToolRequest.objects.create(
            tool=self.tool,
            task=self.task,
            requested_by=self.member,
            quantity=1,
            status=ToolRequestStatusChoices.PENDIENTE,
        )
        delivered = ToolRequest.objects.create(
            tool=self.tool,
            task=self.task,
            requested_by=self.member,
            quantity=1,
            status=ToolRequestStatusChoices.ENTREGADA,
        )

        self.client.force_authenticate(self.member)
        self.assertEqual(
            self.client.delete(
                reverse('tool-request-detail', kwargs={'pk': pending.id})
            ).status_code,
            status.HTTP_204_NO_CONTENT,
        )
        self.assertEqual(
            self.client.delete(
                reverse('tool-request-detail', kwargs={'pk': delivered.id})
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )


class ToolSeedCommandTestCase(TestCase):
    """Verifies the proposed demo seed before it is ever run on EC2."""

    def test_seed_is_idempotent_and_creates_expected_demo_data(self):
        call_command('seed_tool_module', verbosity=0)
        call_command('seed_tool_module', verbosity=0)

        self.assertEqual(Tool.objects.count(), 6)
        self.assertEqual(ToolRequest.objects.count(), 2)
        self.assertEqual(ToolReturn.objects.count(), 1)

        tool_return = ToolReturn.objects.first()
        self.assertEqual(f"#{tool_return.return_number:03d}", '#001')
        self.assertEqual(tool_return.status, ToolReturnStatusChoices.PENDIENTE_REVISION)

        delivered = ToolRequest.objects.get(
            notes='DEMO-001: hormigonado de losa piso 3'
        )
        self.assertEqual(delivered.status, ToolRequestStatusChoices.ENTREGADA)
        delivered.tool.refresh_from_db()
        self.assertEqual(delivered.tool.stock, 6)
