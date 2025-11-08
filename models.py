"""
Data models for the sports betting tracker
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Optional


@dataclass
class GameComment:
    """Single game event comment/commentary"""
    text: str
    event_type: str
    is_home: bool
    time: int
    player_name: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class GameMomentum:
    """Game momentum and statistics data"""
    event_id: int
    possession_home: Optional[int] = None
    possession_away: Optional[int] = None
    attacks_home: Optional[int] = None
    attacks_away: Optional[int] = None
    dangerous_attacks_home: Optional[int] = None
    dangerous_attacks_away: Optional[int] = None
    momentum_direction: Optional[str] = None
    momentum_value: Optional[int] = None
    momentum_graph: Optional[List[Dict]] = None
    recent_comments: Optional[List[GameComment]] = None
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        # Convert GameComment objects to dicts
        if self.recent_comments:
            data['recent_comments'] = [c.to_dict() for c in self.recent_comments]
        return data


@dataclass
class LiveGameData:
    """Live game score and time data"""
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    event_id: int
    current_minute: Optional[int] = None
    status: Optional[str] = None
    momentum: Optional[GameMomentum] = None
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        # Convert momentum to dict
        if self.momentum:
            data['momentum'] = self.momentum.to_dict()
        return data


@dataclass
class PriceData:
    """Price and spread data for a betting outcome"""
    price: Optional[float] = None
    spread: Optional[float] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class MoneylineOutcome:
    """Single outcome in a moneyline market"""
    name: str
    token_id: str
    price_data: PriceData
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'token_id': self.token_id,
            'price': self.price_data.price,
            'spread': self.price_data.spread
        }


@dataclass
class Moneyline:
    """Complete moneyline with all outcomes"""
    outcomes: List[MoneylineOutcome]
    has_draw: bool
    
    def to_dict(self) -> Dict:
        return {
            'has_draw': self.has_draw,
            'outcomes': [o.to_dict() for o in self.outcomes]
        }


@dataclass
class LiveGameResponse:
    """Complete response for a single live game"""
    event_id: str
    event_slug: str
    title: str
    polymarket_url: str
    start_time: str
    home_team: str
    away_team: str
    live_data: Optional[LiveGameData]
    moneyline: Moneyline
    sport: str
    
    def to_dict(self) -> Dict:
        return {
            'event_id': self.event_id,
            'event_slug': self.event_slug,
            'title': self.title,
            'polymarket_url': self.polymarket_url,
            'start_time': self.start_time,
            'home_team': self.home_team,
            'away_team': self.away_team,
            'sport': self.sport,
            'live_data': self.live_data.to_dict() if self.live_data else None,
            'moneyline': self.moneyline.to_dict()
        }

