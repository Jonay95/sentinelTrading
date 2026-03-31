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
    Crea instancia de Celery conectada a Redis
    """
    broker = os.getenv("CELERY_BROKER_URL")
    backend = os.getenv("CELERY_RESULT_BACKEND")

    celery = Celery(
        "sentinel",
        broker=broker,
        backend=backend,
        include=["app.utils.tasks.registro_cita"],
    )

    # Configuración básica
    celery.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="Europe/Madrid",
        enable_utc=True,
    )

    return celery


# Instancia global
celery = create_celery_app()