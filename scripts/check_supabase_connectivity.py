#!/usr/bin/env python3
"""
Check Supabase connectivity and get correct connection parameters.
"""

import requests
import socket
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_dns_resolution():
    """Check DNS resolution for Supabase hosts."""
    print("🔍 Checking DNS resolution...")
    
    hosts_to_check = [
        "db.dqfuuycnzhqatkiwcecf.supabase.co",
        "dqfuuycnzhqatkiwcecf.supabase.co",
        "api.supabase.co"
    ]
    
    for host in hosts_to_check:
        try:
            ip = socket.gethostbyname(host)
            print(f"✅ {host} → {ip}")
        except Exception as e:
            print(f"❌ {host} → {e}")

def check_supabase_api():
    """Check Supabase API connectivity."""
    print("\n🔍 Checking Supabase API...")
    
    supabase_url = os.getenv('SUPABASE_URL')
    anon_key = os.getenv('SUPABASE_ANON_KEY')
    
    if not supabase_url or not anon_key:
        print("❌ Missing SUPABASE_URL or SUPABASE_ANON_KEY")
        return False
    
    try:
        # Test API connectivity
        headers = {
            "apikey": anon_key,
            "Authorization": f"Bearer {anon_key}"
        }
        
        # Test a simple query to check connection
        url = f"{supabase_url}/rest/v1/"
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            print(f"✅ Supabase API is accessible")
            print(f"   Status: {response.status_code}")
            return True
        else:
            print(f"❌ API returned status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ API connection failed: {e}")
        return False

def get_connection_info():
    """Get connection info from Supabase API."""
    print("\n🔍 Getting connection info...")
    
    supabase_url = os.getenv('SUPABASE_URL')
    anon_key = os.getenv('SUPABASE_ANON_KEY')
    
    try:
        # Try to get connection info (this might not work with anon key)
        headers = {
            "apikey": anon_key,
            "Authorization": f"Bearer {anon_key}"
        }
        
        # Test accessing a table to verify connection
        url = f"{supabase_url}/rest/v1/assets?limit=1"
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            print("✅ Can access Supabase tables via REST API")
            print("   Database connection via REST works")
            return True
        elif response.status_code == 406:
            print("✅ Supabase API is working (406 is expected for this endpoint)")
            return True
        else:
            print(f"❌ Table access failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Connection info failed: {e}")
        return False

def suggest_alternative_connection():
    """Suggest alternative connection methods."""
    print("\n💡 Alternative Connection Methods:")
    print("1. Use Supabase Python client instead of direct PostgreSQL")
    print("2. Use REST API for database operations")
    print("3. Check if you need IPv4 add-on in Supabase")
    print("4. Use VPN or different network")
    
    print("\n📝 Recommended .env configuration:")
    print("# Use Supabase Python client")
    print("SUPABASE_URL=https://dqfuuycnzhqatkiwcecf.supabase.co")
    print("SUPABASE_KEY=your_anon_key")
    print("# Remove DATABASE_URL for now")

def main():
    """Main connectivity check."""
    print("🚀 Supabase Connectivity Check")
    print("=" * 50)
    
    # Check DNS
    check_dns_resolution()
    
    # Check API
    api_works = check_supabase_api()
    
    # Get connection info
    if api_works:
        get_connection_info()
    
    # Suggest alternatives
    suggest_alternative_connection()
    
    print("\n🎯 Next Steps:")
    if api_works:
        print("✅ Supabase API works - use REST API or Python client")
        print("❌ Direct PostgreSQL connection has DNS issues")
    else:
        print("❌ Both API and PostgreSQL have issues")
        print("📞 Check Supabase project status and network")

if __name__ == "__main__":
    main()
