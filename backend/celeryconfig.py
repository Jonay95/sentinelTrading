"""
Configuración de Celery Beat para tareas periódicas
"""

from celery.schedules import crontab

# Configuración de tareas periódicas
beat_schedule = {}

# Configuración adicional
timezone = 'Europe/Madrid'
enable_utc = True
