"""
Polymarket API client and market extraction logic
"""

import requests
import json
import re
import time
from typing import List, Dict, Optional

from config import Config
from models import PriceData, Moneyline, MoneylineOutcome

# Optional: Import eth_account for signing if private key is provided
try:
    from eth_account import Account
    ETH_ACCOUNT_AVAILABLE = True
except ImportError:
    ETH_ACCOUNT_AVAILABLE = False
    Account = None


class PolymarketAPIClient:
    """Handles all API interactions with Polymarket"""
    
    def __init__(self):
        self.session = requests.Session()
        self.private_key = Config.POLYMARKET_PRIVATE_KEY
        
        if self.private_key and ETH_ACCOUNT_AVAILABLE:
            try:
                self.account = Account.from_key(self.private_key)
                self.address = self.account.address
                print(f"[DEBUG] Polymarket: Using authenticated account {self.address[:10]}...")
            except Exception as e:
                print(f"[WARNING] Failed to initialize Polymarket account: {e}")
                self.account = None
                self.address = None
        else:
            self.account = None
            self.address = None
            if self.private_key and not ETH_ACCOUNT_AVAILABLE:
                print("[WARNING] eth-account not installed. Install with: pip install eth-account")
    
    def _sign_request(self, method: str, path: str, body: str = '') -> Optional[Dict[str, str]]:
        """
        Sign request for authenticated Polymarket endpoints.
        
        Note: Polymarket's exact signing format may vary. This is a basic implementation.
        Adjust based on Polymarket's actual API requirements.
        """
        if not self.account:
            return None
        
        try:
            # Create signature message (format may need adjustment per Polymarket docs)
            timestamp = str(int(time.time()))
            message = f"{method}{path}{body}{timestamp}"
            
            # Sign the message using Ethereum message signing
            # Polymarket might use a different format - adjust if needed
            from eth_account.messages import encode_defunct
            message_hash = encode_defunct(text=message)
            signed_message = self.account.sign_message(message_hash)
            signature = signed_message.signature.hex()
            
            return {
                'X-PolyAddress': self.address,
                'X-PolySignature': signature,
                'X-PolyTimestamp': timestamp
            }
        except Exception as e:
            print(f"[WARNING] Failed to sign request: {e}")
            return None
    
    def get_sports_tags(self) -> List[Dict]:
        """Fetch all sports tags from /sports endpoint"""
        try:
            headers = {}
            # Add auth headers if private key is available
            if self.account:
                auth_headers = self._sign_request('GET', '/sports')
                if auth_headers:
                    headers.update(auth_headers)
            
            response = self.session.get(
                f"{Config.GAMMA_API}/sports",
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            return []
    
    def get_events(self, closed: bool = False, tag_id: Optional[int] = None, 
                   limit: int = None) -> List[Dict]:
        """
        Fetch events with pagination.
        Returns all events up to MAX_TOTAL_EVENTS.
        """
        if limit is None:
            limit = Config.MAX_EVENTS_PER_REQUEST
            
        params = {
            'closed': 'false' if not closed else 'true',
            'limit': limit,
            'offset': 0
        }
        
        if tag_id:
            params['tag_id'] = tag_id
            
        all_events = []
        
        while params['offset'] < Config.MAX_TOTAL_EVENTS:
            try:
                headers = {}
                # Add auth headers if private key is available
                if self.account:
                    auth_headers = self._sign_request('GET', '/events')
                    if auth_headers:
                        headers.update(auth_headers)
                
                response = self.session.get(
                    f"{Config.GAMMA_API}/events",
                    params=params,
                    headers=headers,
                    timeout=10
                )
                response.raise_for_status()
                events = response.json()
                
                if not events:
                    break
                
                all_events.extend(events)
                params['offset'] += limit
                
            except requests.RequestException:
                break
        
        return all_events

    def get_price_data(self, token_id: str) -> PriceData:
        """Fetch price and spread for a single token"""
        price_data = PriceData()
        
        try:
            headers = {}
            if self.account:
                auth_headers = self._sign_request('GET', f'/spread?token_id={token_id}')
                if auth_headers:
                    headers.update(auth_headers)
            
            spread_response = self.session.get(
                f"{Config.CLOB_API}/spread?token_id={token_id}",
                headers=headers,
                timeout=Config.API_TIMEOUT
            )
            if spread_response.status_code == 200:
                price_data.spread = float(spread_response.json().get('spread', 0))
        except:
            pass
        
        try:
            headers = {}
            if self.account:
                auth_headers = self._sign_request('GET', f'/midpoint?token_id={token_id}')
                if auth_headers:
                    headers.update(auth_headers)
            
            price_response = self.session.get(
                f"{Config.CLOB_API}/midpoint?token_id={token_id}",
                headers=headers,
                timeout=Config.API_TIMEOUT
            )
            if price_response.status_code == 200:
                price_data.price = float(price_response.json().get('mid', 0))
        except:
            pass
        
        return price_data
    
    def get_bulk_price_data(self, token_ids: List[str]) -> Dict[str, PriceData]:
        """Fetch price data for multiple tokens"""
        return {token_id: self.get_price_data(token_id) for token_id in token_ids}


class MarketExtractor:
    """Extracts and parses betting markets from events"""
    
    @staticmethod
    def parse_json_field(field) -> List:
        """Parse field that might be string or list"""
        if isinstance(field, str):
            try:
                return json.loads(field)
            except:
                return [field] if field else []
        elif isinstance(field, list):
            return field
        return []
    
    @staticmethod
    def clean_team_name(question: str) -> str:
        """Extract and clean team name from question"""
        name = question.replace('Will ', '').replace(' win on', '').replace('?', '').strip()
        name = re.sub(r'\s*\d{4}-\d{2}-\d{2}\s*', '', name).strip()
        return name
    
    def extract_moneyline(self, markets: List[Dict], price_data_map: Dict[str, PriceData],
                         has_draw: bool) -> Optional[Moneyline]:
        """
        Extract moneyline from markets.
        
        For sports with draw (soccer):
            Looks for 3 separate Yes/No markets: Team1 win, Draw, Team2 win
        
        For sports without draw (NHL):
            Looks for 2 separate Yes/No markets: Team1 win, Team2 win
        """
        team_markets = []
        draw_market = None
        
        for market in markets:
            question = market.get('question', '').lower()
            outcomes = self.parse_json_field(market.get('outcomes', []))
            clob_token_ids = self.parse_json_field(market.get('clobTokenIds', []))
            
            if len(outcomes) != 2 or not clob_token_ids:
                continue
            
            yes_token = clob_token_ids[0]
            
            if has_draw and 'draw' in question:
                draw_market = MoneylineOutcome(
                    name='Draw',
                    token_id=yes_token,
                    price_data=price_data_map.get(yes_token, PriceData())
                )
            elif 'win' in question:
                team_name = self.clean_team_name(market.get('question', ''))
                team_markets.append(MoneylineOutcome(
                    name=team_name,
                    token_id=yes_token,
                    price_data=price_data_map.get(yes_token, PriceData())
                ))
        
        expected_team_markets = 2
        if has_draw:
            if len(team_markets) == expected_team_markets and draw_market:
                return Moneyline(
                    outcomes=[team_markets[0], draw_market, team_markets[1]],
                    has_draw=True
                )
        else:
            if len(team_markets) == expected_team_markets:
                return Moneyline(
                    outcomes=team_markets,
                    has_draw=False
                )
        
        return None

