"""
Sport-specific logic (Strategy Pattern)
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone

from config import Config


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
    def has_draw_option(self) -> bool:
        """Return whether this sport has draw/tie outcomes"""
        pass
    
    def extract_teams_from_title(self, title: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract home and away team names from event title.
        Default implementation assumes format: "Team A vs. Team B" or "Team A vs Team B"
        """
        title_lower = title.lower()
        
        for separator in [' vs. ', ' vs ', ' v ']:
            if separator in title_lower:
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
        Check if event is potentially live.
        We do minimal filtering here since SofaScore is the real source of truth.
        """
        if event.get('closed', False):
            return False
        
        start_time_str = event.get('startTime') or event.get('eventDate')
        if not start_time_str:
            return False
        
        try:
            start_time = datetime.fromisoformat(str(start_time_str).replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            
            return start_time <= now
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
    
    def is_sport_event(self, event: Dict) -> bool:
        """Check if event is a soccer game"""
        title = event.get('title', '')
        title_lower = title.lower()
        
        has_fc = 'fc' in title_lower or 'f.c.' in title_lower
        has_soccer_terms = any(term in title_lower for term in [
            'united', 'city fc', 'athletic', 'sporting', 'real ', 'club ',
            'wanderers', 'glory', 'mariners', 'victory', 'rovers'
        ])
        
        is_soccer = has_fc or has_soccer_terms
        
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
        return False
    
    def is_sport_event(self, event: Dict) -> bool:
        """Check if event is an NHL game"""
        title = event.get('title', '').lower()
        
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
        is_soccer = 'fc' in title or any(term in title for term in ['united', 'city fc'])
        
        return has_nhl_term and not is_soccer

