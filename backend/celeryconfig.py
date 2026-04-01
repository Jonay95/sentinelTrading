"""
Configuración de Celery Beat para ejecutar tareas periódicas
"""

from celery.schedules import crontab
from app.celery import celery

# Tareas periódicas
@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """
    Configura tareas periódicas cuando Celery se inicia
    """
    
    # Ejecutar registro_cita cada 2 minutos
    sender.add_periodic_task(
        # Cada 2 minutos
        crontab(minute='*/2'),
        'app.utils.tasks.registro_cita.registro_cita',
        name='registro_cita_cada_2_minutos',
        options={
            'queue': 'default',
        }
    )
    
    print("✅ Tarea periódica configurada: registro_cita cada 2 minutos")
