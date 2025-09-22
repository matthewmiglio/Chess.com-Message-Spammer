from send_messages import ChessMessager
from scrape_games import GameSaver
from logger import get_logger, log_session_end

import csv
import os
import pandas as pd
import sys
import traceback

def new_recipients_exist():
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
        if len(games_df) > 0:
            return True
        else:
            return False

    #open both files
    games_df = pd.read_csv(games_csv_path)
    message_log_df = pd.read_csv(message_log_csv_path)

    def user_in_message_log(username):
        return username in message_log_df['recipient'].values
    
    #if there are recipients in games that arent in log, we're good to move on
    all_players = pd.concat([games_df['white_player'], games_df['black_player']]).unique()
    for player in all_players:
        if not user_in_message_log(player):
            return True

    return False

def main():
    logger = get_logger()

    try:
        logger.info("Checking for new recipients...")
        if not new_recipients_exist():
            logger.info("No new recipients found. Starting game scraping session.")
            game_scraper = GameSaver()
            game_scraper.scrape(scrape_limit=101)
        else:
            logger.info("New recipients found. Proceeding to messaging.")

        logger.info("Starting message sending session...")
        messager = ChessMessager()
        messager.send_messages(limit=2)

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