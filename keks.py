"""
Live Sports Betting Tracker for Polymarket
Fetches and displays real-time betting odds for live sports events.

Architecture:
- APIClient: Handles all API communications
- Sport (ABC): Base class for sport-specific logic
- SoccerSport, NHLSport: Concrete implementations
- MarketExtractor: Extracts and parses betting markets
- DisplayFormatter: Formats output
"""

import requests
import json
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass


# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Application configuration"""
    GAMMA_API = "https://gamma-api.polymarket.com"
    CLOB_API = "https://clob.polymarket.com"

    # API limits
    MAX_EVENTS_PER_REQUEST = 100
    MAX_TOTAL_EVENTS = 2000
    API_TIMEOUT = 2
    
    # Filtering thresholds
    DECIDED_ODDS_THRESHOLD = 0.99  # 99%+ means game is decided
    
    # Soccer league codes from /sports endpoint
    SOCCER_LEAGUE_CODES = [
        'epl', 'ucl', 'lal', 'bun', 'fl1', 'sea', 'mls', 'ere',
        'arg', 'mex', 'lib', 'sud', 'tur', 'rus', 'efl', 'con',
        'cof', 'uef', 'caf', 'efa'
    ]
    
    # NHL league codes
    NHL_LEAGUE_CODES = ['nhl']


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class LiveGameData:
    """Live game score and time data"""
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    current_minute: Optional[int] = None
    status: Optional[str] = None  # "1st half", "2nd half", "Halftime", etc.
    
    @property
    def score_display(self) -> str:
        """Get formatted score display"""
        return f"{self.home_score} - {self.away_score}"
    
    @property
    def time_display(self) -> str:
        """Get formatted time display"""
        if self.status and 'halftime' in self.status.lower():
            return "HT"
        elif self.current_minute is not None:
            return f"{self.current_minute}'"
        elif self.status:
            return self.status
        return "Live"


@dataclass
class PriceData:
    """Price and spread data for a betting outcome"""
    price: Optional[float] = None
    spread: Optional[float] = None


@dataclass
class MoneylineOutcome:
    """Single outcome in a moneyline market"""
    name: str
    token_id: str
    price_data: PriceData


@dataclass
class Moneyline:
    """Complete moneyline with all outcomes"""
    outcomes: List[MoneylineOutcome]
    has_draw: bool
    
    def is_decided(self, threshold: float = Config.DECIDED_ODDS_THRESHOLD) -> bool:
        """Check if any outcome has decided odds (>=threshold)"""
        for outcome in self.outcomes:
            if outcome.price_data.price and outcome.price_data.price >= threshold:
                return True
        return False


# ============================================================================
# API CLIENT
# ============================================================================

class PolymarketAPIClient:
    """Handles all API interactions with Polymarket"""
    
    def __init__(self):
        self.session = requests.Session()
    
    def get_sports_tags(self) -> List[Dict]:
        """Fetch all sports tags from /sports endpoint"""
        try:
            response = self.session.get(f"{Config.GAMMA_API}/sports", timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching sports tags: {e}")
            return []
    
    def get_events(self, closed: bool = False, tag_id: Optional[int] = None, 
                   limit: int = Config.MAX_EVENTS_PER_REQUEST) -> List[Dict]:
        """
        Fetch events with pagination.
        Returns all events up to MAX_TOTAL_EVENTS.
        """
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
                response = self.session.get(
                    f"{Config.GAMMA_API}/events",
                    params=params,
                    timeout=10
                )
                response.raise_for_status()
                events = response.json()
                
                if not events:
                    break
                
                all_events.extend(events)
                params['offset'] += limit
                
            except requests.RequestException as e:
                print(f"Error fetching events at offset {params['offset']}: {e}")
                break
        
        return all_events

    def get_price_data(self, token_id: str) -> PriceData:
        """Fetch price and spread for a single token"""
        price_data = PriceData()
        
        try:
            # Get spread
            spread_response = self.session.get(
                f"{Config.CLOB_API}/spread?token_id={token_id}",
                timeout=Config.API_TIMEOUT
            )
            if spread_response.status_code == 200:
                price_data.spread = float(spread_response.json().get('spread', 0))
        except:
            pass
        
        try:
            # Get midpoint price
            price_response = self.session.get(
                f"{Config.CLOB_API}/midpoint?token_id={token_id}",
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


# ============================================================================
# LIVE SCORE PROVIDER
# ============================================================================

class SofaScoreProvider:
    """
    Live scores from SofaScore.com
    
    SofaScore provides comprehensive live scores for football/soccer matches.
    No API key required - publicly accessible endpoint.
    
    Features:
    - Real-time scores
    - Current game minute
    - Match status (1st half, 2nd half, halftime, etc.)
    - Fuzzy team name matching
    - In-memory caching (30 seconds) to minimize API calls
    """
    
    BASE_URL = "https://www.sofascore.com/api/v1"
    CACHE_SECONDS = 30
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Referer': 'https://www.sofascore.com/'
        })
        # Cache: {cache_key: (LiveGameData, timestamp)}
        self._cache: Dict[str, Tuple[LiveGameData, datetime]] = {}
        # Cache all live matches
        self._all_matches_cache: Optional[Tuple[List[Dict], datetime]] = None
    
    def check_health(self) -> bool:
        """
        Check if SofaScore API is accessible and working.
        
        Returns:
            True if API is working, False otherwise
        
        Raises:
            Exception with details if API is not accessible
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/sport/football/events/live",
                timeout=10
            )
            
            if response.status_code != 200:
                raise Exception(
                    f"SofaScore API returned status code {response.status_code}. "
                    f"Expected 200. Response: {response.text[:200]}"
                )
            
            # Try to parse JSON
            data = response.json()
            
            # Verify expected structure
            if 'events' not in data:
                raise Exception(
                    f"SofaScore API response missing 'events' field. "
                    f"Response structure: {list(data.keys())}"
                )
            
            return True
            
        except requests.exceptions.Timeout:
            raise Exception(
                "SofaScore API request timed out after 10 seconds. "
                "Check your internet connection or try again later."
            )
        except requests.exceptions.ConnectionError as e:
            raise Exception(
                f"Failed to connect to SofaScore API. "
                f"Check your internet connection. Error: {str(e)}"
            )
        except requests.exceptions.RequestException as e:
            raise Exception(
                f"SofaScore API request failed: {str(e)}"
            )
        except ValueError as e:
            raise Exception(
                f"SofaScore API returned invalid JSON: {str(e)}"
            )
    
    def _normalize_team_name(self, team_name: str) -> str:
        """Normalize team name for matching"""
        name = team_name.lower()
        # Remove common suffixes and prefixes
        for term in [' fc', ' f.c.', ' united', ' city', ' sporting', ' club', ' cf', ' sc']:
            name = name.replace(term, '')
        # Remove extra whitespace
        name = ' '.join(name.split())
        return name.strip()
    
    def _teams_match(self, team1: str, team2: str) -> bool:
        """
        Check if two team names match using fuzzy matching.
        
        Examples:
        - "Perth Glory FC" matches "Perth Glory"
        - "Central Coast Mariners FC" matches "Central Coast Mariners"
        """
        normalized1 = self._normalize_team_name(team1)
        normalized2 = self._normalize_team_name(team2)
        
        # Exact match
        if normalized1 == normalized2:
            return True
        
        # Check if one contains the other
        if normalized1 in normalized2 or normalized2 in normalized1:
            return True
        
        # Check if key words match (for multi-word team names)
        words1 = set(normalized1.split())
        words2 = set(normalized2.split())
        
        # Remove common words that don't help matching
        common_stopwords = {'de', 'la', 'el', 'cf', 'sc', 'ac', 'as', 'the'}
        words1 -= common_stopwords
        words2 -= common_stopwords
        
        if not words1 or not words2:
            return False
        
        # Calculate word overlap
        common_words = words1 & words2
        overlap_ratio = len(common_words) / min(len(words1), len(words2))
        
        # If 70%+ of words match, consider it a match
        return overlap_ratio >= 0.7
    
    def _calculate_game_minute(self, time_data: Dict, status_description: str) -> Optional[int]:
        """
        Calculate current game minute based on period start timestamp.
        
        Args:
            time_data: Time data from SofaScore API
            status_description: Status description (e.g., "1st half", "2nd half")
            
        Returns:
            Current minute or None if cannot calculate
        """
        period_start = time_data.get('currentPeriodStartTimestamp')
        if not period_start:
            return None
        
        # Calculate elapsed time in current period
        now = datetime.now(timezone.utc).timestamp()
        elapsed_seconds = now - period_start
        elapsed_minutes = int(elapsed_seconds / 60)
        
        # Determine base minute based on period
        status_lower = status_description.lower()
        
        if '1st' in status_lower or 'first' in status_lower:
            # First half: 0-45 minutes
            return min(elapsed_minutes, 45)
        elif '2nd' in status_lower or 'second' in status_lower:
            # Second half: 45+ minutes
            return 45 + min(elapsed_minutes, 45)
        elif 'halftime' in status_lower:
            # Halftime
            return None  # Will show as "HT"
        else:
            # Unknown status, return elapsed
            return elapsed_minutes if elapsed_minutes >= 0 else None
    
    def _fetch_all_live_matches(self) -> List[Dict]:
        """
        Fetch all live football matches from SofaScore.
        Results are cached for CACHE_SECONDS to minimize API calls.
        
        Returns:
            List of live match data dictionaries
        
        Raises:
            Exception if SofaScore API fails
        """
        # Check cache
        if self._all_matches_cache:
            matches, cached_at = self._all_matches_cache
            age = (datetime.now(timezone.utc) - cached_at).total_seconds()
            if age < self.CACHE_SECONDS:
                return matches
        
        try:
            response = self.session.get(
                f"{self.BASE_URL}/sport/football/events/live",
                timeout=5
            )
            
            if response.status_code != 200:
                raise Exception(
                    f"SofaScore API returned status code {response.status_code}. "
                    f"Expected 200."
                )
            
            data = response.json()
            matches = data.get('events', [])
            
            # Cache the result
            self._all_matches_cache = (matches, datetime.now(timezone.utc))
            return matches
        
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch live matches from SofaScore: {str(e)}")
        except ValueError as e:
            raise Exception(f"SofaScore returned invalid JSON: {str(e)}")
    
    def get_live_game_data(self, home_team: str, away_team: str) -> Optional[LiveGameData]:
        """
        Fetch live game data for a specific matchup.
        
        Args:
            home_team: Home team name from Polymarket
            away_team: Away team name from Polymarket
            
        Returns:
            LiveGameData if match found and live, None if not found
            
        Raises:
            Exception if SofaScore API fails
        """
        # Check cache first
        cache_key = f"{home_team.lower()}_{away_team.lower()}"
        if cache_key in self._cache:
            data, cached_at = self._cache[cache_key]
            age = (datetime.now(timezone.utc) - cached_at).total_seconds()
            if age < self.CACHE_SECONDS:
                return data
        
        # Fetch all live matches (will raise exception if API fails)
        live_matches = self._fetch_all_live_matches()
        
        # Find matching match
        for match in live_matches:
            api_home = match.get('homeTeam', {}).get('name', '')
            api_away = match.get('awayTeam', {}).get('name', '')
            
            # Check if teams match (fuzzy)
            if (self._teams_match(home_team, api_home) and 
                self._teams_match(away_team, api_away)):
                
                # Extract score data
                home_score_data = match.get('homeScore', {})
                away_score_data = match.get('awayScore', {})
                
                home_score = home_score_data.get('current', 0)
                away_score = away_score_data.get('current', 0)
                
                # Extract status
                status_data = match.get('status', {})
                status_description = status_data.get('description', 'Live')
                
                # Calculate current minute
                time_data = match.get('time', {})
                current_minute = self._calculate_game_minute(time_data, status_description)
                
                # Create game data
                game_data = LiveGameData(
                    home_team=api_home,
                    away_team=api_away,
                    home_score=home_score,
                    away_score=away_score,
                    current_minute=current_minute,
                    status=status_description
                )
                
                # Cache the result
                self._cache[cache_key] = (game_data, datetime.now(timezone.utc))
                
                return game_data
        
        # No match found (not an error - game might not be live on SofaScore)
        return None


# ============================================================================
# SPORT CLASSES (Strategy Pattern)
# ============================================================================

class Sport(ABC):
    """Abstract base class for sport-specific logic"""
    
    @abstractmethod
    def get_name(self) -> str:
        """Return the display name of this sport"""
        pass
    
    @abstractmethod
    def get_league_codes(self) -> List[str]:
        """Return league codes from /sports endpoint"""
        pass
    
    @abstractmethod
    def is_sport_event(self, event: Dict) -> bool:
        """Check if an event belongs to this sport"""
        pass
    
    @abstractmethod
    def get_max_game_duration_hours(self) -> float:
        """Return maximum expected game duration in hours"""
        pass
    
    @abstractmethod
    def has_draw_option(self) -> bool:
        """Return whether this sport has draw/tie outcomes"""
        pass
    
    def extract_teams_from_title(self, title: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract home and away team names from event title.
        Default implementation assumes format: "Team A vs. Team B" or "Team A vs Team B"
        Override for sport-specific parsing.
        
        Returns:
            Tuple of (home_team, away_team) or (None, None) if cannot parse
        """
        title_lower = title.lower()
        
        # Try different vs separators
        for separator in [' vs. ', ' vs ', ' v ']:
            if separator in title_lower:
                # Remove common suffixes from title first
                clean_title = title
                for suffix in [' - More Markets', ' - Match Winner', ' - Moneyline']:
                    if suffix in title:
                        clean_title = title.replace(suffix, '')
                
                parts = clean_title.split(separator, 1)
                if len(parts) == 2:
                    home_team = parts[0].strip()
                    away_team = parts[1].strip()
                    return (home_team, away_team)
        
        return (None, None)
    
    def is_live_event(self, event: Dict) -> bool:
        """
        Check if event is currently live.
        Default implementation checks:
        - Not closed
        - Started within max game duration
        """
        if event.get('closed', False):
            return False
        
        start_time_str = event.get('startTime') or event.get('eventDate')
        if not start_time_str:
            return False
        
        try:
            start_time = datetime.fromisoformat(str(start_time_str).replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            hours_since_start = (now - start_time).total_seconds() / 3600
            
            return 0 <= hours_since_start <= self.get_max_game_duration_hours()
        except:
            return False


class SoccerSport(Sport):
    """Soccer/Football specific implementation"""
    
    def get_name(self) -> str:
        return "Soccer"
    
    def get_league_codes(self) -> List[str]:
        return Config.SOCCER_LEAGUE_CODES
    
    def has_draw_option(self) -> bool:
        return True
    
    def get_max_game_duration_hours(self) -> float:
        # 90min play + 15min halftime + ~10min stoppage + 30min buffer = 2.5 hours
        return 2.5
    
    def is_sport_event(self, event: Dict) -> bool:
        """Check if event is a soccer game"""
        title = event.get('title', '')
        title_lower = title.lower()
        
        # Must have FC or common soccer terms
        has_fc = 'fc' in title_lower or 'f.c.' in title_lower
        has_soccer_terms = any(term in title_lower for term in [
            'united', 'city fc', 'athletic', 'sporting', 'real ', 'club ',
            'wanderers', 'glory', 'mariners', 'victory', 'rovers'
        ])
        
        is_soccer = has_fc or has_soccer_terms
        
        # Exclude non-soccer events
        excluded_terms = [
            'dota', 'counter-strike', 'valorant', 'league of legends', 'lol:',
            'ufc', 'gamecocks', 'raiders', 'wildcats', 'tigers', 'ospreys',
            'cardinals', 'warriors', 'lancers', 'trailblazers', 'jaguars',
            'leathernecks', 'sharks', 'tulane', 'tulsa', 'margin of victory',
            'larger margin', 'more markets'
        ]
        
        is_excluded = any(term in title_lower for term in excluded_terms)
        
        return is_soccer and not is_excluded


class NHLSport(Sport):
    """NHL Hockey specific implementation"""
    
    def get_name(self) -> str:
        return "NHL"
    
    def get_league_codes(self) -> List[str]:
        return Config.NHL_LEAGUE_CODES
    
    def has_draw_option(self) -> bool:
        return False  # NHL uses overtime/shootout, no draws
    
    def get_max_game_duration_hours(self) -> float:
        # 3 x 20min periods + 2 x 15min intermissions + overtime potential = ~3.5 hours
        return 3.5
    
    def is_sport_event(self, event: Dict) -> bool:
        """Check if event is an NHL game"""
        title = event.get('title', '').lower()
        
        # NHL team identifiers
        nhl_terms = [
            'bruins', 'maple leafs', 'canadiens', 'senators', 'sabres',
            'rangers', 'islanders', 'devils', 'flyers', 'penguins',
            'capitals', 'hurricanes', 'blue jackets', 'panthers', 'lightning',
            'blackhawks', 'avalanche', 'stars', 'wild', 'predators',
            'blues', 'jets', 'flames', 'oilers', 'canucks',
            'golden knights', 'kings', 'ducks', 'sharks', 'coyotes',
            'kraken', 'nhl'
        ]
        
        has_nhl_term = any(term in title for term in nhl_terms)
        
        # Exclude obvious non-NHL
        is_soccer = 'fc' in title or any(term in title for term in ['united', 'city fc'])
        
        return has_nhl_term and not is_soccer


# ============================================================================
# MARKET EXTRACTION
# ============================================================================

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
        # Remove date pattern (e.g., "2025-11-07")
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
            
            # Must be binary Yes/No market
            if len(outcomes) != 2 or not clob_token_ids:
                continue
            
            yes_token = clob_token_ids[0]
            
            # Check for draw market
            if has_draw and 'draw' in question:
                draw_market = MoneylineOutcome(
                    name='Draw',
                    token_id=yes_token,
                    price_data=price_data_map.get(yes_token, PriceData())
                )
            # Check for win markets
            elif 'win' in question:
                team_name = self.clean_team_name(market.get('question', ''))
                team_markets.append(MoneylineOutcome(
                    name=team_name,
                    token_id=yes_token,
                    price_data=price_data_map.get(yes_token, PriceData())
                ))
        
        # Validate we have the right number of markets
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


# ============================================================================
# DISPLAY FORMATTING
# ============================================================================

class DisplayFormatter:
    """Formats output for display"""
    
    @staticmethod
    def format_price(price: Optional[float], spread: Optional[float] = None) -> str:
        """Format price with optional spread"""
        if price is None:
            return "Price unavailable"
        
        price_pct = price * 100
        spread_info = ""
        if spread is not None:
            spread_pct = spread * 100
            spread_info = f" | Spread: {spread_pct:.2f}%"
        
        return f"{price_pct:5.1f}% (${price:.3f}){spread_info}"
    
    @staticmethod
    def display_event_header(event: Dict, live_data: Optional[LiveGameData] = None):
        """Display event header with optional live score"""
        print(f"{'='*80}")
        
        if live_data:
            # Display with live score and time
            print(f"🔴 LIVE | {event['title']}")
            print(f"Score: {live_data.score_display} | Time: {live_data.time_display}")
        else:
            # Display without live score
            print(f"🔴 LIVE | {event['title']}")
        
        start_time = event.get('startTime', 'N/A')
        print(f"Game Time: {start_time}")
        print(f"{'='*80}")
    
    @staticmethod
    def display_moneyline(moneyline: Moneyline):
        """Display moneyline outcomes"""
        market_type = "3-way" if moneyline.has_draw else "2-way"
        print(f"\nMONEYLINE ({market_type}):")
        print()
        
        for outcome in moneyline.outcomes:
            formatted_price = DisplayFormatter.format_price(
                outcome.price_data.price,
                outcome.price_data.spread
            )
            print(f"  {outcome.name:35s} : {formatted_price}")


# ============================================================================
# MAIN APPLICATION
# ============================================================================

class LiveSportsTracker:
    """Main application orchestrator"""
    
    def __init__(self, sports: List[Sport], score_provider: Optional[SofaScoreProvider] = None):
        self.api_client = PolymarketAPIClient()
        self.market_extractor = MarketExtractor()
        self.formatter = DisplayFormatter()
        self.sports = sports
        self.score_provider = score_provider
        
        # Check if live scores are enabled and working
        if self.score_provider:
            print("Checking SofaScore API health...")
            try:
                self.score_provider.check_health()
                print("✓ SofaScore API is working correctly\n")
            except Exception as e:
                print("\n" + "="*80)
                print("❌ FATAL ERROR: SofaScore API Health Check Failed")
                print("="*80)
                print(f"\nError details:\n{str(e)}\n")
                print("The script requires SofaScore to determine if games are live.")
                print("Please check your internet connection and try again.")
                print("If the problem persists, SofaScore.com may be down or blocking requests.")
                print("="*80 + "\n")
                raise SystemExit(1)
    
    def fetch_league_tags(self):
        """Fetch and display league tags for all sports"""
        print("Fetching league tags from /sports endpoint...")
        all_tags = self.api_client.get_sports_tags()
        
        for sport in self.sports:
            sport_codes = sport.get_league_codes()
            found_tags = [
                tag for tag in all_tags
                if tag.get('sport', '').lower() in sport_codes
            ]
            
            if found_tags:
                print(f"\n{sport.get_name()}:")
                for tag in found_tags:
                    print(f"  Found league: {tag.get('sport')} (ID: {tag.get('id')})")
    
    def get_live_events(self, sport: Sport) -> List[Dict]:
        """Get live events for a specific sport"""
        # Fetch all non-closed events
        all_events = self.api_client.get_events(closed=False)
        
        # Filter for this sport and live status
        live_events = [
            event for event in all_events
            if sport.is_sport_event(event) and sport.is_live_event(event)
        ]
        
        return live_events
    
    def process_event(self, event: Dict, sport: Sport) -> bool:
        """
        Process and display a single event.
        Returns True if event was displayed, False if filtered out.
        """
        # Extract team names from title
        home_team, away_team = sport.extract_teams_from_title(event['title'])
        
        if not home_team or not away_team:
            # Can't verify with SofaScore without team names - skip
            return False
        
        # Check SofaScore for live game data - this is the ONLY source of truth
        live_data = None
        if self.score_provider:
            try:
                live_data = self.score_provider.get_live_game_data(home_team, away_team)
            except Exception as e:
                print("\n" + "="*80)
                print("❌ FATAL ERROR: SofaScore API Failed During Operation")
                print("="*80)
                print(f"\nError details:\n{str(e)}\n")
                print("The SofaScore API was working at startup but is now failing.")
                print("This might be a temporary network issue or rate limiting.")
                print("="*80 + "\n")
                raise SystemExit(1)
        
        # If game is not in SofaScore's live feed, it's not live - skip it
        if not live_data:
            # Don't show anything - game is not live according to SofaScore
            return False
        
        # Check if game status indicates it's finished
        if live_data.status:
            status_lower = live_data.status.lower()
            if any(term in status_lower for term in ['finished', 'ended', 'final', 'full time', 'ft']):
                # Game is marked as finished in SofaScore - skip
                return False
        
        # Game is confirmed live by SofaScore - proceed to get betting odds
        markets = event.get('markets', [])
        if not markets:
            return False
        
        # Collect all token IDs
        all_token_ids = []
        for market in markets:
            clob_token_ids = self.market_extractor.parse_json_field(
                market.get('clobTokenIds', [])
            )
            all_token_ids.extend(clob_token_ids)
        
        if not all_token_ids:
            return False
        
        # Fetch price data
        price_data_map = self.api_client.get_bulk_price_data(all_token_ids)
        
        # Extract moneyline
        moneyline = self.market_extractor.extract_moneyline(
            markets, price_data_map, sport.has_draw_option()
        )
        
        if not moneyline:
            self.formatter.display_event_header(event, live_data)
            print("\n⚠️  No moneyline markets found for this game")
            print()
            return False
        
        # Display the event with live data and betting odds
        self.formatter.display_event_header(event, live_data)
        self.formatter.display_moneyline(moneyline)
        print()
        
        return True
    
    def run(self):
        """Main execution loop"""
        # Fetch and display league tags
        self.fetch_league_tags()
        
        # Process each sport
        for sport in self.sports:
            print(f"\n{'='*80}")
            print(f"Fetching LIVE {sport.get_name()} events...")
            print(f"{'='*80}")
            
            live_events = self.get_live_events(sport)
            
            print(f"\n✓ Found {len(live_events)} potentially LIVE {sport.get_name()} game(s) from Polymarket")
            print(f"   (Verifying live status with SofaScore...)\n")
            
            if not live_events:
                print(f"No live {sport.get_name()} games currently.")
                continue
            
            # Process each event
            games_displayed = 0
            for event in live_events:
                if self.process_event(event, sport):
                    games_displayed += 1
            
            # Summary
            print(f"{'='*80}")
            print(f"✓ Displayed {games_displayed} confirmed LIVE {sport.get_name()} game(s)")
            print(f"   (Verified by SofaScore as currently in progress)")
            print(f"{'='*80}\n")


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    """Application entry point"""
    # Configure which sports to track
    sports = [
        SoccerSport(),
        # NHLSport(),  # Uncomment to add NHL tracking
    ]
    
    # Configure live score provider
    # SofaScore provides free, real-time scores with no API key required
    score_provider = SofaScoreProvider()
    
    # Run the tracker
    tracker = LiveSportsTracker(sports, score_provider)
    tracker.run()


if __name__ == "__main__":
    main()
