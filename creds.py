import json
import os
import sys


class ChessCreds:
    PLACEHOLDER_VALUES = {"your_username", "your_password", "your_username_1", "your_password_1",
                          "your_username_2", "your_password_2", "your_username_3", "your_password_3"}

    def __init__(self):
        self.fp = 'chess_creds.json'
        if not os.path.exists(self.fp):
            placeholder_content = {
                "accounts": [
                    {"username": "your_username_1", "password": "your_password_1"},
                    {"username": "your_username_2", "password": "your_password_2"},
                    {"username": "your_username_3", "password": "your_password_3"},
                ]
            }
            with open(self.fp, 'w') as f:
                json.dump(placeholder_content, f, indent=4)
            print(f"\nCreated credentials file: {self.fp}")
            print("Please fill in your chess.com account credentials, then run again.")
            print("You can add or remove accounts as needed.")
            sys.exit(0)

        self._check_for_placeholders()

    def _check_for_placeholders(self):
        with open(self.fp, 'r') as f:
            data = json.load(f)

        accounts = data.get("accounts", [])
        if not accounts:
            print(f"\nNo accounts found in: {self.fp}")
            print("Please add at least one account.")
            sys.exit(0)

        for i, account in enumerate(accounts):
            if account.get("username") in self.PLACEHOLDER_VALUES or account.get("password") in self.PLACEHOLDER_VALUES:
                print(f"\nPlease fill out your credentials in: {self.fp}")
                print(f"Account {i + 1} still has placeholder values.")
                sys.exit(0)

    def valid_creds(self, creds: dict):
        expected_creds = ["username", "password"]
        return all(key in creds for key in expected_creds)

    def get_all_accounts(self):
        with open(self.fp, 'r') as f:
            data = json.load(f)

        accounts = data.get("accounts", [])
        valid_accounts = []
        for account in accounts:
            if self.valid_creds(account):
                valid_accounts.append(account)
            else:
                raise ValueError(f"Fatal error: invalid credentials format for account: {account}")

        return valid_accounts

    def get_creds(self):
        """Returns the first account for backwards compatibility"""
        accounts = self.get_all_accounts()
        if accounts:
            return accounts[0]
        raise ValueError("Fatal error: no valid credentials found")
