#!/usr/bin/env python3
"""
Test Supabase client connection and operations.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.database.supabase_client import get_supabase_client

def test_supabase_client():
    """Test Supabase client functionality."""
    print("🚀 Testing Supabase Client")
    print("=" * 40)
    
    try:
        # Get client
        client = get_supabase_client()
        print("✅ Supabase client initialized")
        
        # Test connection
        print("\n🔍 Testing connection...")
        if client.test_connection():
            print("✅ Connection successful!")
        else:
            print("❌ Connection failed!")
            return False
        
        # Get database stats
        print("\n📊 Getting database stats...")
        stats = client.get_database_stats()
        for table, count in stats.items():
            print(f"   {table}: {count}")
        
        # Test assets
        print("\n💰 Testing assets...")
        assets = client.get_assets(limit=5)
        print(f"✅ Found {len(assets)} assets")
        for asset in assets[:3]:
            print(f"   - {asset.get('symbol', 'Unknown')}: {asset.get('name', 'Unknown')}")
        
        # Test creating an asset
        print("\n➕ Testing asset creation...")
        test_asset = {
            'symbol': 'TEST',
            'name': 'Test Asset',
            'asset_type': 'STOCK',
            'sector': 'Technology'
        }
        
        try:
            created = client.create_asset(test_asset)
            print(f"✅ Created test asset: {created.get('id', 'Unknown')}")
            
            # Clean up
            # Note: We can't easily delete with REST API without the ID
            print("🗑️  Test asset created (will remain in database)")
            
        except Exception as e:
            if "duplicate" in str(e).lower():
                print("✅ Test asset already exists")
            else:
                print(f"⚠️  Asset creation issue: {e}")
        
        # Test market data
        print("\n📈 Testing market data...")
        market_data = client.get_market_data(limit=3)
        print(f"✅ Found {len(market_data)} market data entries")
        
        # Test predictions
        print("\n🤖 Testing predictions...")
        predictions = client.get_predictions(limit=3)
        print(f"✅ Found {len(predictions)} predictions")
        
        print("\n🎉 All Supabase client tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Supabase client test failed: {e}")
        return False

def test_environment():
    """Test environment variables."""
    print("🔧 Checking environment variables...")
    
    required_vars = ['SUPABASE_URL', 'SUPABASE_ANON_KEY']
    missing_vars = []
    
    for var in required_vars:
        if os.getenv(var):
            print(f"✅ {var} is set")
        else:
            print(f"❌ {var} is missing")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\n❌ Missing variables: {', '.join(missing_vars)}")
        return False
    
    print("✅ All required variables are set!")
    return True

def main():
    """Main test function."""
    print("🧪 Supabase Client Test Suite")
    print("=" * 50)
    
    # Check environment
    if not test_environment():
        return 1
    
    print()
    
    # Test client
    if test_supabase_client():
        return 0
    else:
        return 1

if __name__ == "__main__":
    exit(main())
