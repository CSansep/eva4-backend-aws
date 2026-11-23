"""
Core application configuration.
"""
from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Configuration class for the core domain application."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Core Domain & Task Management'
