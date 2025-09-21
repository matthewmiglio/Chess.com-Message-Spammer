




import json
import os


class ChessCreds:
    def __init__(self):
        self.fp = 'chess_creds.json'
        if not os.path.exists(self.fp):
            placeholder_content = {
                "username": "your_username",
                "password": "your_password"
            }
            with open(self.fp, 'w') as f:
                json.dump(placeholder_content, f, indent=4)

    def valid_creds(self,creds:dict):
        expected_creds = ["username", "password"]
        return all(key in creds for key in expected_creds)

    def get_creds(self):
        with open(self.fp, 'r') as f:
            creds = json.load(f)
        if self.valid_creds(creds):
            return creds
        else:
            raise ValueError("Fatal error: invalid credentials format")