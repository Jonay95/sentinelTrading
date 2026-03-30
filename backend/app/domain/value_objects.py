"""
Objetivos de valor inmutables y enumeraciones del dominio.

Separar tipos de negocio de los modelos de persistencia cumple el principio
de independencia de frameworks (Clean Architecture / hexagonal).
"""

from __future__ import annotations

from enum import Enum


class AssetType(str, Enum):
    """Clase de instrumento negociable."""

    crypto = "crypto"
    stock = "stock"
    commodity = "commodity"


class Signal(str, Enum):
    """Señal discreta de la estrategia (no es una orden real de mercado)."""

    buy = "buy"
    sell = "sell"
    hold = "hold"
