"""
Main tracking logic - orchestrates API calls and data collection
"""

from typing import List, Dict, Optional

from config import Config
from models import LiveGameResponse
from .polymarket import PolymarketAPIClient, MarketExtractor
from .sofascore import SofaScoreProvider
from .sports import Sport
from logger import log


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
        log(f"[DEBUG] Polymarket: Fetched {len(all_events)} total events (closed=false)")
        
        # Log events filtered out by is_sport_event
        filtered_out = []
        sport_events = []
        for event in all_events:
            if sport.is_sport_event(event):
                sport_events.append(event)
            else:
                filtered_out.append(event)
        
        log(f"[DEBUG] Polymarket: Found {len(sport_events)} {sport.get_name()} events")
        log(f"[DEBUG] Polymarket: Filtered out {len(filtered_out)} non-{sport.get_name()} events")
        
        # Check if "Gimnasia" or "Vélez" are in filtered out events
        gimnasia_events = [e for e in filtered_out if 'gimnasia' in e.get('title', '').lower() or 'vélez' in e.get('title', '').lower() or 'velez' in e.get('title', '').lower()]
        if gimnasia_events:
            log(f"[DEBUG] ⚠️  Found {len(gimnasia_events)} Gimnasia/Vélez events in FILTERED OUT list:")
            for event in gimnasia_events:
                title = event.get('title', 'N/A')
                event_id = event.get('id', 'N/A')
                closed = event.get('closed', 'N/A')
                tags = event.get('tags', [])
                log(f"[DEBUG]     - Event ID {event_id}: '{title}' (closed={closed}, tags={tags})")
        
        live_events = [event for event in sport_events if sport.is_live_event(event)]
        log(f"[DEBUG] Polymarket: Found {len(live_events)} live {sport.get_name()} events")
        
        # Log all live event titles
        for i, event in enumerate(live_events, 1):
            title = event.get('title', 'N/A')
            event_id = event.get('id', 'N/A')
            log(f"[DEBUG]   {i}. Polymarket Event ID {event_id}: '{title}'")
        
        return live_events
    
    def process_event(self, event: Dict, sport: Sport) -> Optional[LiveGameResponse]:
        """
        Process a single event and return structured data.
        Returns None if event should be filtered out.
        """
        # Extract team names from title
        event_title = event.get('title', '')
        log(f"[DEBUG] Polymarket event title: '{event_title}'")
        home_team, away_team = sport.extract_teams_from_title(event_title)
        log(f"[DEBUG] Extracted teams: Home='{home_team}', Away='{away_team}'")
        
        if not home_team or not away_team:
            log(f"[DEBUG] ✗ Failed to extract team names from title")
            return None
        
        # Check SofaScore for live game data
        live_data = None
        if self.score_provider:
            try:
                log(f"[DEBUG] Checking SofaScore for: {home_team} vs {away_team}")
                live_data = self.score_provider.get_live_game_data(home_team, away_team)
                if live_data:
                    log(f"[DEBUG] ✓ Found match in SofaScore: {live_data.home_team} vs {live_data.away_team}")
                else:
                    log(f"[DEBUG] ✗ No match found in SofaScore for: {home_team} vs {away_team}")
            except Exception as e:
                # SofaScore error - log but don't crash
                # Game might still be shown with Polymarket data only
                log(f"[WARNING] SofaScore API error for {home_team} vs {away_team}: {e}")
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
            
            log(f"[DEBUG] {sport_name}: Found {len(live_events)} live events from Polymarket")
            
            games = []
            for event in live_events:
                game_data = self.process_event(event, sport)
                if game_data:
                    games.append(game_data.to_dict())
            
            log(f"[DEBUG] {sport_name}: Matched {len(games)}/{len(live_events)} games with SofaScore")
            
            result['sports'][sport_name] = {
                'total_found': len(live_events),
                'total_live': len(games),
                'games': games
            }
            result['total_games'] += len(games)
        
        # Check for SofaScore games that don't match any Polymarket events
        if self.score_provider:
            try:
                sofascore_matches = self.score_provider._fetch_all_live_matches()
                matched_sofascore_teams = set()
                
                # Get all matched SofaScore teams from successful matches (already processed above)
                for sport in self.sports:
                    sport_name = sport.get_name()
                    if sport_name in result['sports']:
                        for game in result['sports'][sport_name]['games']:
                            if 'live_data' in game and game['live_data']:
                                live_data = game['live_data']
                                matched_sofascore_teams.add((live_data.get('home_team', '').lower(), live_data.get('away_team', '').lower()))
                
                # Find unmatched SofaScore games
                unmatched_sofascore = []
                for match in sofascore_matches:
                    api_home = match.get('homeTeam', {}).get('name', '')
                    api_away = match.get('awayTeam', {}).get('name', '')
                    if api_home and api_away:
                        team_pair = (api_home.lower(), api_away.lower())
                        if team_pair not in matched_sofascore_teams:
                            unmatched_sofascore.append((api_home, api_away))
                
                if unmatched_sofascore:
                    log(f"[DEBUG] ⚠️  Found {len(unmatched_sofascore)} SofaScore games without matching Polymarket events:")
                    for home, away in unmatched_sofascore[:10]:  # Show top 10
                        log(f"[DEBUG]     - '{home}' vs '{away}'")
                    if len(unmatched_sofascore) > 10:
                        log(f"[DEBUG]     ... and {len(unmatched_sofascore) - 10} more")
            except Exception as e:
                log(f"[DEBUG] Could not check unmatched SofaScore games: {e}")
        
        return result

