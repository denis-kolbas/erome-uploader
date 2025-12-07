#!/usr/bin/env python3
"""
Helper script to login locally and save browser session state.
Run this on your local machine to generate storage_state.json
"""
import os
import time
import shutil
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from twocaptcha import TwoCaptcha

load_dotenv()

def find_brave_executable():
    candidates = [
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        "/usr/bin/brave-browser",
        shutil.which("brave-browser"),
        shutil.which("brave"),
        "C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe",
        "C:\\Program Files (x86)\\BraveSoftware\\Brave-Browser\\Application\\brave.exe",
    ]
    for path in candidates:
        if path and os.path.exists(path):
            print(f"✓ Brave found at: {path}")
            return path
    print("⚠️ Brave not found. Using default Chromium.")
    return None

def solve_captcha(page):
    try:
        captcha_img = page.locator('div.form-group div.mb-10 img')
        captcha_img.screenshot(path='captcha.png')
        solver = TwoCaptcha(os.getenv('TWO_CAPTCHA_API_KEY'))
        print("Sending CAPTCHA to 2Captcha...")
        result = solver.normal('captcha.png')
        captcha_text = result['code'].strip().upper()
        print(f"✓ 2Captcha solved: {captcha_text}")
        return captcha_text
    except Exception as e:
        print(f"✗ 2Captcha solving failed: {str(e)}")
        return None

def handle_age_overlay(page):
    try:
        disclaimer = page.locator('#disclaimer')
        if disclaimer.count() > 0:
            print("⚠️ Age verification overlay detected. Confirming...")
            enter_button = disclaimer.locator('.enter')
            enter_button.click()
            page.wait_for_selector('#disclaimer', state='detached', timeout=5000)
            print("✓ Age verification confirmed.")
    except Exception as e:
        print(f"✗ Error handling age overlay: {e}")

def main():
    print("="*60)
    print("Session Saver - Login and Save Browser State")
    print("="*60)
    
    with sync_playwright() as p:
        brave_path = find_brave_executable()
        
        browser = p.chromium.launch(
            executable_path=brave_path if brave_path else None,
            headless=False,  # Always show browser for local login
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="America/New_York",
        )
        
        page = context.new_page()
        
        # Go to the site
        print("\n1. Navigating to erome.com...")
        page.goto('https://www.erome.com/explore', wait_until='networkidle')
        time.sleep(1)
        handle_age_overlay(page)
        time.sleep(1)
        
        # Check if already logged in
        upload_button = page.locator("a#upload-album, a[href*='/upload']")
        if upload_button.count() > 0:
            print("✓ Already logged in!")
        else:
            print("\n2. Logging in...")
            page.goto('https://www.erome.com/user/login', wait_until='networkidle')
            time.sleep(2)
            
            username = os.getenv('WEBSITE_USERNAME')
            password = os.getenv('WEBSITE_PASSWORD')
            
            print(f"   Filling username: {username[:3]}***")
            page.fill('input#email.form-control', username)
            time.sleep(0.5)
            
            print(f"   Filling password: ***")
            page.fill('input#password.form-control', password)
            time.sleep(0.5)
            
            print("   Solving captcha...")
            captcha_solution = solve_captcha(page)
            if not captcha_solution:
                print("✗ Captcha solving failed!")
                browser.close()
                return
            
            print(f"   Filling captcha: {captcha_solution}")
            page.fill('input[name="captcha"]', captcha_solution)
            time.sleep(1)
            
            print("   Clicking submit...")
            submit_button = page.locator('button[type="submit"].btn.btn-pink')
            
            try:
                with page.expect_navigation(timeout=15000):
                    submit_button.click()
                print("   ✓ Navigation occurred")
            except Exception as e:
                print(f"   ⚠️ No navigation: {e}")
            
            time.sleep(3)
            
            # Verify login
            if page.locator("a#upload-album, a[href*='/upload']").count() > 0:
                print("✓ Login successful!")
            else:
                print("✗ Login failed. Please check credentials.")
                print(f"Current URL: {page.url}")
                input("Press Enter to close browser...")
                browser.close()
                return
        
        # Save storage state
        print("\n3. Saving session state...")
        storage_state = context.storage_state(path="storage_state.json")
        print("✓ Session saved to: storage_state.json")
        
        print("\n" + "="*60)
        print("SUCCESS! Next steps:")
        print("="*60)
        print("1. Copy the content of storage_state.json")
        print("2. Go to your GitHub repo → Settings → Secrets → Actions")
        print("3. Create a new secret named: BROWSER_STATE")
        print("4. Paste the entire JSON content as the value")
        print("="*60)
        
        input("\nPress Enter to close browser...")
        browser.close()

if __name__ == "__main__":
    main()
