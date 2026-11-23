"""
Tests for Authentication, User Registration, and JWT token lifecycle.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class AuthenticationAPITestCase(APITestCase):
    """Tests for /api/v1/auth/ endpoints."""

    def setUp(self):
        self.register_url = reverse('auth-register')
        self.token_url = reverse('token_obtain_pair')
        self.refresh_url = reverse('token_refresh')
        self.me_url = reverse('auth-me')

        self.user = User.objects.create_user(
            email='alice@example.com',
            username='alice',
            password='SecurePassword123!'
        )

    def test_successful_registration(self):
        """Public registration should return 201 Created and NOT return password."""
        payload = {
            'email': 'bob@example.com',
            'username': 'bobsmith',
            'password': 'StrongBobPassword2026!',
            'role': 'MEMBER'
        }
        response = self.client.post(self.register_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['email'], 'bob@example.com')
        self.assertEqual(response.data['username'], 'bobsmith')
        self.assertNotIn('password', response.data)

        # Verify user exists in database
        self.assertTrue(User.objects.filter(email='bob@example.com').exists())

    def test_registration_weak_password_rejected(self):
        """Weak or short passwords must return 400 Bad Request."""
        payload = {
            'email': 'weak@example.com',
            'username': 'weakuser',
            'password': '123'  # Too short
        }
        response = self.client.post(self.register_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)

    def test_registration_duplicate_email_rejected(self):
        """Registering with an already existing email must return 400."""
        payload = {
            'email': 'alice@example.com',
            'username': 'alice2',
            'password': 'AnotherPassword123!'
        }
        response = self.client.post(self.register_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_jwt_token_obtain_and_refresh(self):
        """Login with valid email and password must return access and refresh JWT tokens."""
        login_payload = {
            'email': 'alice@example.com',
            'password': 'SecurePassword123!'
        }
        response = self.client.post(self.token_url, login_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

        refresh_token = response.data['refresh']

        # Test token refresh
        refresh_payload = {'refresh': refresh_token}
        refresh_response = self.client.post(self.refresh_url, refresh_payload, format='json')
        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertIn('access', refresh_response.data)

    def test_current_user_profile_authenticated(self):
        """Endpoint /api/v1/auth/me/ must return authenticated user profile."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], self.user.email)
        self.assertEqual(response.data['username'], self.user.username)
        self.assertNotIn('password', response.data)

    def test_current_user_profile_unauthenticated_returns_401(self):
        """Unauthenticated access to /api/v1/auth/me/ must return 401 Unauthorized."""
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
