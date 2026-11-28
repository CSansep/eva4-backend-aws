"""
Idempotent demo seed for the Tool Inventory module.

Run only after explicit approval:
    python manage.py seed_tool_module

Creates 6 real construction tools, 2 tool requests (one ENTREGADA) and one
pending numbered return (#001) linked to the delivered request. Stock is
decremented for the delivered demo request so the UI starts consistent.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F

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

DEMO_TOOLS = [
    {
        'name': 'Rotomartillo SDS Plus',
        'description': 'Perforación en hormigón armado hasta 28mm, 850W, 3.2J.',
        'stock': 8,
    },
    {
        'name': 'Esmeril Angular 7"',
        'description': 'Corte y desbaste de acero, disco 180mm, 1200W, 11.000 RPM.',
        'stock': 6,
    },
    {
        'name': 'Vibrador de Inmersión para Hormigón',
        'description': 'Compactación de hormigón en losas y columnas, 1.5kW, manguera 6m.',
        'stock': 4,
    },
    {
        'name': 'Nivel Láser Autonivelante',
        'description': 'Nivelación 360°, alcance 30m, clase 2, trípode incluido.',
        'stock': 3,
    },
    {
        'name': 'Placa Compactadora',
        'description': 'Compactado de suelo y pavimento, 5.5HP, 170 kg, 3.600 vpm.',
        'stock': 2,
    },
    {
        'name': 'Arnés de Seguridad + Línea de Vida',
        'description': 'Protección anticaída EN 361/355, 2 anclajes y línea de 10m.',
        'stock': 12,
    },
]


class Command(BaseCommand):
    help = "Carga datos demo idempotentes del módulo de herramientas, pedidos y retornos."

    @staticmethod
    def _resolve_user(role: str, email: str, username: str):
        """Reuse an existing role holder; otherwise create a safe demo account."""
        user = User.objects.filter(role=role).order_by('created_at').first()
        if user:
            return user, False

        user = User.objects.create_user(email=email, username=username, role=role)
        user.set_unusable_password()
        user.save(update_fields=['password'])
        return user, True

    def handle(self, *args, **options):
        with transaction.atomic():
            admin, admin_created = self._resolve_user(
                RoleChoices.ADMIN,
                'inventario.admin@buildcorp.cl',
                'inventario_admin'
            )
            member, member_created = self._resolve_user(
                RoleChoices.MEMBER,
                'inventario.member@buildcorp.cl',
                'inventario_member'
            )

            if admin_created or member_created:
                self.stdout.write(self.style.WARNING(
                    'Se crearon usuarios demo sin contraseña utilizable; '
                    'resetea su password antes de iniciar sesión con ellos.'
                ))

            project, _ = Project.objects.get_or_create(
                name='Obra Demo Costanera Sur',
                defaults={
                    'owner': admin,
                    'description': 'Obra de ejemplo para el módulo de inventario.'
                },
            )
            task, _ = Task.objects.get_or_create(
                title='Hormigonado losa piso 3',
                project=project,
                defaults={
                    'description': 'Frente de obra usado por los pedidos demo.',
                    'priority': 'HIGH',
                },
            )

            tools = {}
            for item in DEMO_TOOLS:
                tool, _ = Tool.objects.get_or_create(
                    name=item['name'],
                    defaults={
                        'description': item['description'],
                        'stock': item['stock'],
                    },
                )
                tools[item['name']] = tool

            delivered, delivered_created = ToolRequest.objects.get_or_create(
                requested_by=member,
                tool=tools['Rotomartillo SDS Plus'],
                task=task,
                notes='DEMO-001: hormigonado de losa piso 3',
                defaults={
                    'quantity': 2,
                    'priority': 'HIGH',
                    'status': ToolRequestStatusChoices.ENTREGADA,
                },
            )
            if delivered_created:
                Tool.objects.filter(pk=delivered.tool_id).update(
                    stock=F('stock') - delivered.quantity
                )

            ToolRequest.objects.get_or_create(
                requested_by=member,
                tool=tools['Nivel Láser Autonivelante'],
                task=task,
                notes='DEMO-002: replanteo de ejes',
                defaults={
                    'quantity': 1,
                    'priority': 'MEDIUM',
                    'status': ToolRequestStatusChoices.PENDIENTE,
                },
            )

            tool_return, return_created = ToolReturn.objects.get_or_create(
                tool_request=delivered,
                observations='DEMO-RETURN-001: devolución inicial pendiente de bodega.',
                defaults={
                    'returned_by': member,
                    'quantity_returned': 1,
                    'condition': ToolConditionChoices.BUEN_ESTADO,
                    'status': ToolReturnStatusChoices.PENDIENTE_REVISION,
                },
            )

        self.stdout.write(self.style.SUCCESS(
            f"Seed listo: {len(tools)} herramientas, 2 pedidos y retorno "
            f"#{tool_return.return_number:03d} ({'creado' if return_created else 'existente'})."
        ))
