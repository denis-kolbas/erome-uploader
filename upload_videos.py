import os
import time
import shutil
import json
from datetime import datetime
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from twocaptcha import TwoCaptcha
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Load environment variables
load_dotenv()
SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SHEET_NAME = "calendar"
DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
VIDEO_DOWNLOAD_PATH = "/tmp/Ero/videos"

# Browser state configuration (for skipping login)
BROWSER_STATE = os.getenv("BROWSER_STATE")  # JSON string from GitHub secret
BROWSER_STATE_FILE = "storage_state.json"  # Local file

# Proxy configuration - Webshare.io rotating proxy (optional, only needed for login)
PROXY_ENABLED = os.getenv("PROXY_ENABLED", "false").lower() == "true"
PROXY_HOST = os.getenv("PROXY_HOST", "p.webshare.io")
PROXY_PORT = os.getenv("PROXY_PORT", "80")
PROXY_USERNAME = os.getenv("PROXY_USERNAME", "mhcbvnkx-rotate")
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD", "wsramyu1qzh0")

def get_browser_state():
    """Get browser state from environment or file"""
    # First check if we have it as an environment variable (GitHub Actions)
    if BROWSER_STATE:
        print("✓ Using browser state from environment variable")
        try:
            state = json.loads(BROWSER_STATE)
            # Save to temp file for Playwright
            temp_state_file = "/tmp/storage_state.json"
            with open(temp_state_file, 'w') as f:
                json.dump(state, f)
            return temp_state_file
        except json.JSONDecodeError as e:
            print(f"⚠️ Failed to parse BROWSER_STATE: {e}")
            return None
    
    # Check for local file
    if os.path.exists(BROWSER_STATE_FILE):
        print(f"✓ Using browser state from {BROWSER_STATE_FILE}")
        return BROWSER_STATE_FILE
    
    print("⚠️ No browser state found. Will need to login.")
    return None

def get_proxy_config():
    """Get proxy configuration for Playwright"""
    if not PROXY_ENABLED:
        return None
    
    proxy = {
        'server': f'http://{PROXY_HOST}:{PROXY_PORT}',
        'username': PROXY_USERNAME,
        'password': PROXY_PASSWORD
    }
    print(f"✓ Using rotating proxy: {PROXY_HOST}:{PROXY_PORT}")
    return proxy

# Validate required environment variables
required_vars = {
    "GOOGLE_SERVICE_ACCOUNT_JSON": SERVICE_ACCOUNT_JSON,
    "GOOGLE_SHEET_ID": SHEET_ID,
    "GOOGLE_DRIVE_FOLDER_ID": DRIVE_FOLDER_ID,
    "WEBSITE_USERNAME": os.getenv("WEBSITE_USERNAME"),
    "WEBSITE_PASSWORD": os.getenv("WEBSITE_PASSWORD"),
    "TWO_CAPTCHA_API_KEY": os.getenv("TWO_CAPTCHA_API_KEY"),
}

missing_vars = [name for name, value in required_vars.items() if not value]
if missing_vars:
    print(f"✗ Error: Missing required environment variables: {', '.join(missing_vars)}")
    print("\nFor GitHub Actions, add these as repository secrets:")
    print("https://github.com/YOUR_USERNAME/YOUR_REPO/settings/secrets/actions")
    exit(1)

if not os.path.exists(VIDEO_DOWNLOAD_PATH):
    os.makedirs(VIDEO_DOWNLOAD_PATH)

# Google Sheets / Drive setup
try:
    creds_info = json.loads(SERVICE_ACCOUNT_JSON)
except json.JSONDecodeError as e:
    print(f"✗ Error: GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON")
    print(f"Details: {e}")
    print("\nMake sure you copied the entire JSON object from your service account file.")
    exit(1)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive.readonly"]

creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
sheets_service = build('sheets', 'v4', credentials=creds)
drive_service = build('drive', 'v3', credentials=creds)

SHEET_RANGE = f"{SHEET_NAME}!A1:E"

# --- Helpers for Sheets / Drive ---
def get_first_pending_row():
    try:
        sheet_data = sheets_service.spreadsheets().values().get(spreadsheetId=SHEET_ID, range=SHEET_RANGE).execute()
        rows = sheet_data.get("values", [])
        if len(rows) < 2:
            return None
        header = rows[0]
        for i, row in enumerate(rows[1:], start=2):  # skip header
            status_idx = header.index("status")
            if len(row) <= status_idx or row[status_idx] == "":
                return i, dict(zip(header, row))
        return None
    except Exception as e:
        print(f"✗ Error accessing sheet: {e}")
        if "404" in str(e):
            print("\nPossible issues:")
            print(f"1. Sheet ID might be wrong: {SHEET_ID}")
            print(f"2. Sheet tab '{SHEET_NAME}' doesn't exist")
            print("3. Service account doesn't have access to the sheet")
            print("\nTo fix:")
            print("- Verify GOOGLE_SHEET_ID is correct")
            print("- Make sure your sheet has a tab named 'calendar'")
            print("- Share the sheet with your service account email")
        return None

def update_sheet_row(row_number, status, timestamp):
    values = [[status, timestamp]]
    body = {"values": values}
    range_to_update = f"{SHEET_NAME}!D{row_number}:E{row_number}"
    sheets_service.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range=range_to_update,
        valueInputOption="RAW",
        body=body
    ).execute()

def download_file_from_drive(file_name):
    file_name_with_ext = f"{file_name}.mp4"
    query = f"name='{file_name_with_ext}' and '{DRIVE_FOLDER_ID}' in parents and trashed=false"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    if not files:
        raise Exception(f"File not found in Drive: {file_name_with_ext}")
    file_id = files[0]["id"]
    request = drive_service.files().get_media(fileId=file_id)
    from googleapiclient.http import MediaIoBaseDownload
    import io
    fh = io.FileIO(os.path.join(VIDEO_DOWNLOAD_PATH, file_name_with_ext), 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.close()
    return os.path.join(VIDEO_DOWNLOAD_PATH, file_name_with_ext)

# --- Playwright helpers ---
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
    print("⚠️ Brave not found. Falling back to default Chromium.")
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
        else:
            print("No age overlay detected.")
    except Exception as e:
        print(f"✗ Error handling age overlay: {e}")

# --- Main uploader ---
def upload_video(row_data):
    downloaded_files = []
    try:
        return _upload_video_impl(row_data, downloaded_files)
    finally:
        # Cleanup downloaded files
        for file_path in downloaded_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"✓ Cleaned up: {file_path}")
            except Exception as e:
                print(f"⚠️ Failed to cleanup {file_path}: {e}")

def _upload_video_impl(row_data, downloaded_files):
    # Validate required fields
    required_fields = ["title", "videos", "tags"]
    for field in required_fields:
        if field not in row_data or not row_data[field]:
            raise Exception(f"Missing required field: {field}")
    
    # Get browser state and proxy configuration
    storage_state_path = get_browser_state()
    proxy = get_proxy_config()
    
    with sync_playwright() as p:
        brave_path = find_brave_executable()
        browser_args = [
            "--disable-popup-blocking",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox"
        ]
        
        # Use headless mode in CI/production, headed locally
        is_ci = os.getenv('CI') is not None or os.getenv('GITHUB_ACTIONS') is not None
        headless_mode = is_ci
        
        if brave_path:
            browser_args += ["--brave-shields-up","--no-default-browser-check","--no-first-run"]

        # If we have storage state, use regular context (not persistent)
        # This allows us to load cookies without a user data dir
        if storage_state_path:
            print("✓ Using stored session - skipping login")
            browser = p.chromium.launch(
                executable_path=brave_path if brave_path else None,
                headless=headless_mode,
                args=browser_args,
            )
            
            context_options = {
                "storage_state": storage_state_path,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "viewport": {"width": 1920, "height": 1080},
                "locale": "en-US",
                "timezone_id": "America/New_York",
            }
            
            # Add proxy if available (only needed for login, but doesn't hurt)
            if proxy:
                context_options["proxy"] = proxy
            
            context = browser.new_context(**context_options)
            page = context.new_page()
            skip_login = True
        else:
            # No storage state - use persistent context and login
            print("⚠️ No stored session - will need to login")
            user_data_dir = "/tmp/brave-profile" if brave_path else "/tmp/chrome-profile"
            
            context_options = {
                "user_data_dir": user_data_dir,
                "executable_path": brave_path if brave_path else None,
                "headless": headless_mode,
                "args": browser_args,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "viewport": {"width": 1920, "height": 1080},
                "locale": "en-US",
                "timezone_id": "America/New_York",
            }
            
            # Add proxy if available
            if proxy:
                context_options["proxy"] = proxy
            
            context = p.chromium.launch_persistent_context(**context_options)
            page = context.new_page()
            skip_login = False
        
        # Start tracing
        trace_dir = "/tmp/traces"
        os.makedirs(trace_dir, exist_ok=True)
        trace_file = os.path.join(trace_dir, f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip")
        
        # Start tracing on context (not browser)
        if storage_state_path:
            context.tracing.start(screenshots=True, snapshots=True, sources=True)
        else:
            context.tracing.start(screenshots=True, snapshots=True, sources=True)
        print(f"✓ Started Playwright trace: {trace_file}")
        
        # Navigate to site
        page.goto('https://www.erome.com/explore', wait_until='networkidle')
        time.sleep(1)
        handle_age_overlay(page)
        time.sleep(1)

        # Check if logged in by looking for upload button
        upload_button_check = page.locator("a#upload-album, a[href*='/upload']")
        
        # If we have stored session, we should already be logged in
        if skip_login:
            if upload_button_check.count() > 0:
                print("✓ Session is valid - already logged in!")
            else:
                print("✗ Session expired or invalid - need to re-login")
                print("   Please run save_session.py locally to update your session")
                raise Exception("Stored session is invalid. Please update BROWSER_STATE secret.")
        
        # If upload button not visible and no stored session, we need to login
        elif upload_button_check.count() == 0:
            username = os.getenv('WEBSITE_USERNAME')
            password = os.getenv('WEBSITE_PASSWORD')
            
            max_login_attempts = 3
            login_successful = False
            
            for attempt in range(1, max_login_attempts + 1):
                print(f"\n{'='*50}")
                print(f"Login attempt {attempt}/{max_login_attempts}")
                print(f"{'='*50}")
                
                print("Navigating to login page...")
                page.goto('https://www.erome.com/user/login', wait_until='networkidle')
                time.sleep(2)
                print(f"✓ On login page: {page.url}")
                
                print(f"  Filling username: {username[:3]}***")
                page.fill('input#email.form-control', username)
                time.sleep(0.5)
                
                print(f"  Filling password: ***")
                page.fill('input#password.form-control', password)
                time.sleep(0.5)
                
                print("  Solving captcha...")
                captcha_solution = solve_captcha(page)
                if not captcha_solution:
                    print(f"  ✗ Captcha solving failed on attempt {attempt}")
                    if attempt < max_login_attempts:
                        print("  Retrying...")
                        continue
                    else:
                        raise Exception("Captcha solving failed after all attempts")
                
                print(f"  Filling captcha: {captcha_solution}")
                page.fill('input[name="captcha"]', captcha_solution)
                time.sleep(1)
                
                # Take screenshot before submitting
                page.screenshot(path=f'before_submit_attempt_{attempt}.png')
                print(f"  Screenshot saved: before_submit_attempt_{attempt}.png")
                
                print("  Looking for submit button...")
                submit_button = page.locator('button[type="submit"].btn.btn-pink')
                if submit_button.count() == 0:
                    print("  ✗ Submit button not found!")
                    raise Exception("Login button not found on page")
                
                print("  Clicking submit button...")
                # Wait for navigation after clicking submit
                try:
                    with page.expect_navigation(timeout=15000):
                        submit_button.click()
                    print("  ✓ Navigation occurred after submit")
                except Exception as e:
                    print(f"  ⚠️ No navigation after submit: {e}")
                
                time.sleep(3)
                
                print(f"  After login URL: {page.url}")
                
                # Check for error messages
                error_msg = page.locator('.alert-danger, .alert-warning, .error, .text-danger').first
                if error_msg.count() > 0:
                    error_text = error_msg.text_content()
                    print(f"  ✗ Error message on page: {error_text}")
                
                # Check if still on login form
                if page.locator('input#email.form-control').count() > 0:
                    print("  ⚠️ Still seeing login form fields")
                    # Get page content for debugging
                    page_title = page.title()
                    print(f"  Page title: {page_title}")
                    
                    # Check if form has validation errors
                    validation_errors = page.locator('.invalid-feedback, .form-error').all()
                    if validation_errors:
                        for err in validation_errors:
                            if err.is_visible():
                                print(f"  Validation error: {err.text_content()}")
                
                # Verify login was successful
                upload_btn_count = page.locator("a#upload-album, a[href*='/upload']").count()
                print(f"  Upload button count: {upload_btn_count}")
                
                if upload_btn_count > 0:
                    login_successful = True
                    print(f"✓ Login successful on attempt {attempt}!")
                    break
                else:
                    print(f"  ✗ Login failed on attempt {attempt}")
                    if attempt < max_login_attempts:
                        print("  Captcha was likely wrong. Retrying with new captcha...")
                        time.sleep(2)
                    else:
                        # Take screenshot on final failure
                        page.screenshot(path='login_failed.png')
                        print("  ✗ Screenshot saved to login_failed.png")
            
            if not login_successful:
                raise Exception(f"Login failed after {max_login_attempts} attempts")
        else:
            print("✓ Already logged in")

        # Navigate to upload
        upload_button = page.locator("a#upload-album, a[href*='/upload']")
        upload_button.wait_for(state='visible', timeout=10000)
        upload_button.click()
        page.wait_for_load_state('networkidle')
        time.sleep(2)
        if page.locator('#rules:visible').count() > 0:
            page.locator('#rules button[data-dismiss="modal"]').click()
            time.sleep(0.5)

        # Update title
        new_title = row_data["title"]
        title_handle = page.locator("h1#title_editable.content-editable.album-title").element_handle()
        page.evaluate("""
            (el) => { el.focus(); document.execCommand('selectAll', false, null); document.execCommand('delete', false, null); }
        """, title_handle)
        for char in new_title:
            page.keyboard.type(char)
            time.sleep(0.05)
        page.keyboard.press("Enter")
        page.evaluate("""
            (el) => { el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); }
        """, title_handle)
        print(f"✓ Album title updated to: {new_title}")
        time.sleep(1)

        # Upload files
        video_files = [v.strip() for v in row_data["videos"].split(",") if v.strip()]
        for vf in video_files:
            print(f"Downloading: {vf}")
            try:
                file_path = download_file_from_drive(vf)
                downloaded_files.append(file_path)
                time.sleep(1)
            except Exception as e:
                print(f"⚠️ Skipping {vf}: {str(e)}")
                continue
        
        if not downloaded_files:
            raise Exception("No videos were successfully downloaded")
        
        file_input = page.locator('#add_more_file')
        file_input.set_input_files(downloaded_files)
        print(f"✓ Files queued for upload: {len(downloaded_files)} file(s)")
        
        # Wait for upload to complete
        print("Waiting for files to upload...")
        time.sleep(5)  # Initial wait for upload to start
        
        # Check for video thumbnails in #medias div (indicates upload complete)
        max_wait = 300  # 5 minutes max wait
        wait_interval = 10
        elapsed = 0
        
        while elapsed < max_wait:
            # Check if videos appear in the medias container
            media_items = page.locator('#medias .media-group, #medias video, #medias img').count()
            if media_items >= len(downloaded_files):
                print(f"✓ All {len(downloaded_files)} file(s) uploaded successfully")
                break
            
            print(f"Upload in progress... ({elapsed}s elapsed, {media_items}/{len(downloaded_files)} files visible)")
            time.sleep(wait_interval)
            elapsed += wait_interval
        
        if elapsed >= max_wait:
            print(f"⚠️ Upload timeout reached. Proceeding anyway...")
        
        # Extra wait to ensure processing is complete
        print("Waiting additional time for upload processing...")
        time.sleep(60)  # 1 minute extra wait

        # Add tags
        tags = [t.strip() for t in row_data["tags"].split(",") if t.strip()]
        if tags:
            tags_input = page.locator('#tag_input')
            for tag in tags:
                tags_input.fill(tag)
                tags_input.press("Enter")
                time.sleep(0.5)
            print(f"✓ Tags added: {', '.join(tags)}")
        else:
            print("⚠️ No tags to add")

        # Save / publish
        print("Preparing to save album...")
        time.sleep(3)
        
        save_button = page.locator("div#done_box a.btn.btn-pink")
        if save_button.count() == 0:
            raise Exception("Save button not found - upload may have failed")
        
        # Get the redirect URL from onclick before clicking
        onclick_attr = save_button.get_attribute('onclick')
        print(f"Save button onclick: {onclick_attr}")
        
        save_button.click()
        print("✓ Clicked SAVE to publish album")
        
        # Wait for redirect (the onclick has 200ms delay, then redirects)
        time.sleep(2)
        
        # Wait for page to load after redirect (use 'load' instead of 'networkidle')
        try:
            page.wait_for_load_state('load', timeout=15000)
        except Exception as e:
            print(f"⚠️ Page load timeout (this is usually fine): {e}")
        
        time.sleep(3)
        
        final_url = page.url
        print(f"✓ Upload complete. Final URL: {final_url}")
        
        # Verify we're on the album page (not still on upload page)
        if '/upload' in final_url:
            raise Exception("Still on upload page - album may not have been created")
        elif '/a/' in final_url:
            print("✓ Successfully redirected to album page")
        else:
            print(f"⚠️ Unexpected URL pattern: {final_url}")
        
        # Stop tracing and save
        context.tracing.stop(path=trace_file)
        print(f"✓ Trace saved to: {trace_file}")
        
        # Close browser/context
        if storage_state_path:
            context.close()
            browser.close()
        else:
            context.close()
        
        return True

# --- Main ---
if __name__ == "__main__":
    print(f"=== Starting upload process at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    
    pending = get_first_pending_row()
    if not pending:
        print("No pending videos found.")
        exit(0)
    
    row_number, row_data = pending
    print(f"Processing row {row_number}: {row_data.get('title', 'No title')}")
    
    try:
        upload_video(row_data)
        # Update sheet
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        update_sheet_row(row_number, "posted", now_str)
        print(f"✓ Sheet updated for row {row_number}")
        print(f"=== Upload completed successfully at {now_str} ===")
    except Exception as e:
        print(f"✗ Upload failed: {str(e)}")
        # Optionally update sheet with error status
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            update_sheet_row(row_number, f"error: {str(e)[:50]}", now_str)
        except:
            pass
        exit(1)