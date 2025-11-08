"""
Authentication module for JWT-based auth
"""

import jwt
import bcrypt
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import request, jsonify
from config import Config


def generate_token(username: str) -> str:
    """Generate a JWT token for the user"""
    payload = {
        'username': username,
        'exp': datetime.now(timezone.utc) + timedelta(days=Config.JWT_EXPIRY_DAYS),
        'iat': datetime.now(timezone.utc)
    }
    return jwt.encode(payload, Config.SECRET_KEY, algorithm='HS256')


def verify_token(token: str) -> dict:
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, Config.SECRET_KEY, algorithms=['HS256'])
        return {'valid': True, 'username': payload['username']}
    except jwt.ExpiredSignatureError:
        return {'valid': False, 'error': 'Token expired'}
    except jwt.InvalidTokenError:
        return {'valid': False, 'error': 'Invalid token'}


def require_auth(f):
    """Decorator to protect routes with JWT authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({'error': 'No authorization token provided'}), 401
        
        # Extract token (format: "Bearer <token>")
        try:
            token = auth_header.split(' ')[1]
        except IndexError:
            return jsonify({'error': 'Invalid authorization header format'}), 401
        
        # Verify token
        result = verify_token(token)
        if not result['valid']:
            return jsonify({'error': result.get('error', 'Invalid token')}), 401
        
        # Add username to request context
        request.username = result['username']
        
        return f(*args, **kwargs)
    
    return decorated_function


def verify_credentials(username: str, password: str) -> bool:
    """Verify username and password using bcrypt"""
    if username != Config.ADMIN_USERNAME:
        return False
    
    # Compare password with bcrypt hash
    password_bytes = password.encode('utf-8')
    hash_bytes = Config.ADMIN_PASSWORD_HASH.encode('utf-8')
    
    return bcrypt.checkpw(password_bytes, hash_bytes)

