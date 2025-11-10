#!/bin/bash

# Start script for Locked in API
# Kills any process on port 5001 and starts the Flask app

PORT=5001

echo "Checking for processes on port $PORT..."

# Find and kill any process using the port
PID=$(lsof -ti:$PORT)

if [ ! -z "$PID" ]; then
    echo "Found process $PID on port $PORT. Killing it..."
    kill -9 $PID
    sleep 1
    echo "Process killed."
else
    echo "No process found on port $PORT."
fi

# Activate virtual environment and start the app
echo "Starting Flask app..."
cd "$(dirname "$0")"
source .venv/bin/activate

# Start the app in background and wait a bit for it to start
python app.py &
APP_PID=$!

# Trap Ctrl+C and kill the Flask app properly
trap "echo 'Shutting down Flask app...'; kill $APP_PID 2>/dev/null; exit" INT TERM

# Wait for server to start
sleep 3

# Open browser
echo "Opening browser..."
if command -v open > /dev/null; then
    # macOS
    open "http://localhost:5001"
elif command -v xdg-open > /dev/null; then
    # Linux
    xdg-open "http://localhost:5001"
fi

# Bring Flask app to foreground
wait $APP_PID

