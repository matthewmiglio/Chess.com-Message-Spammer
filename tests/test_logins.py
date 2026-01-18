#this script should iterate over each account
#and produce a table like this
#account name | step a success indicator | step b success indicator | step c success indicator
#we're only gonna test logging in for this file.
#so we should try to open a driver, get to login page, enter login creds, and watch for a success indicator
#we shouldnt rewrite any code here, really, we should pull from the same functions that main.py would use
#i think we should just print this table to terminal in a nice formatted way
#make good use of formatted strings and spacing so the table looks human readable

import sys
import os
import time
import random

# Add parent directory to path so we can import from the main package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from creds import ChessCreds
from chess_driver import ChessDriver, CHESS_LOGIN_PAGE_URL
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


def test_login_for_account(credentials: dict) -> dict:
    """
    Test the login flow for a single account.
    Returns a dict with results for each step.
    """
    results = {
        "account": credentials["username"],
        "step_a": "---",  # Open browser & navigate to login page
        "step_b": "---",  # Enter credentials
        "step_c": "---",  # Login success detected
        "error": None
    }

    driver = None

    try:
        # Step A: Initialize browser and navigate to login page
        driver = ChessDriver(credentials=credentials, headless=False)
        try:
            driver.driver.get(CHESS_LOGIN_PAGE_URL)
            time.sleep(random.uniform(1.0, 2.0))
            results["step_a"] = "OK"
        except Exception as e:
            results["step_a"] = "FAIL"
            results["error"] = f"Step A: {str(e).split(chr(10))[0][:50]}"
            return results

        # Step B: Enter username and password
        try:
            wait = WebDriverWait(driver.driver, 10)

            # Enter username
            username_field = wait.until(
                EC.presence_of_element_located((By.ID, "login-username"))
            )
            username_field.clear()
            time.sleep(random.uniform(0.3, 0.7))
            driver._human_type(username_field, credentials["username"])

            time.sleep(random.uniform(0.5, 1.0))

            # Enter password
            password_field = driver.driver.find_element(By.ID, "login-password")
            password_field.clear()
            time.sleep(random.uniform(0.3, 0.7))
            driver._human_type(password_field, credentials["password"])

            time.sleep(random.uniform(0.5, 1.0))

            # Click login button
            login_button = driver.driver.find_element(By.ID, "login")
            login_button.click()

            results["step_b"] = "OK"
        except Exception as e:
            results["step_b"] = "FAIL"
            results["error"] = f"Step B: {str(e).split(chr(10))[0][:50]}"
            return results

        # Step C: Wait for login success indicator
        try:
            driver._wait_for_login_success(timeout=15)
            results["step_c"] = "OK"
        except TimeoutException:
            results["step_c"] = "FAIL"
            results["error"] = "Step C: Login timeout (wrong creds or CAPTCHA)"
        except Exception as e:
            results["step_c"] = "FAIL"
            results["error"] = f"Step C: {str(e).split(chr(10))[0][:50]}"

    except Exception as e:
        results["error"] = f"Init: {str(e).split(chr(10))[0][:50]}"

    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

    return results


def print_results_table(all_results: list):
    """Print a nicely formatted table of all results."""

    # Column widths
    col_account = 22
    col_step = 8
    col_error = 55

    # Header
    header = (
        f"{'Account':<{col_account}} | "
        f"{'Step A':<{col_step}} | "
        f"{'Step B':<{col_step}} | "
        f"{'Step C':<{col_step}} | "
        f"{'Error':<{col_error}}"
    )
    separator = "-" * len(header)

    print("\n" + "=" * len(header))
    print("LOGIN TEST RESULTS")
    print("=" * len(header))
    print("Step A: Open browser & navigate to login page")
    print("Step B: Enter credentials and click login")
    print("Step C: Detect login success indicator")
    print("=" * len(header) + "\n")

    print(header)
    print(separator)

    # Results rows
    for r in all_results:
        error_str = r["error"] if r["error"] else ""
        if len(error_str) > col_error:
            error_str = error_str[:col_error-3] + "..."

        # Color coding for terminal (green=OK, red=FAIL)
        step_a = f"\033[92m{r['step_a']}\033[0m" if r['step_a'] == "OK" else f"\033[91m{r['step_a']}\033[0m"
        step_b = f"\033[92m{r['step_b']}\033[0m" if r['step_b'] == "OK" else f"\033[91m{r['step_b']}\033[0m"
        step_c = f"\033[92m{r['step_c']}\033[0m" if r['step_c'] == "OK" else f"\033[91m{r['step_c']}\033[0m"

        # Pad the colored strings (ANSI codes don't count towards visible width)
        step_a_padded = step_a + " " * (col_step - len(r['step_a']))
        step_b_padded = step_b + " " * (col_step - len(r['step_b']))
        step_c_padded = step_c + " " * (col_step - len(r['step_c']))

        row = (
            f"{r['account']:<{col_account}} | "
            f"{step_a_padded} | "
            f"{step_b_padded} | "
            f"{step_c_padded} | "
            f"{error_str:<{col_error}}"
        )
        print(row)

    print(separator)

    # Summary
    total = len(all_results)
    passed = sum(1 for r in all_results if r["step_c"] == "OK")
    failed = total - passed

    print(f"\nSummary: {passed}/{total} accounts logged in successfully, {failed} failed\n")


def main():
    print("\nLoading accounts...")
    creds_manager = ChessCreds()
    accounts = creds_manager.get_all_accounts()
    print(f"Found {len(accounts)} accounts to test\n")

    all_results = []

    for i, account in enumerate(accounts):
        print(f"[{i+1}/{len(accounts)}] Testing: {account['username']}...")
        result = test_login_for_account(account)
        all_results.append(result)

        status = "PASS" if result["step_c"] == "OK" else "FAIL"
        print(f"[{i+1}/{len(accounts)}] {account['username']}: {status}")

        # Small delay between accounts
        if i < len(accounts) - 1:
            print("Waiting 3s before next account...")
            time.sleep(3)

    # Print final table
    print_results_table(all_results)


if __name__ == "__main__":
    main()
