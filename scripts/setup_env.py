#!/usr/bin/env python3
"""
Script to setup .env file for Sentinel Trading with Supabase.
"""

import os
from pathlib import Path

def setup_env_file():
    """Setup .env file with Supabase credentials."""
    
    print("🔧 Sentinel Trading Environment Setup")
    print("=" * 50)
    
    # Supabase credentials (known from user)
    database_url = "postgresql://postgres:e@s^h&270P%1iD&A29JF@db.dqfuuycnzhqatkiwcecf.supabase.co:5432/postgres"
    supabase_url = "https://dqfuuycnzhqatkiwcecf.supabase.co"
    
    # Get API keys from user
    print("\n📋 Please provide your Supabase API keys:")
    print("(Go to your Supabase project → Settings → API)")
    
    anon_key = input("Anon public key: ").strip()
    service_role_key = input("Service role key: ").strip()
    
    if not anon_key or not service_role_key:
        print("❌ Both API keys are required!")
        return False
    
    # Generate random secrets
    import secrets
    secret_key = secrets.token_urlsafe(32)
    jwt_secret_key = secrets.token_urlsafe(32)
    
    # Create .env content
    env_content = f"""# ============================================
# Supabase Configuration
# ============================================
DATABASE_URL={database_url}
SUPABASE_URL={supabase_url}
SUPABASE_ANON_KEY={anon_key}
SUPABASE_SERVICE_ROLE_KEY={service_role_key}

# ============================================
# Security
# ============================================
SECRET_KEY={secret_key}
JWT_SECRET_KEY={jwt_secret_key}

# ============================================
# Flask Configuration
# ============================================
FLASK_ENV=development
SQL_DEBUG=false

# ============================================
# API Keys (Optional - leave blank if not using)
# ============================================
ALPHA_VANTAGE_API_KEY=
NEWS_API_KEY=
TWITTER_API_KEY=
TWITTER_API_SECRET=
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=

# ============================================
# External Services (Optional)
# ============================================
COINGECKO_API_KEY=
FINNHUB_API_KEY=
POLYGON_API_KEY=

# ============================================
# Optional Services
# ============================================
# REDIS_URL=redis://localhost:6379
# MLFLOW_TRACKING_URI=http://localhost:5000
"""
    
    # Write .env file
    env_path = Path(__file__).parent.parent / ".env"
    
    try:
        with open(env_path, 'w') as f:
            f.write(env_content)
        
        print(f"\n✅ .env file created at: {env_path}")
        print("🔐 Environment variables configured successfully!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating .env file: {e}")
        return False

if __name__ == "__main__":
    success = setup_env_file()
    
    if success:
        print("\n🎯 Next steps:")
        print("1. Run: cd scripts && python test_database.py")
        print("2. Run: cd scripts && python insert_sample_data.py")
        print("3. Deploy to Render when ready")
    else:
        print("\n❌ Setup failed. Please try again.")
