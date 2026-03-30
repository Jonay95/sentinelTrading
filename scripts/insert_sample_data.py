#!/usr/bin/env python3
"""
Script to insert sample data into Supabase database.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import random

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.database.connection import db
import psycopg2
from psycopg2.extras import RealDictCursor

def insert_sample_assets():
    """Insert sample trading assets."""
    print("📈 Inserting sample assets...")
    
    assets = [
        ('AAPL', 'Apple Inc.', 'STOCK', 'Technology', 'NASDAQ'),
        ('MSFT', 'Microsoft Corporation', 'STOCK', 'Technology', 'NASDAQ'),
        ('GOOGL', 'Alphabet Inc.', 'STOCK', 'Technology', 'NASDAQ'),
        ('AMZN', 'Amazon.com Inc.', 'STOCK', 'Consumer Discretionary', 'NASDAQ'),
        ('TSLA', 'Tesla Inc.', 'STOCK', 'Automotive', 'NASDAQ'),
        ('NVDA', 'NVIDIA Corporation', 'STOCK', 'Technology', 'NASDAQ'),
        ('META', 'Meta Platforms Inc.', 'STOCK', 'Technology', 'NASDAQ'),
        ('BTC', 'Bitcoin', 'CRYPTO', 'Cryptocurrency', 'Binance'),
        ('ETH', 'Ethereum', 'CRYPTO', 'Cryptocurrency', 'Binance'),
        ('SPY', 'SPDR S&P 500 ETF', 'STOCK', 'ETF', 'NYSE')
    ]
    
    try:
        database_url = os.getenv('DATABASE_URL')
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        for asset in assets:
            cursor.execute("""
                INSERT INTO assets (symbol, name, asset_type, sector, exchange)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (symbol) DO NOTHING
            """, asset)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"✅ Inserted {len(assets)} sample assets")
        
    except Exception as e:
        print(f"❌ Error inserting assets: {e}")

def insert_sample_market_data():
    """Insert sample market data."""
    print("📊 Inserting sample market data...")
    
    try:
        database_url = os.getenv('DATABASE_URL')
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Get asset IDs
        cursor.execute("SELECT id, symbol FROM assets WHERE symbol IN ('AAPL', 'MSFT', 'GOOGL')")
        assets = cursor.fetchall()
        
        # Generate 30 days of sample data
        for asset_id, symbol in assets:
            base_price = random.uniform(100, 500)
            
            for i in range(30):
                timestamp = datetime.utcnow() - timedelta(days=i)
                
                # Generate realistic OHLCV data
                price_change = random.uniform(-0.05, 0.05)
                open_price = base_price * (1 + price_change)
                close_price = open_price * (1 + random.uniform(-0.03, 0.03))
                high_price = max(open_price, close_price) * (1 + random.uniform(0, 0.02))
                low_price = min(open_price, close_price) * (1 - random.uniform(0, 0.02))
                volume = random.randint(1000000, 10000000)
                
                cursor.execute("""
                    INSERT INTO market_data 
                    (asset_id, timestamp, open_price, high_price, low_price, close_price, volume)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (asset_id, timestamp) DO NOTHING
                """, (asset_id, timestamp, open_price, high_price, low_price, close_price, volume))
                
                base_price = close_price
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"✅ Inserted 30 days of market data for {len(assets)} assets")
        
    except Exception as e:
        print(f"❌ Error inserting market data: {e}")

def insert_sample_portfolio():
    """Insert sample portfolio and positions."""
    print("💼 Inserting sample portfolio...")
    
    try:
        database_url = os.getenv('DATABASE_URL')
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Insert sample portfolio
        cursor.execute("""
            INSERT INTO portfolios (name, description, user_id, total_value, cash_balance)
            VALUES ('Demo Portfolio', 'Sample portfolio for testing', 'demo_user', 100000.00, 10000.00)
            ON CONFLICT DO NOTHING
            RETURNING id
        """)
        
        result = cursor.fetchone()
        portfolio_id = result[0] if result else None
        
        if portfolio_id:
            # Get asset IDs for positions
            cursor.execute("SELECT id, symbol FROM assets WHERE symbol IN ('AAPL', 'MSFT', 'GOOGL')")
            assets = cursor.fetchall()
            
            # Insert sample positions
            positions = [
                (portfolio_id, assets[0][0], 100, 150.00, 165.00, 'LONG', 'OPEN'),
                (portfolio_id, assets[1][0], 50, 250.00, 260.00, 'LONG', 'OPEN'),
                (portfolio_id, assets[2][0], 30, 2000.00, 1950.00, 'LONG', 'OPEN')
            ]
            
            for pos in positions:
                unrealized_pnl = (pos[4] - pos[3]) * pos[2]
                cursor.execute("""
                    INSERT INTO positions 
                    (portfolio_id, asset_id, quantity, entry_price, current_price, position_type, status, entry_date, unrealized_pnl)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (*pos, datetime.utcnow() - timedelta(days=10), unrealized_pnl))
            
            # Update portfolio total value
            cursor.execute("""
                UPDATE portfolios 
                SET total_value = (
                    SELECT SUM(quantity * current_price) 
                    FROM positions 
                    WHERE portfolio_id = %s AND status = 'OPEN'
                ) + cash_balance
                WHERE id = %s
            """, (portfolio_id, portfolio_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Inserted sample portfolio and positions")
        
    except Exception as e:
        print(f"❌ Error inserting portfolio: {e}")

def insert_sample_predictions():
    """Insert sample predictions."""
    print("🤖 Inserting sample predictions...")
    
    try:
        database_url = os.getenv('DATABASE_URL')
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Get asset IDs
        cursor.execute("SELECT id, symbol FROM assets WHERE symbol IN ('AAPL', 'MSFT', 'GOOGL')")
        assets = cursor.fetchall()
        
        # Generate sample predictions
        for asset_id, symbol in assets:
            for i in range(10):
                prediction_timestamp = datetime.utcnow() - timedelta(hours=i)
                
                # Generate realistic prediction
                current_price = random.uniform(100, 500)
                predicted_price = current_price * (1 + random.uniform(-0.05, 0.05))
                confidence = random.uniform(0.6, 0.95)
                
                cursor.execute("""
                    INSERT INTO predictions 
                    (asset_id, timestamp, prediction_timestamp, predicted_price, confidence_score, 
                     model_version, prediction_type, time_horizon)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (asset_id, prediction_timestamp + timedelta(days=1), prediction_timestamp, 
                      predicted_price, confidence, 'v1.0', 'PRICE', '1D'))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"✅ Inserted sample predictions for {len(assets)} assets")
        
    except Exception as e:
        print(f"❌ Error inserting predictions: {e}")

def insert_sample_news():
    """Insert sample news articles."""
    print("📰 Inserting sample news...")
    
    try:
        database_url = os.getenv('DATABASE_URL')
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        news_articles = [
            ('Apple announces new iPhone features', 'Apple Inc. revealed exciting new features for the upcoming iPhone model...', 'TechNews', '2024-01-15 10:30:00', 0.7, 'POSITIVE', ['apple', 'iphone', 'technology']),
            ('Microsoft earnings beat expectations', 'Microsoft Corporation reported better than expected quarterly earnings...', 'FinancialTimes', '2024-01-14 15:45:00', 0.8, 'POSITIVE', ['microsoft', 'earnings', 'technology']),
            ('Tesla faces production challenges', 'Tesla Inc. is experiencing some production delays at its factories...', 'AutoNews', '2024-01-13 09:15:00', -0.3, 'NEGATIVE', ['tesla', 'production', 'automotive']),
            ('Fed signals potential rate pause', 'Federal Reserve officials indicated they may pause interest rate hikes...', 'Reuters', '2024-01-12 14:20:00', 0.1, 'NEUTRAL', ['fed', 'interest rates', 'economy']),
            ('Google AI advances impress investors', 'Alphabet\'s Google division announced significant advances in artificial intelligence...', 'TechCrunch', '2024-01-11 11:00:00', 0.6, 'POSITIVE', ['google', 'ai', 'technology'])
        ]
        
        for news in news_articles:
            cursor.execute("""
                INSERT INTO news_articles 
                (title, content, source, published_at, sentiment_score, sentiment_label, keywords)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, news)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"✅ Inserted {len(news_articles)} sample news articles")
        
    except Exception as e:
        print(f"❌ Error inserting news: {e}")

def main():
    """Main function to insert all sample data."""
    print("🚀 Inserting Sample Data into Sentinel Trading Database")
    print("=" * 60)
    
    # Check environment
    if not os.getenv('DATABASE_URL'):
        print("❌ DATABASE_URL not set!")
        return 1
    
    try:
        # Insert sample data
        insert_sample_assets()
        insert_sample_market_data()
        insert_sample_portfolio()
        insert_sample_predictions()
        insert_sample_news()
        
        print("\n🎉 All sample data inserted successfully!")
        print("📊 Your database is now ready for testing!")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error inserting sample data: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
