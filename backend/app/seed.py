"""Activo iniciales: crypto (CoinGecko), acciones y commodities (Yahoo)."""

from app.extensions import db
from app.models import Asset, AssetType

DEFAULT_ASSETS = [
    # symbol, name, type, external_id, provider, news_keywords
    ("BTC", "Bitcoin", AssetType.crypto, "bitcoin", "coingecko", "bitcoin OR BTC"),
    ("ETH", "Ethereum", AssetType.crypto, "ethereum", "coingecko", "ethereum OR ETH"),
    ("SOL", "Solana", AssetType.crypto, "solana", "coingecko", "solana OR SOL"),
    ("AAPL", "Apple Inc.", AssetType.stock, "AAPL", "yahoo", "Apple stock AAPL"),
    ("MSFT", "Microsoft", AssetType.stock, "MSFT", "yahoo", "Microsoft MSFT"),
    ("GLD", "SPDR Gold Shares", AssetType.commodity, "GLD", "yahoo", "gold price OR GLD"),
    ("CL=F", "Crude Oil WTI", AssetType.commodity, "CL=F", "yahoo", "WTI crude oil"),
    ("NG=F", "Natural Gas", AssetType.commodity, "NG=F", "yahoo", "natural gas price"),
]


def seed_assets_if_empty() -> int:
    if Asset.query.count() > 0:
        return 0
    n = 0
    for symbol, name, atype, ext_id, provider, kw in DEFAULT_ASSETS:
        a = Asset(
            symbol=symbol,
            name=name,
            asset_type=atype,
            external_id=ext_id,
            provider=provider,
            news_keywords=kw,
        )
        db.session.add(a)
        n += 1
    db.session.commit()
    return n
