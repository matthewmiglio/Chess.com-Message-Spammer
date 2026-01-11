import logging
import os
from datetime import datetime
from pathlib import Path


class SessionLogger:
    MAX_LOG_FILES = 50
    CLEANUP_COUNT = 10

    def __init__(self):
        self.start_time = datetime.now()
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)

        # Clean up old logs if we have too many
        self._cleanup_old_logs()

        # Format: 21_Sept_2025_13_34.log
        timestamp = self.start_time.strftime("%d_%b_%Y_%H_%M")
        self.log_file = self.log_dir / f"{timestamp}.log"

    def _cleanup_old_logs(self):
        """Remove oldest log files if we exceed MAX_LOG_FILES."""
        log_files = sorted(self.log_dir.glob("*.log"), key=lambda f: f.stat().st_mtime)

        if len(log_files) >= self.MAX_LOG_FILES:
            files_to_delete = log_files[:self.CLEANUP_COUNT]
            for f in files_to_delete:
                try:
                    f.unlink()
                    print(f"Deleted old log: {f.name}")
                except Exception as e:
                    print(f"Failed to delete {f.name}: {e}")

        # Configure logging
        self.logger = logging.getLogger("chess_bot")
        self.logger.setLevel(logging.INFO)

        # Clear any existing handlers
        self.logger.handlers.clear()

        # File handler
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )

        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

        # Log session start
        self.logger.info("=" * 60)
        self.logger.info(f"CHESS BOT SESSION STARTED - {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"Log file: {self.log_file}")
        self.logger.info("=" * 60)

    def info(self, message):
        self.logger.info(message)

    def warning(self, message):
        self.logger.warning(message)

    def error(self, message):
        self.logger.error(message)

    def debug(self, message):
        self.logger.debug(message)

    def log_session_end(self):
        end_time = datetime.now()
        duration = end_time - self.start_time

        self.logger.info("=" * 60)
        self.logger.info(f"SESSION ENDED - {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"Total runtime: {duration}")
        self.logger.info("=" * 60)

    def log_scraping_start(self, username):
        self.logger.info(f"Starting to scrape games for user: {username}")

    def log_scraping_found(self, username, count):
        self.logger.info(f"Found {count} games for {username}")

    def log_scraping_limited(self, original, limited):
        self.logger.info(f"Limiting to first {limited} games (found {original} total)")

    def log_game_success(self, game_num, total, white_player, black_player, time_taken):
        self.logger.info(f"Game {game_num}/{total} - SUCCESS: {white_player} vs {black_player} ({time_taken:.2f}s)")

    def log_game_skip(self, game_num, total, reason, time_taken):
        self.logger.warning(f"Game {game_num}/{total} - SKIP: {reason} ({time_taken:.2f}s)")

    def log_game_timeout(self, game_num, total, element, fallback):
        self.logger.warning(f"Game {game_num}/{total} - TIMEOUT: {element}, using '{fallback}'")

    def log_game_error(self, game_num, total, error, time_taken):
        self.logger.error(f"Game {game_num}/{total} - ERROR: {error} ({time_taken:.2f}s)")

    def log_scraping_error(self, username, error):
        self.logger.error(f"Error scraping games for {username}: {error}")

    def log_message_attempt(self, recipient, message):
        self.logger.info(f"Attempting to send message to {recipient}: {message[:50]}...")

    def log_message_success(self, recipient):
        self.logger.info(f"Successfully sent message to {recipient}")

    def log_message_failure(self, recipient, error):
        self.logger.error(f"Failed to send message to {recipient}: {error}")

    def log_new_recipient_check(self, recipient, is_new):
        status = "NEW" if is_new else "EXISTING"
        self.logger.info(f"Recipient check: {recipient} - {status}")

    def log_browser_operation(self, operation):
        self.logger.debug(f"Browser: {operation}")

    def log_stats(self, **stats):
        self.logger.info("Session Statistics:")
        for key, value in stats.items():
            self.logger.info(f"  {key}: {value}")


# Global logger instance
_session_logger = None

def get_logger():
    global _session_logger
    if _session_logger is None:
        _session_logger = SessionLogger()
    return _session_logger

def log_session_end():
    global _session_logger
    if _session_logger:
        _session_logger.log_session_end()