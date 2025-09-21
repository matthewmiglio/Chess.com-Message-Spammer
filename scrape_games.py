
from chess_driver import ChessDriver, Game

import csv
import os
import random
import time

class GameSaver:
    def __init__(self):
        self.driver = ChessDriver()
        self.fp = 'games.csv'

    def get_random_username(self):
        #if the CSV file doesn't exist yet, just use this username to start
        if not os.path.exists(self.fp):
            return 'bloodxoxo'

        #open the games csv, find the white_player & black_player cols
        #return a random one from a random row

        usernames = set()

        try:
            with open(self.fp, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    if 'white_player' in row and row['white_player']:
                        usernames.add(row['white_player'])
                    if 'black_player' in row and row['black_player']:
                        usernames.add(row['black_player'])
        except Exception as e:
            print(f"Error reading CSV file: {e}")
            return 'bloodxoxo'

        if not usernames:
            return 'bloodxoxo'

        return random.choice(list(usernames))

    def save_game(self, game: Game):
        # Check if this game already exists to avoid duplicates
        existing_urls = set()
        file_exists = os.path.exists(self.fp)

        if file_exists:
            try:
                with open(self.fp, 'r', newline='', encoding='utf-8') as csvfile:
                    reader = csv.DictReader(csvfile)
                    for row in reader:
                        if 'game_url' in row and row['game_url']:
                            existing_urls.add(row['game_url'])
            except Exception as e:
                print(f"Error reading existing CSV file: {e}")

        # Skip if this game URL already exists
        if game.game_url in existing_urls:
            return

        # Define the fieldnames for the CSV
        fieldnames = [
            'game_type', 'time_control', 'white_player', 'white_rating',
            'black_player', 'black_rating', 'result', 'moves', 'date', 'game_url'
        ]

        # Write the game to CSV
        try:
            # If file doesn't exist, create with headers
            if not file_exists:
                with open(self.fp, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()

            # Append the new game
            with open(self.fp, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writerow({
                    'game_type': game.game_type,
                    'time_control': game.time_control,
                    'white_player': game.white_player,
                    'white_rating': game.white_rating,
                    'black_player': game.black_player,
                    'black_rating': game.black_rating,
                    'result': game.result,
                    'moves': game.moves,
                    'date': game.date,
                    'game_url': game.game_url
                })
            print(f"Saved game: {game.white_player} vs {game.black_player}")
        except Exception as e:
            print(f"Error saving game to CSV: {e}")
    
    def scrape(self, scrape_limit = None):
        scrapes = 0
        try:
            while True:
                #pick a random target, given the already scraped games
                username = self.get_random_username()
                print(f"Scraping games for user: {username}")

                try:
                    #scrape games
                    games = self.driver.scrape_games(username)
                    print(f"Found {len(games)} games for {username}")

                    for game in games:
                        #save each game
                        self.save_game(game)
                        scrapes += 1

                        #limit check
                        if scrape_limit and scrapes >= scrape_limit:
                            print(f"Reached scrape limit of {scrape_limit} games")
                            return

                except Exception as e:
                    print(f"Error scraping games for {username}: {e}")
                    # Wait longer on errors to avoid rate limiting
                    time.sleep(5)
                    continue

                # Brief delay between users to be respectful
                time.sleep(2)

        except KeyboardInterrupt:
            print("\nScraping interrupted by user")
        except Exception as e:
            print(f"Error during scraping: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        try:
            self.driver.quit()
            print("Browser cleanup completed")
        except Exception as e:
            print(f"Error during cleanup: {e}")

if __name__ == "__main__":
    saver = GameSaver()
    saver.scrape(scrape_limit=100)  # Set a limit for testing purposes