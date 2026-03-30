#!/usr/bin/env python3
"""
Script to insert sample data using Supabase client.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import random
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.database.supabase_client import get_supabase_client

def insert_sample_assets():
    """Insert sample trading assets."""
    print("📈 Inserting sample assets...")
    
    assets = [
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
        client = get_supabase_client()
        
        for asset_data in assets:
            asset = {
                'symbol': asset_data[0],
                'name': asset_data[1],
                'asset_type': asset_data[2],
                'sector': asset_data[3],
                'exchange': asset_data[4]
            }
            
            try:
                result = client.create_asset(asset)
                print(f"✅ Inserted {asset_data[0]}")
            except Exception as e:
                if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                    print(f"⚠️  {asset_data[0]} already exists")
                else:
                    print(f"❌ Error inserting {asset_data[0]}: {e}")
        
        print(f"✅ Processed {len(assets)} assets")
        
    except Exception as e:
        print(f"❌ Error inserting assets: {e}")

def insert_sample_market_data():
    """Insert sample market data."""
    print("📊 Inserting sample market data...")
    
    try:
        client = get_supabase_client()
        
        # Get assets
        assets = client.get_assets(limit=3)
        
        # Generate 30 days of sample data
        for asset in assets:
            asset_id = asset['id']
            symbol = asset['symbol']
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
                
                market_data = {
                    'asset_id': asset_id,
                    'timestamp': timestamp.isoformat(),
                    'open_price': open_price,
                    'high_price': high_price,
                    'low_price': low_price,
                    'close_price': close_price,
                    'volume': volume
                }
                
                try:
                    client.create_market_data(market_data)
                except Exception as e:
                    if "duplicate" in str(e).lower():
                        continue  # Skip duplicates
                    else:
                        print(f"❌ Error inserting market data for {symbol}: {e}")
                
                base_price = close_price
        
        print(f"✅ Inserted 30 days of market data for {len(assets)} assets")
        
    except Exception as e:
        print(f"❌ Error inserting market data: {e}")

def insert_sample_portfolio():
    """Insert sample portfolio and positions."""
    print("💼 Inserting sample portfolio...")
    
    try:
        client = get_supabase_client()
        
        # Insert sample portfolio
        portfolio_data = {
            'name': 'Demo Portfolio',
            'description': 'Sample portfolio for testing',
            'user_id': 'demo-user-uuid',
            'total_value': 100000.00,
            'cash_balance': 10000.00
        }
        
        try:
            portfolio = client.create_portfolio(portfolio_data)
            portfolio_id = portfolio.get('id')
            print(f"✅ Created demo portfolio")
            
            # Get assets for positions
            assets = client.get_assets(limit=3)
            
            # Insert sample positions
            positions_data = [
                {
                    'portfolio_id': portfolio_id,
                    'asset_id': assets[0]['id'],
                    'quantity': 100,
                    'entry_price': 150.00,
                    'current_price': 165.00,
                    'position_type': 'LONG',
                    'status': 'OPEN',
                    'entry_date': (datetime.utcnow() - timedelta(days=10)).isoformat(),
                    'unrealized_pnl': (165.00 - 150.00) * 100
                },
                {
                    'portfolio_id': portfolio_id,
                    'asset_id': assets[1]['id'],
                    'quantity': 50,
                    'entry_price': 250.00,
                    'current_price': 260.00,
                    'position_type': 'LONG',
                    'status': 'OPEN',
                    'entry_date': (datetime.utcnow() - timedelta(days=10)).isoformat(),
                    'unrealized_pnl': (260.00 - 250.00) * 50
                },
                {
                    'portfolio_id': portfolio_id,
                    'asset_id': assets[2]['id'],
                    'quantity': 30,
                    'entry_price': 2000.00,
                    'current_price': 1950.00,
                    'position_type': 'LONG',
                    'status': 'OPEN',
                    'entry_date': (datetime.utcnow() - timedelta(days=10)).isoformat(),
                    'unrealized_pnl': (1950.00 - 2000.00) * 30
                }
            ]
            
            for pos_data in positions_data:
                try:
                    client.create_position(pos_data)
                    print(f"✅ Created position for {pos_data['asset_id']}")
                except Exception as e:
                    print(f"❌ Error creating position: {e}")
            
        except Exception as e:
            print(f"❌ Error creating portfolio: {e}")
        
    except Exception as e:
        print(f"❌ Error inserting portfolio: {e}")

def insert_sample_predictions():
    """Insert sample predictions."""
    print("🤖 Inserting sample predictions...")
    
    try:
        client = get_supabase_client()
        
        # Get assets
        assets = client.get_assets(limit=3)
        
        # Generate sample predictions
        for asset in assets:
            asset_id = asset['id']
            symbol = asset['symbol']
            
            for i in range(10):
                prediction_timestamp = datetime.utcnow() - timedelta(hours=i)
                
                # Generate realistic prediction
                current_price = random.uniform(100, 500)
                predicted_price = current_price * (1 + random.uniform(-0.05, 0.05))
                confidence = random.uniform(0.6, 0.95)
                
                prediction_data = {
                    'asset_id': asset_id,
                    'timestamp': (prediction_timestamp + timedelta(days=1)).isoformat(),
                    'prediction_timestamp': prediction_timestamp.isoformat(),
                    'predicted_price': predicted_price,
                    'confidence_score': confidence,
                    'model_version': 'v1.0',
                    'prediction_type': 'PRICE',
                    'time_horizon': '1D'
                }
                
                try:
                    client.create_prediction(prediction_data)
                except Exception as e:
                    if "duplicate" in str(e).lower():
                        continue
                    else:
                        print(f"❌ Error inserting prediction for {symbol}: {e}")
        
        print(f"✅ Inserted sample predictions for {len(assets)} assets")
        
    except Exception as e:
        print(f"❌ Error inserting predictions: {e}")

def main():
    """Main function to insert all sample data."""
    print("🚀 Inserting Sample Data into Sentinel Trading Database")
    print("=" * 60)
    
    try:
        # Insert sample data
        insert_sample_assets()
        insert_sample_market_data()
        insert_sample_portfolio()
        insert_sample_predictions()
        
        print("\n🎉 All sample data inserted successfully!")
        print("📊 Your database is now ready for testing!")
        
        # Show final stats
        client = get_supabase_client()
        stats = client.get_database_stats()
        print("\n📈 Final Database Stats:")
        for table, count in stats.items():
            print(f"   {table}: {count}")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error inserting sample data: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
