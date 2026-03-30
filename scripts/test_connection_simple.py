#!/usr/bin/env python3
"""
Simple test to check database connection with different URLs.
"""

import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_connection_with_url(url, description):
    """Test connection with specific URL."""
    print(f"\n🔍 Testing {description}...")
    print(f"URL: {url}")
    
    try:
        conn = psycopg2.connect(url)
        cursor = conn.cursor()
        
        # Test basic query
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"✅ Connected! PostgreSQL: {version[0][:50]}...")
        
        # Check tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """)
        
        tables = cursor.fetchall()
        print(f"📋 Found {len(tables)} tables:")
        for table in tables:
            print(f"   - {table[0]}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

def main():
    """Test different connection URLs."""
    print("🚀 Sentinel Trading Database Connection Test")
    print("=" * 60)
    
    # Different URLs to test
    urls_to_test = [
        (
            "postgresql://postgres:e%40s%5Eh%26270P%251iD%26A29JF@db.dqfuuycnzhqatkiwcecf.supabase.co:5432/postgres",
            "Direct Connection (Port 5432)"
        ),
        (
            "postgresql://postgres.e%40s%5Eh%26270P%251iD%26A29JF@db.dqfuuycnzhqatkiwcecf.supabase.co:6543/postgres",
            "Session Pooler (Port 6543)"
        ),
        (
            "postgresql://postgres.e%40s%5Eh%26270P%251iD%26A29JF@pg.dqfuuycnzhqatkiwcecf.supabase.co:5432/postgres",
            "Alternative Host (pg. prefix)"
        ),
        (
            "postgresql://postgres.e%40s%5Eh%26270P%251iD%26A29JF@aws-0-us-east-1.pooler.supabase.com:6543/postgres",
            "AWS Pooler (if available)"
        )
    ]
    
    success_count = 0
    
    for url, description in urls_to_test:
        if test_connection_with_url(url, description):
            success_count += 1
            print(f"✅ SUCCESS: {description}")
            break  # Stop at first successful connection
    
    if success_count > 0:
        print(f"\n🎉 Found working connection!")
        print("Update your .env file with the working URL.")
    else:
        print(f"\n❌ No connection worked. Check:")
        print("1. Database is running in Supabase")
        print("2. Password is correct")
        print("3. Network connectivity")
        print("4. Supabase project settings")

if __name__ == "__main__":
    main()
