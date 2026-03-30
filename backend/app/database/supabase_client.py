"""
Supabase client for database operations using REST API instead of direct PostgreSQL.
"""

import os
import requests
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class SupabaseClient:
    """Supabase client using REST API."""
    
    def __init__(self):
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_ANON_KEY')
        self.service_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY are required")
        
        self.headers = {
            'apikey': self.supabase_key,
            'Authorization': f'Bearer {self.supabase_key}',
            'Content-Type': 'application/json'
        }
    
    def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """Make HTTP request to Supabase."""
        url = f"{self.supabase_url}/rest/v1/{endpoint}"
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=self.headers, params=data)
            elif method == 'POST':
                response = requests.post(url, headers=self.headers, json=data)
            elif method == 'PUT':
                response = requests.put(url, headers=self.headers, json=data)
            elif method == 'DELETE':
                response = requests.delete(url, headers=self.headers, params=data)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            
            if response.text:
                return response.json()
            return {}
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Supabase request failed: {e}")
            raise
    
    def test_connection(self) -> bool:
        """Test connection to Supabase."""
        try:
            # Try to get a single asset to test connection
            result = self._make_request('GET', 'assets', {'limit': 1})
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    def get_assets(self, symbol: str = None, limit: int = 100) -> List[Dict]:
        """Get assets from database."""
        params = {'limit': limit}
        if symbol:
            params['symbol'] = f'eq.{symbol}'
        
        return self._make_request('GET', 'assets', params)
    
    def create_asset(self, asset_data: Dict) -> Dict:
        """Create a new asset."""
        return self._make_request('POST', 'assets', asset_data)
    
    def get_market_data(self, asset_id: str = None, limit: int = 100) -> List[Dict]:
        """Get market data."""
        params = {'limit': limit, 'order': 'timestamp.desc'}
        if asset_id:
            params['asset_id'] = f'eq.{asset_id}'
        
        return self._make_request('GET', 'market_data', params)
    
    def create_market_data(self, data: Dict) -> Dict:
        """Create market data entry."""
        return self._make_request('POST', 'market_data', data)
    
    def get_predictions(self, asset_id: str = None, limit: int = 100) -> List[Dict]:
        """Get predictions."""
        params = {'limit': limit, 'order': 'prediction_timestamp.desc'}
        if asset_id:
            params['asset_id'] = f'eq.{asset_id}'
        
        return self._make_request('GET', 'predictions', params)
    
    def create_prediction(self, prediction_data: Dict) -> Dict:
        """Create a new prediction."""
        return self._make_request('POST', 'predictions', prediction_data)
    
    def get_portfolios(self, user_id: str = None) -> List[Dict]:
        """Get portfolios."""
        params = {}
        if user_id:
            params['user_id'] = f'eq.{user_id}'
        
        return self._make_request('GET', 'portfolios', params)
    
    def create_portfolio(self, portfolio_data: Dict) -> Dict:
        """Create a new portfolio."""
        return self._make_request('POST', 'portfolios', portfolio_data)
    
    def get_positions(self, portfolio_id: str = None) -> List[Dict]:
        """Get positions."""
        params = {}
        if portfolio_id:
            params['portfolio_id'] = f'eq.{portfolio_id}'
        
        return self._make_request('GET', 'positions', params)
    
    def create_position(self, position_data: Dict) -> Dict:
        """Create a new position."""
        return self._make_request('POST', 'positions', position_data)
    
    def get_table_info(self, table_name: str) -> Dict:
        """Get table information."""
        try:
            # Get table structure
            url = f"{self.supabase_url}/rest/v1/{table_name}?limit=1"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                return {'exists': True, 'accessible': True}
            else:
                return {'exists': False, 'accessible': False}
                
        except Exception as e:
            logger.error(f"Table info failed: {e}")
            return {'exists': False, 'accessible': False, 'error': str(e)}
    
    def get_database_stats(self) -> Dict:
        """Get database statistics."""
        stats = {}
        
        tables = ['assets', 'market_data', 'predictions', 'portfolios', 'positions']
        
        for table in tables:
            try:
                result = self._make_request('GET', table, {'select': 'count'})
                if result:
                    stats[table] = len(result)
                else:
                    stats[table] = 0
            except Exception as e:
                stats[table] = f"Error: {e}"
        
        return stats

# Global instance
supabase_client = SupabaseClient()

def get_supabase_client() -> SupabaseClient:
    """Get Supabase client instance."""
    return supabase_client
