"""
Flask REST API for live sports betting tracker
"""

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import os

from config import Config
from services import SoccerSport, NHLSport, SofaScoreProvider, LiveSportsTracker

app = Flask(__name__, static_folder='static')
CORS(app)  # Enable CORS for all routes

# Initialize services
sports = [
    SoccerSport(),
    # NHLSport(),  # Uncomment to add NHL tracking
]

score_provider = SofaScoreProvider()
tracker = LiveSportsTracker(sports, score_provider)


@app.route('/api/live-games', methods=['GET'])
def get_live_games():
    """
    GET /api/live-games
    
    Returns JSON with all currently live games, including:
    - Event details (title, Polymarket link, start time)
    - Team names
    - Live score and game time from SofaScore
    - Betting odds from Polymarket
    - Game momentum, possession, and statistics
    - Recent game events/commentary
    
    Response format:
    {
        "timestamp": "2025-11-08T15:30:00Z",
        "total_games": 5,
        "sports": {
            "Soccer": {
                "total_found": 10,
                "total_live": 5,
                "games": [
                    {
                        "event_id": "...",
                        "event_slug": "...",
                        "title": "Team A vs Team B",
                        "polymarket_url": "https://polymarket.com/event/...",
                        "start_time": "2025-11-08T15:00:00Z",
                        "home_team": "Team A",
                        "away_team": "Team B",
                        "sport": "Soccer",
                        "live_data": {
                            "home_score": 1,
                            "away_score": 0,
                            "current_minute": 35,
                            "status": "1st half",
                            "momentum": {
                                "possession_home": 55,
                                "possession_away": 45,
                                "attacks_home": 15,
                                "attacks_away": 8,
                                "dangerous_attacks_home": 5,
                                "dangerous_attacks_away": 2,
                                "momentum_direction": "home",
                                "momentum_value": 25,
                                "momentum_graph": [...],
                                "recent_comments": [...]
                            }
                        },
                        "moneyline": {
                            "has_draw": true,
                            "outcomes": [
                                {"name": "Team A", "price": 0.45, "spread": 0.04},
                                {"name": "Draw", "price": 0.30, "spread": 0.03},
                                {"name": "Team B", "price": 0.25, "spread": 0.03}
                            ]
                        }
                    }
                ]
            }
        }
    }
    """
    try:
        data = tracker.get_all_live_games()
        return jsonify(data), 200
    except Exception as e:
        return jsonify({
            'error': 'Failed to fetch live games',
            'message': str(e)
        }), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """
    GET /api/health
    
    Health check endpoint to verify API and dependencies are working.
    """
    try:
        # Check SofaScore API
        score_provider.check_health()
        
        return jsonify({
            'status': 'healthy',
            'sofascore': 'connected',
            'polymarket': 'connected'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 503


@app.route('/')
def index():
    """Serve the web interface"""
    return send_from_directory('static', 'index.html')


@app.route('/<path:path>')
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

