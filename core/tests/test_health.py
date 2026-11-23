"""
Tests for Health Check endpoint /api/v1/health/.
"""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class HealthCheckAPITestCase(APITestCase):
    """Tests for lightweight health check endpoint."""

    def test_health_check_returns_200_and_status(self):
        """Health check must return 200 OK and database status without requiring authentication."""
        url = reverse('health-check')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'ok')
        self.assertEqual(response.data['database'], 'connected')
        self.assertIn('timestamp', response.data)
        self.assertEqual(response.data['service'], 'eva4-backend')
