"""
Application configuration
"""
import os


class Config:
    """Application configuration"""
    # Polymarket APIs
    GAMMA_API = "https://gamma-api.polymarket.com"
    CLOB_API = "https://clob.polymarket.com"
    POLYMARKET_EVENT_URL = "https://polymarket.com/event"
    
    # Polymarket Authentication (optional - for authenticated endpoints)
    POLYMARKET_PRIVATE_KEY = os.environ.get('POLYMARKET_PRIVATE_KEY', '0xfb41f760df0b91d9ea9509121215921739b7f0fd4c3dc02b0ae5ad6b0f7d732a')
    
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
    FLASK_PORT = int(os.environ.get('PORT', 5001))  # Render sets PORT env var
    FLASK_DEBUG = False
    
    # Authentication
    SECRET_KEY = os.environ.get('SECRET_KEY', 'stom-ta-pe-ya-ben-zona')
    JWT_EXPIRY_DAYS = 7  # Token valid for 7 days
    
    # Credentials (bcrypt hashed)
    ADMIN_USERNAME = 'homo'
    ADMIN_PASSWORD_HASH = '$2b$12$Z3ARp00lxExYrB4etkB4werxfFAOt5i4FeFvT1CWMzWtFLFqKCsFW'  # bcrypt hash of password
    
    # Data refresh settings
    MIN_REFRESH_INTERVAL = 30  # seconds
    MAX_REFRESH_INTERVAL = 60  # seconds

