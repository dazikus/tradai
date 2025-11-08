# 🔐 Authentication & Caching System

## Features Implemented

### 1. JWT Authentication
- **Login Page**: Modern, sleek login page at `/`
- **Protected Routes**: All API endpoints (except `/api/health` and `/api/login`) require authentication
- **Credentials**: `admin` / `admin` (configurable in `config.py`)
- **Token Expiry**: 7 days (configurable)
- **Auto-logout**: Redirects to login on token expiry

### 2. Server-Side Caching
- **Background Refresh**: Server fetches data every 30-60 seconds (randomized)
- **User Reads from Cache**: No user request triggers web scraping
- **Single Source**: Only one server process scrapes APIs, all users read from cache
- **Efficient**: Reduces API load and improves response time

### 3. Random Auto-Refresh
- **Client-Side**: Each user's browser refreshes every 30-60 seconds (random)
- **Server-Side**: Background job refreshes every 30-60 seconds (random)
- **No Sync Issues**: Client reads cached data, no race conditions

### 4. UI Enhancements
- **Logout Button**: Added to header with logout icon
- **Auth Redirect**: Seamless redirect to login if not authenticated
- **Token in LocalStorage**: Persists across browser sessions for 7 days

## How It Works

### Authentication Flow
1. User visits `/` → Login page
2. User enters `admin:admin`
3. Server generates JWT token (valid 7 days)
4. Token stored in localStorage
5. User redirected to `/app`
6. All API requests include `Authorization: Bearer <token>` header
7. On 401 error → Auto-logout and redirect to login

### Data Flow
```
Server Background Job (30-60s random) 
    ↓
Fetch from Polymarket & SofaScore APIs
    ↓
Store in Memory Cache
    ↓
User Requests /api/live-games
    ↓
Return Cached Data (instant response)
```

### Client Refresh
```
User Clicks Refresh OR Auto-refresh Timer
    ↓
Call /api/live-games (with auth token)
    ↓
Receive cached data from server
    ↓
Update UI
    ↓
Schedule next random refresh (30-60s)
```

## Default Credentials

**Username**: `admin`  
**Password**: `admin`

⚠️ **Change these in production!** Update `ADMIN_USERNAME` and `ADMIN_PASSWORD` in `config.py`

## Configuration

All settings in `config.py`:

```python
# Authentication
SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me')
JWT_EXPIRY_DAYS = 7
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin'

# Refresh intervals
MIN_REFRESH_INTERVAL = 30  # seconds
MAX_REFRESH_INTERVAL = 60  # seconds
```

## Security Notes

1. **HTTPS**: Always use HTTPS in production (Render.com does this automatically)
2. **Secret Key**: Set `SECRET_KEY` environment variable on Render
3. **Credentials**: Use environment variables for credentials in production
4. **Token Storage**: Tokens stored in localStorage (consider httpOnly cookies for better security)

## Routes

### Public
- `GET /` - Login page
- `GET /api/health` - Health check
- `POST /api/login` - Login endpoint

### Protected (Requires JWT)
- `GET /app` - Main application
- `GET /api/live-games` - Get cached live games data
- `GET /static/*` - Static assets (JS, CSS)

## Deployment Notes

- Cache is in-memory, so it resets on server restart
- First request after restart may take a few seconds while cache populates
- Background job starts automatically on server start
- APScheduler handles job scheduling

