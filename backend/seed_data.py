#!/usr/bin/env python3
"""
Script to seed initial data
"""
from app import create_app
from app.seed import seed_assets_if_empty

app = create_app()

with app.app_context():
    seed_assets_if_empty()
    print("Assets seeded successfully")
