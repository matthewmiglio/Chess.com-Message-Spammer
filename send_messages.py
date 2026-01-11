from chess_driver import ChessDriver
from logger import get_logger
import csv
import pandas as pd
import random
import time
from datetime import datetime


class MessageLogger:
    def __init__(
        self,
    ):
        self.fp = "message_log.csv"
        self.cols = [
            "recipient",
            "message",
            "timestamp",
        ]
        self.logger = get_logger()

        # create the file if it doesn't exist
        try:
            with open(self.fp, "x", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=self.cols,
                )
                writer.writeheader()
        except FileExistsError:
            pass

    def is_new_recipient(self, recipient):
        df = pd.read_csv(self.fp)
        is_new = recipient not in df["recipient"].values
        return is_new

    def log_message(self, recipient, message):
        timestamp = datetime.now().isoformat()

        new_entry = {
            "recipient": recipient,
            "message": message,
            "timestamp": timestamp,
        }

        # Append to CSV
        with open(self.fp, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.cols)
            writer.writerow(new_entry)


class ChessMessager:
    def __init__(self, credentials: dict):
        self.credentials = credentials
        self.driver = ChessDriver(credentials=credentials)
        self.games_file = "games.csv"
        self.message_logger = MessageLogger()
        self.logged_in = False
        self.logger = get_logger()

    def close(self):
        """Clean up the browser driver."""
        if self.driver:
            self.driver._cleanup()
            self.driver = None

    def get_random_target(self):
        # load that csv as a pandas df
        df = pd.read_csv(self.games_file)

        # loop until we get a new recipient
        while 1:
            # get a random row
            random_row = df.sample(n=1).iloc[0]
            self.logger.debug(f"Random game: {random_row['white_player']} vs {random_row['black_player']}")

            # check if any of these guys are new recipients
            for player in [random_row["white_player"], random_row["black_player"]]:
                if self.message_logger.is_new_recipient(player):
                    self.logger.info(f"Selected new target: {player}")
                    return player

    def compile_random_ad_message(self):
        greetings = [
            "Hey!",
            "Yo!",
            "Hey man",
            "Hey dude",
            "What's good?",
            "Hey fam",
            "What's up?",
            "How's it going?",
            "Yo",
            "Hey bro",
            "What's happening?",
            "Yo man",
            "Sup",
            "Hey there",
            "Yo dude",
            "Hey buddy",
            "What's going on?",
            "Hi there",
            "Hey friend",
            "Hi!",
        ]

        middles = [
            "I've been working on a chess practice site",
            "I just launched a chess training site I've been building",
            "I've been putting together a site for chess practice",
            "I built a site with chess puzzles and training tools",
            "I put together a chess practice site with daily puzzles",
            "I've been building a place for chess players to train",
            "I'm working on a chess training site",
            "I just finished a site for chess practice",
            "I've been setting up a chess training site",
            "I made a site focused on puzzles and practice",
            "I started a chess practice site",
            "I built a spot for daily puzzles and training",
            "I created a chess training site",
            "I've been working on a site with chess drills",
            "I put together a chess practice site",
            "I built a place for chess puzzles and training",
            "I just launched a site for practice and puzzles",
            "I made a chess training site",
            "I recently finished building a chess practice site",
            "I made a place for chess players to practice",
        ]

        endings = [
            "hope you like it",
            "let me know what you think",
            "would love your thoughts",
            "curious what you think",
            "let me know if it's fun",
            "hope it's useful",
            "check it out if you get a chance",
            "thought you might like it",
            "feel free to try it out",
            "hope you find it helpful",
            "let me know if you have any feedback",
            "would appreciate any feedback",
            "give it a try if you want",
            "hope it helps with your game",
            "thought I'd share it with you",
            "let me know if you like it",
            "hope you enjoy it",
            "tell me what you think",
            "happy to hear your thoughts",
            "would love to know what you think",
        ]

        greeting = random.choice(greetings)
        middle = random.choice(middles)
        ending = random.choice(endings)

        def assemble(greeting, middle, ending):
            needs_comma = not (greeting.endswith("!") or greeting.endswith("?"))
            g = greeting + ("," if needs_comma else "")
            return f"{g} {middle}: https://chesspecker.org {ending}"

        return assemble(greeting, middle, ending)

    def send_random_message(self):
        # log in if not logged in
        if not self.logged_in:
            self.logger.info("Logging into Chess.com...")
            self.driver.login()
            self.logged_in = True
            self.logger.info("Successfully logged in")

        recipient = self.get_random_target()
        message = self.compile_random_ad_message()

        self.logger.log_message_attempt(recipient, message)

        if self.driver.send_message(recipient, message):
            self.message_logger.log_message(recipient, message)
            self.logger.log_message_success(recipient)
            return True
        else:
            self.logger.log_message_failure(recipient, "Unknown error")
            return False

    def send_messages(self, limit=100):
        sends = 0
        self.logger.info(f"Starting message sending session (limit: {limit})")

        while 1:
            if self.send_random_message():
                sends += 1
                self.logger.info(f"Progress: Sent {sends}/{limit} messages")
            if sends >= limit:
                self.logger.info(f"Completed message sending session: {sends} messages sent")
                break

        # Log final statistics
        self.logger.log_stats(
            messages_sent=sends,
            target_limit=limit,
            success_rate=f"{(sends/limit)*100:.1f}%" if limit > 0 else "N/A"
        )

        # Wait for final message to fully send before driver cleanup
        print("Waiting 10s for final message to complete...")
        time.sleep(10)

    def test_compile_random_ad_message(self):
        for _ in range(100):
            print(self.compile_random_ad_message())

    @staticmethod
    def print_random_messages(count=20):
        greetings = [
            "Hey!",
            "Yo!",
            "Hey man",
            "Hey dude",
            "What's good?",
            "Hey fam",
            "What's up?",
            "How's it going?",
            "Yo",
            "Hey bro",
            "What's happening?",
            "Yo man",
            "Sup",
            "Hey there",
            "Yo dude",
            "Hey buddy",
            "What's going on?",
            "Hi there",
            "Hey friend",
            "Hi!",
        ]

        middles = [
            "I've been working on a chess practice site",
            "I just launched a chess training site I've been building",
            "I've been putting together a site for chess practice",
            "I built a site with chess puzzles and training tools",
            "I put together a chess practice site with daily puzzles",
            "I've been building a place for chess players to train",
            "I'm working on a chess training site",
            "I just finished a site for chess practice",
            "I've been setting up a chess training site",
            "I made a site focused on puzzles and practice",
            "I started a chess practice site",
            "I built a spot for daily puzzles and training",
            "I created a chess training site",
            "I've been working on a site with chess drills",
            "I put together a chess practice site",
            "I built a place for chess puzzles and training",
            "I just launched a site for practice and puzzles",
            "I made a chess training site",
            "I recently finished building a chess practice site",
            "I made a place for chess players to practice",
        ]

        endings = [
            "hope you like it",
            "let me know what you think",
            "would love your thoughts",
            "curious what you think",
            "let me know if it's fun",
            "hope it's useful",
            "check it out if you get a chance",
            "thought you might like it",
            "feel free to try it out",
            "hope you find it helpful",
            "let me know if you have any feedback",
            "would appreciate any feedback",
            "give it a try if you want",
            "hope it helps with your game",
            "thought I'd share it with you",
            "let me know if you like it",
            "hope you enjoy it",
            "tell me what you think",
            "happy to hear your thoughts",
            "would love to know what you think",
        ]

        def assemble(greeting, middle, ending):
            needs_comma = not (greeting.endswith("!") or greeting.endswith("?"))
            g = greeting + ("," if needs_comma else "")
            return f"{g} {middle}: https://chesspecker.org {ending}"

        print(f"=== {count} Random Messages ===\n")
        for i in range(count):
            g = random.choice(greetings)
            m = random.choice(middles)
            e = random.choice(endings)
            msg = assemble(g, m, e)
            print(f"[{i+1}] {msg}")
        print()


if __name__ == "__main__":
    ChessMessager.print_random_messages(20)
