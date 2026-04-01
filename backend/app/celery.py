# backend/app/celery.py
"""
Celery configuration for the project.

- Inicializa Celery con Flask context
- Usa variables de entorno (Redis)
- Permite ejecutar tareas como registro_cita
"""

from celery import Celery
import os


def create_celery_app():
    """
    Crea instancia de Celery conectada a Redis con SSL
    """
    broker = os.getenv("CELERY_BROKER_URL")
    backend = os.getenv("CELERY_RESULT_BACKEND")
    use_ssl = os.getenv("CELERY_BROKER_USE_SSL", "true").lower() in ("1", "true", "yes")

    celery = Celery(
        "sentinel",
        broker=broker,
        backend=backend,
        include=["app.utils.tasks.registro_cita"],
    )

    # Configuración básica con SSL
    celery.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="Europe/Madrid",
        enable_utc=True,
        broker_use_ssl=use_ssl,
        redis_backend_use_ssl=use_ssl,
        broker_connection_retry_on_startup=True,
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        # Configuración SSL específica para rediss://
        broker_transport_options={
            'ssl_cert_reqs': None,
            'ssl_check_hostname': False,
        },
        redis_backend_transport_options={
            'ssl_cert_reqs': None,
            'ssl_check_hostname': False,
        },
    )

    return celery


# Instancia global
celery = create_celery_app()