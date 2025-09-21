import requests

def fetch_games(username, filename="games.html"):
    url = f"https://www.chess.com/member/{username}/games"
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; MyChessBot/1.0; +https://yourdomain.example)",
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()  # raises HTTPError if status is 4xx/5xx

    # Write the response content to a file
    with open(filename, "w", encoding="utf-8") as f:
        f.write(response.text)

    print(f"Saved games page for {username} to {filename}")

if __name__ == "__main__":
    fetch_games("bloodxoxo")
