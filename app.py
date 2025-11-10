"""
Flask REST API for live sports betting tracker with JWT auth and caching
"""

from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
from datetime import datetime, timezone, timedelta
import os

from config import Config
from services import SoccerSport, NHLSport, SofaScoreProvider, LiveSportsTracker
from auth import generate_token, require_auth, verify_credentials

app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = Config.SECRET_KEY
CORS(app)  # Enable CORS for all routes

# Initialize services
try:
    sports = [
        SoccerSport(),
        # NHLSport(),  # Uncomment to add NHL tracking
    ]
    
    score_provider = SofaScoreProvider()
    tracker = LiveSportsTracker(sports, score_provider)
except Exception as e:
    print(f"[WARNING] Service initialization failed: {e}")
    # Set to None - will be handled gracefully in routes
    sports = []
    score_provider = None
    tracker = None

# In-memory cache for live games data (works in serverless with short TTL)
games_cache = {
    'data': None,
    'last_updated': None,
    'is_fetching': False
}

# Cache TTL: refresh every 45 seconds
CACHE_TTL_SECONDS = 45


def fetch_and_cache_data():
    """Fetch and cache live games data"""
    global games_cache
    
    if games_cache['is_fetching'] or tracker is None:
        return  # Skip if already fetching or tracker not initialized
    
    try:
        games_cache['is_fetching'] = True
        print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Fetching live games data...")
        
        data = tracker.get_all_live_games()
        games_cache['data'] = data
        games_cache['last_updated'] = datetime.now(timezone.utc)
        
        print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Cache updated. Games: {data.get('total_games', 0)}")
        
    except Exception as e:
        print(f"[ERROR] Failed to fetch data: {e}")
        # Don't crash - just log and continue with empty cache
    finally:
        games_cache['is_fetching'] = False


def should_refresh_cache() -> bool:
    """Check if cache should be refreshed"""
    if games_cache['data'] is None:
        return True
    
    if games_cache['last_updated'] is None:
        return True
    
    age = (datetime.now(timezone.utc) - games_cache['last_updated']).total_seconds()
    return age >= CACHE_TTL_SECONDS


@app.route('/api/login', methods=['POST'])
def login():
    """
    POST /api/login
    
    Authenticate user and return JWT token.
    Request body: {"username": "admin", "password": "admin"}
    """
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    if verify_credentials(username, password):
        token = generate_token(username)
        return jsonify({
            'token': token,
            'username': username,
            'expires_in_days': Config.JWT_EXPIRY_DAYS
        }), 200
    else:
        return jsonify({'error': 'Invalid credentials'}), 401


@app.route('/api/refresh', methods=['GET', 'POST'])
def refresh_cache():
    """
    GET/POST /api/refresh (Public - for Vercel Cron)
    
    Manually trigger cache refresh. Called by Vercel Cron every 45 seconds.
    """
    fetch_and_cache_data()
    return jsonify({
        'status': 'refreshed',
        'games': games_cache['data'].get('total_games', 0) if games_cache['data'] else 0,
        'timestamp': games_cache['last_updated'].isoformat() if games_cache['last_updated'] else None
    }), 200


@app.route('/api/live-games', methods=['GET'])
@require_auth
def get_live_games():
    """
    GET /api/live-games (Protected)
    
    Returns cached live games data. Refreshes if cache is stale (>45 seconds old).
    """
    # Refresh cache if stale (on-demand refresh for serverless)
    if should_refresh_cache():
        fetch_and_cache_data()
    
    if games_cache['data'] is None:
        return jsonify({
            'error': 'Data not yet available',
            'message': 'Server is fetching initial data, please retry in a few seconds'
        }), 503
    
    # Return cached data with cache timestamp
    response_data = games_cache['data'].copy()
    response_data['cached_at'] = games_cache['last_updated'].isoformat() if games_cache['last_updated'] else None
    response_data['is_live_cache'] = True
    
    return jsonify(response_data), 200


@app.route('/api/health', methods=['GET'])
def health_check():
    """
    GET /api/health (Public)
    
    Health check endpoint - does not require authentication.
    """
    cache_age = None
    if games_cache['last_updated']:
        cache_age = (datetime.now(timezone.utc) - games_cache['last_updated']).total_seconds()
    
    return jsonify({
        'status': 'healthy',
        'cache_status': 'populated' if games_cache['data'] else 'empty',
        'cache_age_seconds': cache_age,
        'is_fetching': games_cache['is_fetching']
    }), 200


@app.route('/')
def index():
    """Serve the login page (public) or redirect authenticated users"""
    return send_from_directory('static', 'login.html')


@app.route('/app')
def app_page():
    """Serve the main app interface (requires valid token in localStorage)"""
    return send_from_directory('static', 'index.html')


@app.route('/static/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory('static', path)


if __name__ == '__main__':
    print("=" * 80)
    print("Live Sports Betting Tracker")
    print("=" * 80)
    print(f"\nStarting server on {Config.FLASK_HOST}:{Config.FLASK_PORT}")
    print(f"\n🌐 Web Interface:")
    print(f"  http://localhost:{Config.FLASK_PORT}/")
    print(f"\n📡 API Endpoints:")
    print(f"  - GET  http://localhost:{Config.FLASK_PORT}/api/health")
    print(f"  - GET  http://localhost:{Config.FLASK_PORT}/api/live-games")
    print(f"\nPress Ctrl+C to stop")
    print("=" * 80 + "\n")
    
    app.run(
        host=Config.FLASK_HOST,
        port=Config.FLASK_PORT,
        debug=Config.FLASK_DEBUG
    )

