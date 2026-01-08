from send_messages import ChessMessager
from scrape_games import GameSaver
from creds import ChessCreds
from logger import get_logger, log_session_end

import csv
import os
import pandas as pd
import sys
import time
import traceback

MESSAGES_PER_RUN = 3  # Messages per account per run
SCRAPE_BACKOFF_MINUTES = [1, 3, 5]  # Backoff times between retries

def new_recipients_exist(required_count):
    """Check if there are enough new recipients for the given count."""
    games_csv_path = r'games.csv'
    message_log_csv_path = r'message_log.csv'

    # if there is no games file
    # there are no games,
    # then there are no recipients
    if not os.path.exists(games_csv_path):
        return False

    #if there is no message log file,
    #and the length of games it not zero
    #then there must be new recipients
    if not os.path.exists(message_log_csv_path):
        games_df = pd.read_csv(games_csv_path)
        all_players = pd.concat([games_df['white_player'], games_df['black_player']]).unique()
        return len(all_players) >= required_count

    #open both files
    games_df = pd.read_csv(games_csv_path)
    message_log_df = pd.read_csv(message_log_csv_path)

    def user_in_message_log(username):
        return username in message_log_df['recipient'].values

    #count recipients in games that arent in log
    all_players = pd.concat([games_df['white_player'], games_df['black_player']]).unique()
    new_recipient_count = 0
    for player in all_players:
        if not user_in_message_log(player):
            new_recipient_count += 1
            if new_recipient_count >= required_count:
                return True

    return False

def run_scraping_with_retry(logger, scrape_limit=99):
    """Run scraping with retry and backoff logic."""
    for attempt in range(len(SCRAPE_BACKOFF_MINUTES) + 1):
        try:
            game_scraper = GameSaver()
            game_scraper.scrape(scrape_limit=scrape_limit)
            return True
        except Exception as e:
            logger.error(f"Scraping attempt {attempt + 1} failed: {e}")

            if attempt < len(SCRAPE_BACKOFF_MINUTES):
                backoff_minutes = SCRAPE_BACKOFF_MINUTES[attempt]
                logger.info(f"Waiting {backoff_minutes} minute(s) before retry...")
                time.sleep(backoff_minutes * 60)
            else:
                logger.warning("All scraping retries exhausted, continuing without new recipients")
                return False
    return False

def main():
    logger = get_logger()

    try:
        # Load all accounts
        creds_manager = ChessCreds()
        accounts = creds_manager.get_all_accounts()
        num_accounts = len(accounts)
        total_messages_needed = num_accounts * MESSAGES_PER_RUN

        logger.info(f"Loaded {num_accounts} accounts, planning to send {MESSAGES_PER_RUN} messages each ({total_messages_needed} total)")

        logger.info("Checking for new recipients...")
        if not new_recipients_exist(total_messages_needed):
            logger.info("Not enough new recipients found. Starting game scraping session.")
            run_scraping_with_retry(logger, scrape_limit=99)
        else:
            logger.info("Enough new recipients found. Proceeding to messaging.")

        logger.info("Starting message sending session...")

        # Each account sends MESSAGES_PER_RUN messages
        for i, account in enumerate(accounts):
            username = account['username']
            logger.info(f"Account {i + 1}/{num_accounts}: {username}")

            messager = ChessMessager(credentials=account)
            messager.send_messages(limit=MESSAGES_PER_RUN)

            logger.info(f"Account {username} finished sending messages")

        logger.info("Main execution completed successfully.")

    except KeyboardInterrupt:
        logger.info("Program interrupted by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"Unexpected error in main execution: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)
    finally:
        log_session_end()

if __name__ == "__main__":
    main()