"""
SofaScore API provider for live game data
"""

import requests
import re
import time
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone

from models import LiveGameData, GameMomentum, GameComment
from logger import log


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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Origin': 'https://www.sofascore.com',
            'Referer': 'https://www.sofascore.com/',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        })
        self._cache: Dict[str, Tuple[LiveGameData, datetime]] = {}
        self._all_matches_cache: Optional[Tuple[List[Dict], datetime]] = None
    
    def check_health(self) -> bool:
        """Check if SofaScore API is accessible and working"""
        try:
            response = self.session.get(
                f"{self.BASE_URL}/sport/football/events/live",
                timeout=10
            )
            
            if response.status_code != 200:
                raise Exception(f"SofaScore API returned status {response.status_code}")
            
            data = response.json()
            
            if 'events' not in data:
                raise Exception("SofaScore API response missing 'events' field")
            
            return True
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"SofaScore API request failed: {str(e)}")
        except ValueError as e:
            raise Exception(f"SofaScore API returned invalid JSON: {str(e)}")
    
    def _normalize_team_name(self, team_name: str) -> str:
        """Normalize team name for matching"""
        name = team_name.lower()
        # Replace hyphens and apostrophes with spaces
        name = name.replace('-', ' ').replace("'", ' ')
        # Remove year suffixes
        name = re.sub(r"'\d+", '', name)
        name = re.sub(r'\b\d{4}\b', '', name)
        
        # Remove common prefixes (order matters - check full words)
        prefixes = [
            'ca ', 'club atlético ', 'club atletico ', 'atlético ', 'atletico ',
            'ac ', 'athletic club ', 'athletic ', 'cf ', 'sc ', 'fc ', 'f.c. ',
            'cd ', 'club deportivo ', 'club de fútbol ', 'club de futbol '
        ]
        for prefix in prefixes:
            if name.startswith(prefix):
                name = name[len(prefix):]
        
        # Remove common suffixes (order matters - longer first)
        # NOTE: Don't remove "y esgrima" - it's part of team names like "Gimnasia y Esgrima"
        # IMPORTANT: Process "reserves" BEFORE "reserve" to avoid bugs like "rangers reserves" -> "rangerss"
        suffixes = [
            ' saudi club', ' saudi', ' fc', ' f.c.', ' f c', 
            ' united', ' city', ' sporting', ' club', ' cf', ' sc', 
            ' ac', ' athletic', ' athletic club', ' de fútbol', ' de futbol',
            ' w.f.c.', ' wfc', ' women', ' reserves', ' reserve', ' u21', ' u23', ' u13'
        ]
        for term in suffixes:
            # Use word boundary-aware replacement to avoid partial matches
            # Example: "rangers reserves" should become "rangers" not "rangerss"
            term_clean = term.strip()
            # Replace whole word only (with space before it or at start)
            # Pattern: space + term + end of string OR space + term + space OR start + term + space
            pattern = r'(^|\s)' + re.escape(term_clean) + r'(\s|$)'
            name = re.sub(pattern, r'\1\2', name)
        
        # Clean up multiple spaces
        name = ' '.join(name.split())
        return name.strip()
    
    def _teams_match(self, team1: str, team2: str, debug: bool = False) -> bool:
        """Check if two team names match using fuzzy matching"""
        normalized1 = self._normalize_team_name(team1)
        normalized2 = self._normalize_team_name(team2)
        
        if debug:
            log(f"    [MATCH] Comparing: '{team1}' -> '{normalized1}' vs '{team2}' -> '{normalized2}'")
        
        if normalized1 == normalized2:
            if debug:
                log(f"    [MATCH] ✓ Exact match!")
            return True
        
        if normalized1 in normalized2 or normalized2 in normalized1:
            if debug:
                log(f"    [MATCH] ✓ Substring match!")
            return True
        
        words1 = set(normalized1.split())
        words2 = set(normalized2.split())
        
        common_stopwords = {'de', 'la', 'el', 'cf', 'sc', 'ac', 'as', 'the', 'y', 'vs'}
        words1 -= common_stopwords
        words2 -= common_stopwords
        
        if not words1 or not words2:
            if debug:
                log(f"    [MATCH] ✗ No words after stopword removal")
            return False
        
        common_words = words1 & words2
        overlap_ratio = len(common_words) / min(len(words1), len(words2))
        
        if debug:
            log(f"    [MATCH] Words1: {words1}, Words2: {words2}, Common: {common_words}, Ratio: {overlap_ratio:.2f}")
        
        result = overlap_ratio >= 0.7
        if debug:
            log(f"    [MATCH] {'✓ Match!' if result else '✗ No match'}")
        
        return result
    
    def _calculate_game_minute(self, time_data: Dict, status_description: str) -> Optional[int]:
        """Calculate current game minute based on period start timestamp"""
        period_start = time_data.get('currentPeriodStartTimestamp')
        if not period_start:
            return None
        
        now = datetime.now(timezone.utc).timestamp()
        elapsed_seconds = now - period_start
        elapsed_minutes = int(elapsed_seconds / 60)
        
        status_lower = status_description.lower()
        
        if '1st' in status_lower or 'first' in status_lower:
            return min(elapsed_minutes, 45)
        elif '2nd' in status_lower or 'second' in status_lower:
            return 45 + min(elapsed_minutes, 45)
        elif 'halftime' in status_lower:
            return None
        else:
            return elapsed_minutes if elapsed_minutes >= 0 else None
    
    def _fetch_all_live_matches(self) -> List[Dict]:
        """Fetch all live football matches from SofaScore (cached)"""
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
                raise Exception(f"SofaScore API returned status {response.status_code}")
            
            data = response.json()
            matches = data.get('events', [])
            
            log(f"[DEBUG] SofaScore API: Fetched {len(matches)} live matches")
            
            # Log ALL SofaScore games for debugging
            for i, match in enumerate(matches, 1):
                api_home = match.get('homeTeam', {}).get('name', 'N/A')
                api_away = match.get('awayTeam', {}).get('name', 'N/A')
                status_desc = match.get('status', {}).get('description', 'N/A')
                event_id = match.get('id', 'N/A')
                log(f"[DEBUG]   {i}. SofaScore Event ID {event_id}: '{api_home}' vs '{api_away}' ({status_desc})")
            
            self._all_matches_cache = (matches, datetime.now(timezone.utc))
            return matches
        
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch live matches from SofaScore: {str(e)}")
        except ValueError as e:
            raise Exception(f"SofaScore returned invalid JSON: {str(e)}")
    
    def fetch_game_comments(self, event_id: int, limit: int = 10) -> List[GameComment]:
        """Fetch recent game comments/events from SofaScore"""
        try:
            response = self.session.get(
                f"{self.BASE_URL}/event/{event_id}/comments",
                timeout=3
            )
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            comments_data = data.get('comments', [])
            
            comments = []
            for comment_data in comments_data[:limit]:
                text = comment_data.get('text', '')
                event_type = comment_data.get('type', 'unknown')
                is_home = comment_data.get('isHome', False)
                time = comment_data.get('time', 0)
                
                player_name = None
                player_data = comment_data.get('player')
                if player_data:
                    player_name = player_data.get('shortName') or player_data.get('name')
                
                comments.append(GameComment(
                    text=text,
                    event_type=event_type,
                    is_home=is_home,
                    time=time,
                    player_name=player_name
                ))
            
            return comments
            
        except Exception:
            return []
    
    def fetch_game_momentum(self, event_id: int) -> Optional[GameMomentum]:
        """
        Fetch game momentum and statistics from SofaScore.
        Combines data from /graph, /statistics, and /comments endpoints.
        """
        momentum = GameMomentum(event_id=event_id)
        
        # Fetch momentum graph data
        try:
            graph_response = self.session.get(
                f"{self.BASE_URL}/event/{event_id}/graph",
                timeout=3
            )
            
            if graph_response.status_code == 200:
                graph_data = graph_response.json()
                graph_points = graph_data.get('graphPoints', [])
                
                if graph_points:
                    momentum.momentum_graph = graph_points
                    
                    recent_points = graph_points[-5:] if len(graph_points) >= 5 else graph_points
                    if recent_points:
                        total_weight = 0
                        weighted_sum = 0
                        for i, point in enumerate(recent_points):
                            weight = i + 1
                            value = point.get('value', 0)
                            weighted_sum += value * weight
                            total_weight += weight
                        
                        momentum.momentum_value = int(weighted_sum / total_weight) if total_weight > 0 else 0
                        
                        if momentum.momentum_value > 15:
                            momentum.momentum_direction = "home"
                        elif momentum.momentum_value < -15:
                            momentum.momentum_direction = "away"
                        else:
                            momentum.momentum_direction = "neutral"
        except Exception:
            pass
        
        # Fetch statistics data
        try:
            stats_response = self.session.get(
                f"{self.BASE_URL}/event/{event_id}/statistics",
                timeout=3
            )
            
            if stats_response.status_code == 200:
                stats_data = stats_response.json()
                statistics = stats_data.get('statistics', [])
                
                for period_stats in statistics:
                    if period_stats.get('period') != 'ALL':
                        continue
                    
                    groups = period_stats.get('groups', [])
                    
                    for group in groups:
                        items = group.get('statisticsItems', [])
                        
                        for item in items:
                            key = item.get('key', '')
                            home_val = item.get('homeValue')
                            away_val = item.get('awayValue')
                            
                            if key == 'ballPossession' and home_val is not None and away_val is not None:
                                momentum.possession_home = int(home_val)
                                momentum.possession_away = int(away_val)
                            
                            elif key == 'attacks' and home_val is not None and away_val is not None:
                                momentum.attacks_home = int(home_val) if isinstance(home_val, (int, float)) else 0
                                momentum.attacks_away = int(away_val) if isinstance(away_val, (int, float)) else 0
                            
                            elif key == 'dangerousAttacks' and home_val is not None and away_val is not None:
                                momentum.dangerous_attacks_home = int(home_val) if isinstance(home_val, (int, float)) else 0
                                momentum.dangerous_attacks_away = int(away_val) if isinstance(away_val, (int, float)) else 0
        except Exception:
            pass
        
        # Fetch recent comments/events
        try:
            comments = self.fetch_game_comments(event_id, limit=10)
            if comments:
                momentum.recent_comments = comments
        except Exception:
            pass
        
        # If we didn't get momentum from graph but have stats, calculate it
        if momentum.momentum_direction is None and momentum.possession_home is not None:
            momentum.momentum_direction = self._calculate_momentum_direction(momentum)
        
        return momentum if self._has_momentum_data(momentum) else None
    
    def _has_momentum_data(self, momentum: GameMomentum) -> bool:
        """Check if momentum object has any data"""
        return any([
            momentum.possession_home is not None,
            momentum.attacks_home is not None,
            momentum.dangerous_attacks_home is not None,
            momentum.momentum_value is not None,
            momentum.recent_comments is not None
        ])
    
    def _calculate_momentum_direction(self, momentum: GameMomentum) -> str:
        """Calculate which team has the momentum based on available stats"""
        home_score = 0
        away_score = 0
        total_factors = 0
        
        if momentum.possession_home is not None and momentum.possession_away is not None:
            if momentum.possession_home > momentum.possession_away + 10:
                home_score += 1
            elif momentum.possession_away > momentum.possession_home + 10:
                away_score += 1
            total_factors += 1
        
        if momentum.attacks_home is not None and momentum.attacks_away is not None:
            if momentum.attacks_home > momentum.attacks_away:
                home_score += 1.5
            elif momentum.attacks_away > momentum.attacks_home:
                away_score += 1.5
            total_factors += 1
        
        if momentum.dangerous_attacks_home is not None and momentum.dangerous_attacks_away is not None:
            if momentum.dangerous_attacks_home > momentum.dangerous_attacks_away:
                home_score += 2
            elif momentum.dangerous_attacks_away > momentum.dangerous_attacks_home:
                away_score += 2
            total_factors += 1
        
        if total_factors == 0:
            return "neutral"
        
        if home_score > away_score * 1.2:
            return "home"
        elif away_score > home_score * 1.2:
            return "away"
        else:
            return "neutral"
    
    def get_live_game_data(self, home_team: str, away_team: str) -> Optional[LiveGameData]:
        """Fetch live game data for a specific matchup"""
        cache_key = f"{home_team.lower()}_{away_team.lower()}"
        if cache_key in self._cache:
            data, cached_at = self._cache[cache_key]
            age = (datetime.now(timezone.utc) - cached_at).total_seconds()
            if age < self.CACHE_SECONDS:
                return data
        
        live_matches = self._fetch_all_live_matches()
        
        log(f"[DEBUG] Looking for: '{home_team}' vs '{away_team}'")
        log(f"[DEBUG]   Normalized: '{self._normalize_team_name(home_team)}' vs '{self._normalize_team_name(away_team)}'")
        
        matched = False
        potential_matches = []  # Track games that might match for debugging
        
        for match in live_matches:
            api_home = match.get('homeTeam', {}).get('name', '')
            api_away = match.get('awayTeam', {}).get('name', '')
            
            # Enable debug for matching attempts
            home_match = self._teams_match(home_team, api_home, debug=True)
            away_match = self._teams_match(away_team, api_away, debug=True)
            
            # Track potential partial matches for debugging
            home_partial = home_match or \
                          (home_team.lower() in api_home.lower() or api_home.lower() in home_team.lower())
            away_partial = away_match or \
                          (away_team.lower() in api_away.lower() or api_away.lower() in away_team.lower())
            
            if home_partial or away_partial:
                potential_matches.append((api_home, api_away, home_match, away_match))
            
            if home_match and away_match:
                log(f"[DEBUG] ✓ MATCH FOUND: '{home_team}' vs '{away_team}' = '{api_home}' vs '{api_away}'")
                matched = True
                event_id = match.get('id')
                if not event_id:
                    continue
                
                home_score_data = match.get('homeScore', {})
                away_score_data = match.get('awayScore', {})
                
                home_score = home_score_data.get('current', 0)
                away_score = away_score_data.get('current', 0)
                
                status_data = match.get('status', {})
                status_description = status_data.get('description', 'Live')
                
                time_data = match.get('time', {})
                current_minute = self._calculate_game_minute(time_data, status_description)
                
                momentum = self.fetch_game_momentum(event_id)
                
                game_data = LiveGameData(
                    home_team=api_home,
                    away_team=api_away,
                    home_score=home_score,
                    away_score=away_score,
                    event_id=event_id,
                    current_minute=current_minute,
                    status=status_description,
                    momentum=momentum
                )
                
                self._cache[cache_key] = (game_data, datetime.now(timezone.utc))
                
                return game_data
        
        # No match found - show debug info
        if not matched:
            log(f"[DEBUG] ✗ No match for: '{home_team}' vs '{away_team}'")
            if potential_matches:
                log(f"[DEBUG]   Potential partial matches found ({len(potential_matches)} total):")
                for api_home, api_away, h_match, a_match in potential_matches[:10]:  # Show top 10
                    match_status = "✓" if (h_match and a_match) else "~"
                    log(f"    {match_status} {api_home} vs {api_away} (Home: {'✓' if h_match else '✗'}, Away: {'✓' if a_match else '✗'})")
            else:
                log(f"[DEBUG]   No potential matches found in {len(live_matches)} SofaScore games")
        
        return None

