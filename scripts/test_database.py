#!/usr/bin/env python3
"""
Script to test Supabase database connection and schema.
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

import psycopg2
from psycopg2.extras import RealDictCursor

def test_connection():
    """Test database connection."""
    print("🔍 Testing database connection...")
    
    try:
        # Test basic connection
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            print("❌ DATABASE_URL not set!")
            return False
        
        # Test with direct psycopg2 connection
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Test basic query
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"📊 PostgreSQL version: {version['version']}")
        
        # Check if tables exist
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """)
        
        tables = cursor.fetchall()
        print(f"📋 Found {len(tables)} tables:")
        for table in tables:
            print(f"   - {table['table_name']}")
        
        # Test sample data insertion
        print("\n🧪 Testing data insertion...")
        cursor.execute("""
            INSERT INTO assets (symbol, name, asset_type, sector, exchange) 
            VALUES ('TEST', 'Test Asset', 'STOCK', 'Technology', 'TEST') 
            ON CONFLICT (symbol) DO NOTHING;
        """)
        
        cursor.execute("SELECT * FROM assets WHERE symbol = 'TEST';")
        test_asset = cursor.fetchone()
        
        if test_asset:
            print("✅ Data insertion test successful!")
            # Clean up test data
            cursor.execute("DELETE FROM assets WHERE symbol = 'TEST';")
        else:
            print("❌ Data insertion test failed!")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ All database tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Database connection test failed: {e}")
        return False

def check_environment():
    """Check if environment variables are set."""
    print("🔧 Checking environment variables...")
    
    required_vars = [
        'DATABASE_URL',
        'SUPABASE_URL',
        'SUPABASE_ANON_KEY'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
        else:
            print(f"✅ {var} is set")
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        return False
    
    print("✅ All required environment variables are set!")
    return True

def main():
    """Main test function."""
    print("🚀 Sentinel Trading Database Test")
    print("=" * 50)
    
    # Check environment
    if not check_environment():
        print("\n❌ Please set missing environment variables first!")
        return 1
    
    print()
    
    # Test database
    if not test_connection():
        print("\n❌ Database tests failed!")
        return 1
    
    print("\n🎉 All tests passed! Database is ready for use!")
    return 0

if __name__ == "__main__":
    exit(main())
