"""
Modelos ORM (SQLAlchemy) — lado “adaptador” de persistencia.

El dominio no importa este módulo; los repositorios mapean ORM ↔ DTOs.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.value_objects import AssetType, Signal
from app.extensions import db


class Asset(db.Model):
    __tablename__ = "assets"

    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(32), unique=True, nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False)
    asset_type = db.Column(db.Enum(AssetType, native_enum=False, length=32), nullable=False)
    external_id = db.Column(db.String(64), nullable=True)
    provider = db.Column(db.String(32), nullable=False, default="yahoo")
    news_keywords = db.Column(db.String(256), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    quotes = db.relationship("Quote", backref="asset", lazy="dynamic")
    predictions = db.relationship("Prediction", backref="asset", lazy="dynamic")


class Quote(db.Model):
    __tablename__ = "quotes"

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("assets.id"), nullable=False, index=True)
    ts = db.Column(db.DateTime, nullable=False, index=True)
    open = db.Column(db.Float, nullable=True)
    high = db.Column(db.Float, nullable=True)
    low = db.Column(db.Float, nullable=True)
    close = db.Column(db.Float, nullable=False)
    volume = db.Column(db.Float, nullable=True)

    __table_args__ = (db.UniqueConstraint("asset_id", "ts", name="uq_quote_asset_ts"),)


class Prediction(db.Model):
    __tablename__ = "predictions"

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("assets.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    horizon_days = db.Column(db.Integer, nullable=False, default=1)
    target_date = db.Column(db.DateTime, nullable=False, index=True)
    base_price = db.Column(db.Float, nullable=False)
    predicted_value = db.Column(db.Float, nullable=False)
    signal = db.Column(db.Enum(Signal, native_enum=False, length=16), nullable=False)
    confidence = db.Column(db.Float, nullable=False)
    model_version = db.Column(db.String(64), nullable=False)
    features_json = db.Column(db.JSON, nullable=True)

    outcome = db.relationship(
        "PredictionOutcome",
        backref="prediction",
        uselist=False,
        cascade="all, delete-orphan",
    )


class PredictionOutcome(db.Model):
    __tablename__ = "prediction_outcomes"

    id = db.Column(db.Integer, primary_key=True)
    prediction_id = db.Column(
        db.Integer, db.ForeignKey("predictions.id"), unique=True, nullable=False
    )
    actual_value = db.Column(db.Float, nullable=False)
    evaluated_at = db.Column(db.DateTime, default=datetime.utcnow)
    metrics_json = db.Column(db.JSON, nullable=True)


news_asset = db.Table(
    "news_asset",
    db.Column("news_item_id", db.Integer, db.ForeignKey("news_items.id"), primary_key=True),
    db.Column("asset_id", db.Integer, db.ForeignKey("assets.id"), primary_key=True),
)


class NewsItem(db.Model):
    __tablename__ = "news_items"

    id = db.Column(db.Integer, primary_key=True)
    published_at = db.Column(db.DateTime, nullable=False, index=True)
    title = db.Column(db.String(512), nullable=False)
    url = db.Column(db.String(1024), nullable=True)
    source = db.Column(db.String(128), nullable=True)
    snippet = db.Column(db.Text, nullable=True)
    fetched_at = db.Column(db.DateTime, default=datetime.utcnow)

    sentiment = db.relationship(
        "NewsSentiment",
        backref="news_item",
        uselist=False,
        cascade="all, delete-orphan",
    )
    assets = db.relationship("Asset", secondary=news_asset, backref="news_items")


class NewsSentiment(db.Model):
    __tablename__ = "news_sentiment"

    id = db.Column(db.Integer, primary_key=True)
    news_item_id = db.Column(
        db.Integer, db.ForeignKey("news_items.id"), unique=True, nullable=False
    )
    compound_score = db.Column(db.Float, nullable=False)
