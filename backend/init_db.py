#!/usr/bin/env python3
"""
Script to initialize database
"""
from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    db.create_all()
    print("Database tables created successfully")
