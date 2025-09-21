from send_messages import ChessMessager

from scrape_games import GameSaver

import csv
import os
import pandas as pd

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
        return username in message_log_df['username'].values
    
    #if there are recipients in games that arent in log, we're good to move on
    all_players = pd.concat([games_df['white_player'], games_df['black_player']]).unique()
    for player in all_players:
        if not user_in_message_log(player):
            return True

    return False

if __name__ == "__main__":
    if not new_recipients_exist():
        print("No new recipients found. Scraping some.")
        game_scraper = GameSaver()
        game_scraper.scrape(scrape_limit=101)
    
    messager = ChessMessager()
    messager.send_messages(limit=1)