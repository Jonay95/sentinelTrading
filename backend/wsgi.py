from app import create_app
from app import models  # noqa: F401 — modelos registrados para Alembic / Flask-Migrate

app = create_app()
