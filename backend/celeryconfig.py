"""
Configuración de Celery Beat para tareas periódicas

Ejecuta el bot de registro de citas cada 10 minutos (estrategia conservadora)
"""

from celery.schedules import crontab

# Configuración de tareas periódicas
beat_schedule = {
    'registro-cita-conservador': {
        'task': 'app.utils.tasks.registro_cita.registro_cita',
        'schedule': 600.0,  # Cada 600 segundos (10 minutos) - estrategia conservadora
        'options': {
            'queue': 'default',
            'priority': 5,
        }
    },
}

# Configuración adicional
timezone = 'Europe/Madrid'
enable_utc = True
