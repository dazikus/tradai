"""
Main tracking logic - orchestrates API calls and data collection
"""

from typing import List, Dict, Optional

from config import Config
from models import LiveGameResponse
from .polymarket import PolymarketAPIClient, MarketExtractor
from .sofascore import SofaScoreProvider
from .sports import Sport


class LiveSportsTracker:
    """Main application orchestrator - collects data instead of printing"""
    
    def __init__(self, sports: List[Sport], score_provider: Optional[SofaScoreProvider] = None):
        self.api_client = PolymarketAPIClient()
        self.market_extractor = MarketExtractor()
        self.sports = sports
        self.score_provider = score_provider
        
        # Note: Health check removed from init to allow app to start even if SofaScore is temporarily unavailable
        # The app will gracefully handle SofaScore errors during data fetching
    
    def get_live_events(self, sport: Sport) -> List[Dict]:
        """Get live events for a specific sport"""
        all_events = self.api_client.get_events(closed=False)
        sport_events = [event for event in all_events if sport.is_sport_event(event)]
        live_events = [event for event in sport_events if sport.is_live_event(event)]
        
        return live_events
    
    def process_event(self, event: Dict, sport: Sport) -> Optional[LiveGameResponse]:
        """
        Process a single event and return structured data.
        Returns None if event should be filtered out.
        """
        # Extract team names from title
        home_team, away_team = sport.extract_teams_from_title(event['title'])
        
        if not home_team or not away_team:
            return None
        
        # Check SofaScore for live game data
        live_data = None
        if self.score_provider:
            try:
                live_data = self.score_provider.get_live_game_data(home_team, away_team)
            except Exception as e:
                # SofaScore error - log but don't crash
                # Game might still be shown with Polymarket data only
                print(f"[WARNING] SofaScore API error for {home_team} vs {away_team}: {e}")
                return None  # Skip games we can't verify are live
        
        # If game is not in SofaScore's live feed, it's not live
        if not live_data:
            return None
        
        # Check if game status indicates it's finished
        if live_data.status:
            status_lower = live_data.status.lower()
            if any(term in status_lower for term in ['finished', 'ended', 'full time', 'after extra time', 'after penalties']):
                return None
        
        # Game is confirmed live by SofaScore - get betting odds
        markets = event.get('markets', [])
        if not markets:
            return None
        
        # Collect all token IDs
        all_token_ids = []
        for market in markets:
            clob_token_ids = self.market_extractor.parse_json_field(
                market.get('clobTokenIds', [])
            )
            all_token_ids.extend(clob_token_ids)
        
        if not all_token_ids:
            return None
        
        # Fetch price data
        price_data_map = self.api_client.get_bulk_price_data(all_token_ids)
        
        # Extract moneyline
        moneyline = self.market_extractor.extract_moneyline(
            markets, price_data_map, sport.has_draw_option()
        )
        
        if not moneyline:
            return None
        
        # Build Polymarket URL
        event_id = event.get('id', '')
        event_slug = event.get('slug', '')
        polymarket_url = f"{Config.POLYMARKET_EVENT_URL}/{event_slug}"
        if not event_slug and event_id:
            polymarket_url = f"{Config.POLYMARKET_EVENT_URL}/{event_id}"
        
        # Create response object
        return LiveGameResponse(
            event_id=event_id,
            event_slug=event_slug,
            title=event['title'],
            polymarket_url=polymarket_url,
            start_time=event.get('startTime', ''),
            home_team=home_team,
            away_team=away_team,
            live_data=live_data,
            moneyline=moneyline,
            sport=sport.get_name()
        )
    
    def get_all_live_games(self) -> Dict:
        """
        Main method to get all live games across all sports.
        Returns structured data suitable for JSON API response.
        """
        result = {
            'timestamp': None,
            'sports': {},
            'total_games': 0
        }
        
        from datetime import datetime, timezone
        result['timestamp'] = datetime.now(timezone.utc).isoformat()
        
        for sport in self.sports:
            sport_name = sport.get_name()
            live_events = self.get_live_events(sport)
            
            games = []
            for event in live_events:
                game_data = self.process_event(event, sport)
                if game_data:
                    games.append(game_data.to_dict())
            
            result['sports'][sport_name] = {
                'total_found': len(live_events),
                'total_live': len(games),
                'games': games
            }
            result['total_games'] += len(games)
        
        return result

