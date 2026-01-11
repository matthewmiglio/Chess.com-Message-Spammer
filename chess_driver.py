# reddit_scraper.py
import contextlib
import atexit
import json
import logging
import os
import random
import re
import shutil
import socket
import tempfile
import time
from dataclasses import dataclass, asdict
from typing import List, Optional

import undetected_chromedriver as uc
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    SessionNotCreatedException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from logger import get_logger

CHESS_LOGIN_PAGE_URL = 'https://www.chess.com/login_and_go'

# ----------------------------
# Global noise suppression
# ----------------------------
logging.basicConfig(level=logging.ERROR)
logging.getLogger("WDM").setLevel(logging.CRITICAL)  # webdriver_manager

# Quiet environment logs (absl / TF / OpenBLAS etc.)
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("ABSL_LOG_LEVEL", "3")
os.environ.setdefault("OPENBLAS_VERBOSE", "0")


@dataclass
class Game:
    game_type: str
    time_control: str
    white_player: str
    white_rating: str
    black_player: str
    black_rating: str
    result: str
    moves: str
    date: str
    game_url: str



def _get_free_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port




class ChessDriver:
    def __init__(
        self,
        credentials: dict = None,
        headless: bool = False,
        page_load_timeout: int = 30,
        implicit_wait: int = 5,
    ):
        self.credentials = credentials
        self.chrome_process_id = None
        self._tmp_user_data_dir = tempfile.mkdtemp(prefix="selenium_chrome_profile_")
        atexit.register(self._cleanup)
        self.logger = get_logger()
        if credentials:
            print(f'Using credentials for user {credentials["username"]}')

        chrome_options = uc.ChromeOptions()
        # Quiet flags
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-logging")
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument("--no-default-browser-check")
        chrome_options.add_argument("--no-first-run")
        chrome_options.add_argument("--disable-crash-reporter")
        chrome_options.add_argument("--disable-in-process-stack-traces")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-notifications")

        if headless:
            chrome_options.add_argument("--headless=new")

        try:
            self.logger.log_browser_operation("Initializing Chrome browser (undetected)")
            with contextlib.redirect_stderr(open(os.devnull, "w")):
                self.driver = uc.Chrome(
                    options=chrome_options,
                    user_data_dir=self._tmp_user_data_dir,
                    use_subprocess=True,
                )
                # Track the Chrome process ID for targeted cleanup
                self.chrome_process_id = self.driver.browser_pid if hasattr(self.driver, 'browser_pid') else None
            self.logger.log_browser_operation(f"Chrome browser initialized (PID: {self.chrome_process_id})")
        except SessionNotCreatedException:
            # retry once with a fresh dir
            self.logger.log_browser_operation("Retrying Chrome initialization with fresh configuration")
            self._cleanup()
            self._tmp_user_data_dir = tempfile.mkdtemp(prefix="selenium_chrome_profile_retry_")
            with contextlib.redirect_stderr(open(os.devnull, "w")):
                self.driver = uc.Chrome(
                    options=chrome_options,
                    user_data_dir=self._tmp_user_data_dir,
                    use_subprocess=True,
                )
                self.chrome_process_id = self.driver.browser_pid if hasattr(self.driver, 'browser_pid') else None
            self.logger.log_browser_operation(f"Chrome browser retry successful (PID: {self.chrome_process_id})")

        self.driver.set_page_load_timeout(page_load_timeout)
        self.driver.implicitly_wait(implicit_wait)

        # Spoof browser fingerprint to hide VM detection
        self._apply_fingerprint_spoofing()

    def _apply_fingerprint_spoofing(self):
        """Inject script to spoof various browser fingerprints to hide VM."""
        spoof_script = """
        // Spoof WebGL renderer/vendor
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) return 'Intel Inc.';
            if (parameter === 37446) return 'Intel Iris OpenGL Engine';
            return getParameter.call(this, parameter);
        };
        const getParameter2 = WebGL2RenderingContext.prototype.getParameter;
        WebGL2RenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) return 'Intel Inc.';
            if (parameter === 37446) return 'Intel Iris OpenGL Engine';
            return getParameter2.call(this, parameter);
        };

        // Spoof hardware concurrency (CPU cores)
        Object.defineProperty(navigator, 'hardwareConcurrency', {
            get: () => 12
        });

        // Spoof device memory (GB)
        Object.defineProperty(navigator, 'deviceMemory', {
            get: () => 8
        });

        // Spoof screen resolution
        Object.defineProperty(screen, 'width', { get: () => 1920 });
        Object.defineProperty(screen, 'height', { get: () => 1080 });
        Object.defineProperty(screen, 'availWidth', { get: () => 1920 });
        Object.defineProperty(screen, 'availHeight', { get: () => 1040 });

        // Spoof timezone to America/New_York
        const originalDateTimeFormat = Intl.DateTimeFormat;
        Intl.DateTimeFormat = function(locales, options) {
            options = options || {};
            options.timeZone = options.timeZone || 'America/New_York';
            return new originalDateTimeFormat(locales, options);
        };
        Intl.DateTimeFormat.prototype = originalDateTimeFormat.prototype;
        Intl.DateTimeFormat.supportedLocalesOf = originalDateTimeFormat.supportedLocalesOf;

        // Also override Date to use Eastern timezone offset (-5 or -4 for DST)
        const originalGetTimezoneOffset = Date.prototype.getTimezoneOffset;
        Date.prototype.getTimezoneOffset = function() {
            // Return offset for Eastern Time (300 = UTC-5, 240 = UTC-4 DST)
            const month = this.getMonth();
            // Rough DST check (March-November)
            if (month >= 2 && month <= 10) return 240;
            return 300;
        };
        """
        try:
            self.driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": spoof_script}
            )
            self.logger.log_browser_operation("Browser fingerprint spoofing enabled")
        except Exception as e:
            self.logger.warning(f"Failed to apply fingerprint spoofing: {e}")

    # --- lifecycle
    def _cleanup(self):
        try:
            if hasattr(self, "driver") and self.driver:
                try:
                    # Close all windows first
                    for handle in self.driver.window_handles:
                        self.driver.switch_to.window(handle)
                        self.driver.close()
                except Exception:
                    pass

                try:
                    # Quit the driver
                    self.driver.quit()
                except Exception as e:
                    print(f"Error during driver quit: {e}")
                finally:
                    self.driver = None

            # Target only our specific Chrome process if we have its PID
            self._kill_specific_chrome_process()

        finally:
            # Clean up temp directory
            if getattr(self, "_tmp_user_data_dir", None) and os.path.isdir(self._tmp_user_data_dir):
                try:
                    shutil.rmtree(self._tmp_user_data_dir, ignore_errors=True)
                except Exception as e:
                    print(f"Error cleaning temp directory: {e}")

    def _kill_specific_chrome_process(self):
        """Kill only the specific Chrome process we launched, not all Chrome processes"""
        if not self.chrome_process_id:
            return

        try:
            import subprocess
            import platform
            import psutil

            # Use psutil for more precise process management
            try:
                process = psutil.Process(self.chrome_process_id)
                # Check if it's actually a chrome process
                if "chrome" in process.name().lower():
                    # Kill child processes first
                    for child in process.children(recursive=True):
                        try:
                            child.terminate()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass

                    # Then kill the main process
                    process.terminate()
                    process.wait(timeout=5)  # Wait up to 5 seconds

                    print(f"Successfully terminated Chrome process {self.chrome_process_id}")

            except psutil.NoSuchProcess:
                # Process already terminated
                pass
            except psutil.TimeoutExpired:
                # If terminate doesn't work, force kill
                try:
                    process.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            except ImportError:
                # Fallback if psutil is not available
                self._fallback_kill_process()

        except Exception as e:
            print(f"Error killing specific Chrome process {self.chrome_process_id}: {e}")
        finally:
            self.chrome_process_id = None

    def _fallback_kill_process(self):
        """Fallback method if psutil is not available"""
        if not self.chrome_process_id:
            return

        try:
            import subprocess
            import platform

            if platform.system() == "Windows":
                subprocess.run(["taskkill", "/f", "/pid", str(self.chrome_process_id)],
                             capture_output=True, check=False)
            else:
                subprocess.run(["kill", "-9", str(self.chrome_process_id)],
                             capture_output=True, check=False)
        except Exception:
            pass

    def quit(self):
        self._cleanup()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self._cleanup()

    def _safe_text(self, by: By, selector: str) -> Optional[str]:
        try:
            el = self.driver.find_element(by, selector)
            return el.text.strip()
        except NoSuchElementException:
            return None

    def _safe_attr(self, by: By, selector: str, attr: str) -> Optional[str]:
        try:
            el = self.driver.find_element(by, selector)
            return el.get_attribute(attr)
        except NoSuchElementException:
            return None

 
    # --- scraping
    def _human_type(self, element, text):
        """Type text character by character with random delays to mimic human typing."""
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.05, 0.15))

    def login(self):
        if not self.credentials:
            raise ValueError("No credentials provided for login")

        username = self.credentials['username']
        password = self.credentials['password']

        self.driver.get(CHESS_LOGIN_PAGE_URL)

        # Random delay after page load
        time.sleep(random.uniform(1.0, 2.0))

        wait = WebDriverWait(self.driver, 10)

        username_field = wait.until(
            EC.presence_of_element_located((By.ID, "login-username"))
        )
        username_field.clear()
        time.sleep(random.uniform(0.3, 0.7))
        self._human_type(username_field, username)

        # Random delay before moving to password field
        time.sleep(random.uniform(0.5, 1.0))

        password_field = self.driver.find_element(By.ID, "login-password")
        password_field.clear()
        time.sleep(random.uniform(0.3, 0.7))
        self._human_type(password_field, password)

        # Random delay before clicking login
        time.sleep(random.uniform(0.5, 1.0))

        login_button = self.driver.find_element(By.ID, "login")
        login_button.click()

        # Wait for login indicators, dismissing any modals that appear
        self._wait_for_login_success(timeout=15)

    def _wait_for_login_success(self, timeout=15):
        """
        Poll for login success indicators while also checking for modals.
        If a modal appears, it means login succeeded - refresh page to clear it.
        """
        logged_in_selectors = [
            "div.sidebar-footer-icon[data-interaction='messages']",
            "a[href*='/stats/overview/']",
            "div.sidebar-footer-icon[data-interaction='settings']",
            "div.toolbar-user-info[data-cy='profile-section']",
            "div.home-user-info",
            "a.toolbar-action.friends",
            "a.toolbar-action.messages",
            "a.toolbar-action.settings",
            "a.play-quick-links-link",
        ]

        # Selectors for modal containers (presence = logged in)
        modal_selectors = [
            "div.coach-nudges-modal-component",
            "div.cc-modal-body",
        ]

        start_time = time.time()
        last_log_time = -3  # Start at -3 so first log happens immediately

        # Disable implicit wait for fast polling (restore after)
        self.driver.implicitly_wait(0)

        print("Waiting for login confirmation...")

        try:
            iteration = 0
            while time.time() - start_time < timeout:
                elapsed = time.time() - start_time
                iteration += 1

                # Log progress every 3 seconds
                if elapsed - last_log_time >= 3:
                    print(f"  Checking... ({int(elapsed)}s elapsed, iteration {iteration})")
                    last_log_time = elapsed

                # Check for login success indicators
                for i, selector in enumerate(logged_in_selectors):
                    check_start = time.time()
                    print(f"    [{i+1}/{len(logged_in_selectors)}] Checking: {selector[:50]}...", end=" ", flush=True)
                    try:
                        element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if element.is_displayed():
                            print(f"FOUND! ({time.time()-check_start:.2f}s)")
                            print(f"Login confirmed via: {selector}")
                            return
                        print(f"exists but hidden ({time.time()-check_start:.2f}s)")
                    except NoSuchElementException:
                        print(f"not found ({time.time()-check_start:.2f}s)")

                # Check for modals - if present, login succeeded, refresh to clear
                for i, selector in enumerate(modal_selectors):
                    check_start = time.time()
                    print(f"    [modal {i+1}/{len(modal_selectors)}] Checking: {selector}...", end=" ", flush=True)
                    try:
                        modal = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if modal.is_displayed():
                            print(f"FOUND! ({time.time()-check_start:.2f}s)")
                            print(f"Modal detected ({selector}) - login successful, refreshing page...")
                            self.driver.refresh()
                            time.sleep(1.5)
                            print("Page refreshed, login complete")
                            return
                        print(f"exists but hidden ({time.time()-check_start:.2f}s)")
                    except NoSuchElementException:
                        print(f"not found ({time.time()-check_start:.2f}s)")

                print(f"  --- End of iteration {iteration}, sleeping 0.2s ---")
                time.sleep(0.2)  # Poll interval

            raise TimeoutException(f"Login success not detected within {timeout} seconds")
        finally:
            # Restore implicit wait
            self.driver.implicitly_wait(5)

    def open_messages(self):
        self.driver.get("https://www.chess.com/messages/")

        wait = WebDriverWait(self.driver, 10)
        wait.until(
            EC.presence_of_element_located((By.CLASS_NAME, "message-list-search-wrapper"))
        )
    
    def scrape_games(self, username: str) -> List[Game]:
        # Timeout constants
        ITEM_TIMEOUT = 5  # seconds per attribute extraction
        GAME_TIMEOUT = 20  # seconds per game row

        url = f"https://www.chess.com/member/{username}/games"
        self.logger.log_browser_operation(f"Navigating to {url}")
        self.driver.get(url)

        wait = WebDriverWait(self.driver, 30)
        try:
            wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "archived-games-table"))
            )
        except TimeoutException:
            self.logger.error(f"Timeout waiting for games table for user {username}")
            return []

        # Wait a bit more for dynamic content to load
        time.sleep(2)

        games = []
        try:
            game_rows = self.driver.find_elements(By.CSS_SELECTOR, "tr.archived-games-table-row")
            print(f"Found {len(game_rows)} game rows for {username}")

            # Limit to first 20 games to avoid timeouts on large tables
            if len(game_rows) > 20:
                print(f"Limiting to first 20 games (found {len(game_rows)} total)")
                self.logger.log_scraping_limited(len(game_rows), 20)
                game_rows = game_rows[:20]

        except Exception as e:
            self.logger.error(f"Error finding game rows for {username}: {e}")
            return []

        for i, row in enumerate(game_rows, 1):
            try:
                game_start_time = time.time()
                print(f"\rProcessing game {i}/{len(game_rows)} for {username}...", end="", flush=True)

                def check_game_timeout():
                    """Returns True if game timeout exceeded"""
                    return time.time() - game_start_time > GAME_TIMEOUT

                # Extract game type and time control
                print(f"\rProcessing game {i}/{len(game_rows)} - extracting time control...", end="", flush=True)
                try:
                    game_type_elem = WebDriverWait(self.driver, ITEM_TIMEOUT).until(
                        lambda d: row.find_element(By.CSS_SELECTOR, ".archived-games-time-control")
                    )
                    time_control = game_type_elem.text.strip()
                except (TimeoutException, NoSuchElementException):
                    elapsed = time.time() - game_start_time
                    print(f"\rGame {i}/{len(game_rows)} - SKIP: failed to get time control ({elapsed:.2f}s)")
                    self.logger.log_game_skip(i, len(game_rows), "failed to get time control", elapsed)
                    continue

                if check_game_timeout():
                    elapsed = time.time() - game_start_time
                    print(f"\rGame {i}/{len(game_rows)} - SKIP: game timeout exceeded ({elapsed:.2f}s)")
                    self.logger.log_game_skip(i, len(game_rows), "game timeout exceeded", elapsed)
                    continue

                # Determine game type from SVG data-glyph attribute
                print(f"\rProcessing game {i}/{len(game_rows)} - extracting game type...", end="", flush=True)
                try:
                    game_type_svg = WebDriverWait(self.driver, ITEM_TIMEOUT).until(
                        lambda d: row.find_element(By.CSS_SELECTOR, "[data-glyph*='game-time']")
                    )
                    glyph = game_type_svg.get_attribute("data-glyph")
                    if glyph and "blitz" in glyph:
                        game_type = "Blitz"
                    elif glyph and "rapid" in glyph:
                        game_type = "Rapid"
                    elif glyph and "bullet" in glyph:
                        game_type = "Bullet"
                    elif glyph and "daily" in glyph:
                        game_type = "Daily"
                    else:
                        game_type = "Unknown"
                except (TimeoutException, NoSuchElementException):
                    elapsed = time.time() - game_start_time
                    print(f"\rGame {i}/{len(game_rows)} - SKIP: failed to get game type ({elapsed:.2f}s)")
                    self.logger.log_game_skip(i, len(game_rows), "failed to get game type", elapsed)
                    continue

                if check_game_timeout():
                    elapsed = time.time() - game_start_time
                    print(f"\rGame {i}/{len(game_rows)} - SKIP: game timeout exceeded ({elapsed:.2f}s)")
                    self.logger.log_game_skip(i, len(game_rows), "game timeout exceeded", elapsed)
                    continue

                # Extract player information
                print(f"\rProcessing game {i}/{len(game_rows)} - extracting players...", end="", flush=True)
                try:
                    user_tags = WebDriverWait(self.driver, ITEM_TIMEOUT).until(
                        lambda d: row.find_elements(By.CSS_SELECTOR, ".archived-games-user-tagline")
                    )
                except (TimeoutException, NoSuchElementException):
                    elapsed = time.time() - game_start_time
                    print(f"\rGame {i}/{len(game_rows)} - SKIP: failed to get players ({elapsed:.2f}s)")
                    self.logger.log_game_skip(i, len(game_rows), "failed to get players", elapsed)
                    continue

                if len(user_tags) >= 2:
                    # White player (first tagline)
                    print(f"\rProcessing game {i}/{len(game_rows)} - extracting white player...", end="", flush=True)
                    try:
                        white_username_elem = WebDriverWait(self.driver, ITEM_TIMEOUT).until(
                            lambda d: user_tags[0].find_element(By.CSS_SELECTOR, ".cc-user-username-component")
                        )
                        white_player = white_username_elem.text.strip() if white_username_elem else None
                        if not white_player:
                            raise NoSuchElementException("White player name empty")
                    except (TimeoutException, NoSuchElementException):
                        elapsed = time.time() - game_start_time
                        print(f"\rGame {i}/{len(game_rows)} - SKIP: failed to get white player ({elapsed:.2f}s)")
                        self.logger.log_game_skip(i, len(game_rows), "failed to get white player", elapsed)
                        continue

                    try:
                        white_rating_elem = user_tags[0].find_element(By.CSS_SELECTOR, ".cc-user-rating-default")
                        white_rating = white_rating_elem.text.strip().replace("(", "").replace(")", "") if white_rating_elem else "0"
                    except NoSuchElementException:
                        white_rating = "0"

                    # Black player (second tagline)
                    print(f"\rProcessing game {i}/{len(game_rows)} - extracting black player...", end="", flush=True)
                    try:
                        black_username_elem = WebDriverWait(self.driver, ITEM_TIMEOUT).until(
                            lambda d: user_tags[1].find_element(By.CSS_SELECTOR, ".cc-user-username-component")
                        )
                        black_player = black_username_elem.text.strip() if black_username_elem else None
                        if not black_player:
                            raise NoSuchElementException("Black player name empty")
                    except (TimeoutException, NoSuchElementException):
                        elapsed = time.time() - game_start_time
                        print(f"\rGame {i}/{len(game_rows)} - SKIP: failed to get black player ({elapsed:.2f}s)")
                        self.logger.log_game_skip(i, len(game_rows), "failed to get black player", elapsed)
                        continue

                    try:
                        black_rating_elem = user_tags[1].find_element(By.CSS_SELECTOR, ".cc-user-rating-default")
                        black_rating = black_rating_elem.text.strip().replace("(", "").replace(")", "") if black_rating_elem else "0"
                    except NoSuchElementException:
                        black_rating = "0"
                else:
                    # Skip if we don't have at least 2 user tags
                    elapsed = time.time() - game_start_time
                    print(f"\rGame {i}/{len(game_rows)} - SKIP: insufficient player data ({elapsed:.2f}s)")
                    self.logger.log_game_skip(i, len(game_rows), "insufficient player data", elapsed)
                    continue

                if check_game_timeout():
                    elapsed = time.time() - game_start_time
                    print(f"\rGame {i}/{len(game_rows)} - SKIP: game timeout exceeded ({elapsed:.2f}s)")
                    self.logger.log_game_skip(i, len(game_rows), "game timeout exceeded", elapsed)
                    continue

                # Extract result
                print(f"\rProcessing game {i}/{len(game_rows)} - extracting result...", end="", flush=True)
                try:
                    result_elem = WebDriverWait(self.driver, ITEM_TIMEOUT).until(
                        lambda d: row.find_element(By.CSS_SELECTOR, ".archived-games-result span")
                    )
                    if result_elem:
                        result_glyph = result_elem.get_attribute("data-glyph")
                        if result_glyph and "plus" in result_glyph:
                            result = "Win"
                        elif result_glyph and "minus" in result_glyph:
                            result = "Loss"
                        elif result_glyph and "equal" in result_glyph:
                            result = "Draw"
                        else:
                            result = "Unknown"
                    else:
                        raise NoSuchElementException("Result element not found")
                except (TimeoutException, NoSuchElementException):
                    elapsed = time.time() - game_start_time
                    print(f"\rGame {i}/{len(game_rows)} - SKIP: failed to get result ({elapsed:.2f}s)")
                    self.logger.log_game_skip(i, len(game_rows), "failed to get result", elapsed)
                    continue

                # Extract moves count
                print(f"\rProcessing game {i}/{len(game_rows)} - extracting moves...", end="", flush=True)
                try:
                    moves_elem = WebDriverWait(self.driver, ITEM_TIMEOUT).until(
                        lambda d: row.find_element(By.CSS_SELECTOR, "td:nth-child(6) span")
                    )
                    moves = moves_elem.text.strip() if moves_elem else None
                    if not moves:
                        raise NoSuchElementException("Moves element empty")
                except (TimeoutException, NoSuchElementException):
                    elapsed = time.time() - game_start_time
                    print(f"\rGame {i}/{len(game_rows)} - SKIP: failed to get moves ({elapsed:.2f}s)")
                    self.logger.log_game_skip(i, len(game_rows), "failed to get moves", elapsed)
                    continue

                # Extract date
                print(f"\rProcessing game {i}/{len(game_rows)} - extracting date...", end="", flush=True)
                try:
                    date_elem = WebDriverWait(self.driver, ITEM_TIMEOUT).until(
                        lambda d: row.find_element(By.CSS_SELECTOR, "td:nth-child(7) span")
                    )
                    date = date_elem.text.strip() if date_elem else None
                    if not date:
                        raise NoSuchElementException("Date element empty")
                except (TimeoutException, NoSuchElementException):
                    elapsed = time.time() - game_start_time
                    print(f"\rGame {i}/{len(game_rows)} - SKIP: failed to get date ({elapsed:.2f}s)")
                    self.logger.log_game_skip(i, len(game_rows), "failed to get date", elapsed)
                    continue

                # Extract game URL
                print(f"\rProcessing game {i}/{len(game_rows)} - extracting URL...", end="", flush=True)
                try:
                    game_link = WebDriverWait(self.driver, ITEM_TIMEOUT).until(
                        lambda d: row.find_element(By.CSS_SELECTOR, ".archived-games-background-link")
                    )
                    game_url = game_link.get_attribute("href") if game_link else None
                    if not game_url:
                        raise NoSuchElementException("URL element empty")
                except (TimeoutException, NoSuchElementException):
                    elapsed = time.time() - game_start_time
                    print(f"\rGame {i}/{len(game_rows)} - SKIP: failed to get URL ({elapsed:.2f}s)")
                    self.logger.log_game_skip(i, len(game_rows), "failed to get URL", elapsed)
                    continue

                print(f"\rProcessing game {i}/{len(game_rows)} - creating game object...", end="", flush=True)
                game = Game(
                    game_type=game_type,
                    time_control=time_control,
                    white_player=white_player,
                    white_rating=white_rating,
                    black_player=black_player,
                    black_rating=black_rating,
                    result=result,
                    moves=moves,
                    date=date,
                    game_url=game_url
                )
                games.append(game)
                elapsed = time.time() - game_start_time
                print(f"\rGame {i}/{len(game_rows)} - SUCCESS: {white_player} vs {black_player} ({elapsed:.2f}s)")
                self.logger.log_game_success(i, len(game_rows), white_player, black_player, elapsed)

            except Exception as e:
                elapsed = time.time() - game_start_time
                print(f"\rGame {i}/{len(game_rows)} - ERROR: {str(e)} ({elapsed:.2f}s)")
                self.logger.log_game_error(i, len(game_rows), str(e), elapsed)
                continue

        return games

    def send_message(self, recipient_username, message) -> bool:
        try:
            self.logger.log_browser_operation(f'Navigating to compose message page for {recipient_username}')

            # Navigate to compose message page
            self.driver.get('https://www.chess.com/messages/compose')

            wait = WebDriverWait(self.driver, 10)

            # Find and fill recipient search field
            recipient_field = wait.until(
                EC.presence_of_element_located((By.ID, "search-member"))
            )
            recipient_field.clear()
            recipient_field.send_keys(recipient_username)

            # Wait for autocomplete dropdown and select first result
            time.sleep(2)
            try:
                autocomplete_dropdown = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".form-autocomplete-dropdown"))
                )
                # Click the first autocomplete item
                first_result = autocomplete_dropdown.find_element(By.CSS_SELECTOR, ".form-autocomplete-item")
                first_result.click()
            except (TimeoutException, NoSuchElementException):
                self.logger.warning(f"Could not find autocomplete for user {recipient_username}")
                return False

            # Wait for the message editor iframe to load
            time.sleep(2)
            iframe = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "iframe.tox-edit-area__iframe"))
            )

            # Switch to iframe context
            self.driver.switch_to.frame(iframe)

            # Find the message body element and enter the message
            message_body = wait.until(
                EC.presence_of_element_located((By.ID, "tinymce"))
            )

            # Important: Click on the message body to focus it
            message_body.click()
            time.sleep(1)  # Give it a moment to register the focus

            # Clear any existing content
            message_body.clear()

            # Handle URLs in the message by converting them to HTML links
            if "http" in message:
                # Use JavaScript to set innerHTML with proper link formatting
                html_message = self._format_message_with_links(message)
                self.driver.execute_script(f"arguments[0].innerHTML = '{html_message}';", message_body)
                # Trigger input event to let the editor know content changed
                self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", message_body)
            else:
                # Simple text message - click first then type
                message_body.send_keys(message)

            # Trigger blur event to ensure content is registered
            self.driver.execute_script("arguments[0].blur(); arguments[0].focus();", message_body)

            # Switch back to main page context
            self.driver.switch_to.default_content()

            # Find and click send button
            send_button = wait.until(
                EC.element_to_be_clickable((By.ID, "message-submit"))
            )
            send_button.click()

            self.logger.log_browser_operation(f"Successfully sent message to {recipient_username}")
            return True

        except Exception as e:
            self.logger.error(f"Error sending message to {recipient_username}: {e}")
            # Make sure we're back in default context
            try:
                self.driver.switch_to.default_content()
            except:
                pass
            return False

    def _format_message_with_links(self, message):
        # Convert URLs in message to HTML links
        import re
        url_pattern = r'(https?://[^\s]+)'

        def replace_url(match):
            url = match.group(1)
            # Extract domain for display text
            domain = url.replace('https://', '').replace('http://', '').split('/')[0]
            return f'<a href="{url}" target="_blank" rel="noopener">{domain}</a>'

        html_message = re.sub(url_pattern, replace_url, message)
        return html_message.replace("'", "\\'")  # Escape single quotes for JavaScript


if __name__ == "__main__":
    # Test the messaging functionality
    from creds import ChessCreds

    driver = None

    try:
        creds_manager = ChessCreds()
        creds = creds_manager.get_creds()
        driver = ChessDriver(credentials=creds, headless=False)

        # Login first
        print("Logging in...")
        driver.login()
        print("Login successful!")

        # Test message with embedded URL
        recipient = 'Fellmatte'
        message = 'Hey! I want you to check out my chess website ive been working on: https://chesspecker.org'

        print(f"Ready to send message to {recipient}")

        # Send the message
        success = driver.send_message(recipient, message)

        if success:
            print("Message sent successfully!")
        else:
            print("Failed to send message.")

        # Wait before closing
        input("Press Enter to quit...")

    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
    except Exception as e:
        print(f"Error during execution: {e}")
    finally:
        if driver:
            print("Cleaning up browser...")
            driver.quit()
            print("Browser cleanup completed")