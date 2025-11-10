"""
Simple logging utility that writes to both stdout and a file
"""
import sys
from datetime import datetime
from pathlib import Path

LOG_FILE = Path("logs.txt")

class DualLogger:
    """Logger that writes to both stdout and file"""
    
    def __init__(self, log_file: Path = LOG_FILE):
        self.log_file = log_file
        # Ensure log file exists and is writable
        self.log_file.parent.mkdir(exist_ok=True)
    
    def log(self, message: str):
        """Write message to both stdout and file"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        
        # Write to stdout
        print(log_message, flush=True)
        
        # Write to file
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_message + '\n')
        except Exception as e:
            # If file write fails, at least print the error
            print(f"[ERROR] Failed to write to log file: {e}", file=sys.stderr, flush=True)

# Global logger instance
_logger = DualLogger()

def log(message: str):
    """Convenience function to log messages"""
    _logger.log(message)

def set_log_file(log_file: Path):
    """Change the log file location"""
    global _logger
    _logger = DualLogger(log_file)

