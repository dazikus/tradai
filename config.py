"""
Application configuration
"""


class Config:
    """Application configuration"""
    # Polymarket APIs
    GAMMA_API = "https://gamma-api.polymarket.com"
    CLOB_API = "https://clob.polymarket.com"
    POLYMARKET_EVENT_URL = "https://polymarket.com/event"
    
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
    
    # Flask config
    FLASK_HOST = '0.0.0.0'
    FLASK_PORT = 5001
    FLASK_DEBUG = False

