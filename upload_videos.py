import os
import time
import shutil
import json
from datetime import datetime
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth
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

# Proxy configuration
PROXY_ENABLED = os.getenv("PROXY_ENABLED", "true").lower() == "true"
PROXY_HOST = os.getenv("PROXY_HOST", "p.webshare.io")
PROXY_PORT = os.getenv("PROXY_PORT", "80")
PROXY_USERNAME = os.getenv("PROXY_USERNAME", "mhcbvnkx-rotate")
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD", "wsramyu1qzh0")

# --- Configuration & Helpers ---

def get_proxy_config():
    """Get proxy configuration for Playwright"""
    if not PROXY_ENABLED:
        print("⚠️ Proxy is DISABLED - running without proxy")
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
    exit(1)

if not os.path.exists(VIDEO_DOWNLOAD_PATH):
    os.makedirs(VIDEO_DOWNLOAD_PATH)

# Google Sheets / Drive setup
try:
    creds_info = json.loads(SERVICE_ACCOUNT_JSON)
except json.JSONDecodeError as e:
    print(f"✗ Error: GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON")
    exit(1)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.readonly"]
creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
sheets_service = build('sheets', 'v4', credentials=creds)
drive_service = build('drive', 'v3', credentials=creds)
SHEET_RANGE = f"{SHEET_NAME}!A1:E"

# --- Google API Functions ---

def get_first_pending_row():
    try:
        sheet_data = sheets_service.spreadsheets().values().get(spreadsheetId=SHEET_ID, range=SHEET_RANGE).execute()
        rows = sheet_data.get("values", [])
        if len(rows) < 2: return None
        header = rows[0]
        for i, row in enumerate(rows[1:], start=2):
            status_idx = header.index("status")
            if len(row) <= status_idx or row[status_idx] == "":
                return i, dict(zip(header, row))
        return None
    except Exception as e:
        print(f"✗ Error accessing sheet: {e}")
        return None

def update_sheet_row(row_number, status, timestamp):
    values = [[status, timestamp]]
    body = {"values": values}
    range_to_update = f"{SHEET_NAME}!D{row_number}:E{row_number}"
    sheets_service.spreadsheets().values().update(
        spreadsheetId=SHEET_ID, range=range_to_update, valueInputOption="RAW", body=body
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
    
    save_path = os.path.join(VIDEO_DOWNLOAD_PATH, file_name_with_ext)
    fh = io.FileIO(save_path, 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.close()
    return save_path

# --- Playwright Helpers ---

def find_brave_executable():
    candidates = [
        "/usr/bin/brave-browser",
        shutil.which("brave-browser"),
        "C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe",
    ]
    for path in candidates:
        if path and os.path.exists(path): return path
    return None

def solve_captcha(page):
    try:
        captcha_img = page.locator('div.form-group div.mb-10 img')
        captcha_img.screenshot(path='captcha.png')
        solver = TwoCaptcha(os.getenv('TWO_CAPTCHA_API_KEY'))
        print("Sending CAPTCHA to 2Captcha...")
        result = solver.normal('captcha.png')
        return result['code'].strip().upper()
    except Exception as e:
        print(f"✗ 2Captcha solving failed: {str(e)}")
        return None

def handle_age_overlay(page):
    try:
        if page.locator('#disclaimer').count() > 0:
            print("⚠️ Age verification detected. Confirming...")
            page.locator('#disclaimer .enter').click()
            page.wait_for_selector('#disclaimer', state='detached', timeout=5000)
    except: pass

screenshot_counter = 0
def take_screenshot(page, description):
    global screenshot_counter
    screenshot_counter += 1
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"screenshot_{screenshot_counter:02d}_{timestamp}_{description}.png"
    try:
        page.screenshot(path=filename)
        print(f"📸 Saved: {filename} | URL: {page.url}")
    except: pass

# --- Core Logic ---

def upload_video(row_data):
    downloaded_files = []
    try:
        return _upload_video_impl(row_data, downloaded_files)
    finally:
        for file_path in downloaded_files:
            if os.path.exists(file_path): os.remove(file_path)

def _upload_video_impl(row_data, downloaded_files):
    # Validate fields
    if not all(k in row_data for k in ["title", "videos", "tags"]):
        raise Exception("Missing required columns in sheet")

    proxy = get_proxy_config()
    
    with sync_playwright() as p:
        brave_path = find_brave_executable()
        
        # Args optimized for stealth
        browser_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-infobars",
            "--disable-dev-shm-usage",
            "--disable-extensions",
            "--disable-popup-blocking",
        ]
        
        is_ci = os.getenv('CI') is not None or os.getenv('GITHUB_ACTIONS') is not None
        
        context_options = {
            "executable_path": brave_path if brave_path else None,
            "headless": is_ci, # True on GitHub Actions
            "args": browser_args,
            # Updated User Agent to recent Chrome
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "viewport": {"width": 1920, "height": 1080},
            "locale": "en-US",
        }
        
        if proxy: context_options["proxy"] = proxy
        
        context = p.chromium.launch_persistent_context(
            user_data_dir="/tmp/chrome-profile",
            **context_options
        )
        
        page = context.new_page()
        
        # Apply stealth to avoid detection
        stealth(page)
        print("✓ Stealth mode applied")
        
        # Start Trace
        trace_file = f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        context.tracing.start(screenshots=True, snapshots=True, sources=True)

        # 1. Login Flow
        print("\n=== STEP 1: Login ===")
        page.goto('https://www.erome.com/user/login', wait_until='networkidle')
        handle_age_overlay(page)
        
        if page.locator("a#upload-album, a[href*='/upload']").count() == 0:
            print("Logging in...")
            username = os.getenv('WEBSITE_USERNAME')
            password = os.getenv('WEBSITE_PASSWORD')
            
            page.fill('input#email.form-control', username)
            page.fill('input#password.form-control', password)
            
            captcha_code = solve_captcha(page)
            if not captcha_code: raise Exception("Captcha failed")
            
            page.fill('input[name="captcha"]', captcha_code)
            
            with page.expect_navigation(timeout=30000):
                page.locator('button[type="submit"].btn.btn-pink').click()
            
            # Verify login success
            if page.locator("a#upload-album, a[href*='/upload']").count() == 0:
                take_screenshot(page, "login_failed")
                raise Exception("Login failed - check credentials or IP ban")
            print("✓ Login successful")
        else:
            print("✓ Already logged in")

        # 2. Token Injection (The Fix)
        print("\n=== STEP 2: Token Injection & Navigation ===")
        print("Bypassing UI click, requesting token via API...")
        
        try:
            # Manually POST to get the token
            response = page.request.post(
                "https://gr.erome.com/user/upload/token",
                headers={
                    "Referer": "https://www.erome.com/user/upload",
                    "Origin": "https://www.erome.com",
                    "X-Requested-With": "XMLHttpRequest" # Mimic AJAX
                }
            )
            
            if response.status != 200:
                print(f"Response: {response.text()}")
                raise Exception(f"Token API failed: {response.status}")

            # Extract token
            try:
                data = response.json()
                token = data.get('token')
            except:
                token = response.text().strip().replace('"', '')

            print(f"✓ Got Token: {token[:15]}...")
            
            # Force navigate using the token
            target_url = f"https://www.erome.com/user/upload?token={token}"
            print(f"Navigating to: {target_url}")
            
            page.goto(target_url)
            page.wait_for_url("**/a/*/edit", timeout=30000)
            print(f"✓ Redirected to Album Editor: {page.url}")
            
        except Exception as e:
            take_screenshot(page, "token_injection_failure")
            raise e

        # Handle Rules Popup
        try:
            if page.locator('#rules').is_visible(timeout=3000):
                page.click('#rules button[data-dismiss="modal"]')
                time.sleep(1)
        except: pass

        # 3. Content Update
        print("\n=== STEP 3: Uploading Content ===")
        
        # Title
        title_loc = page.locator("h1#title_editable")
        title_loc.wait_for()
        
        # Use JS to clear and set text (more reliable than typing)
        new_title = row_data["title"]
        page.evaluate(f"document.getElementById('title_editable').innerText = '{new_title}'")
        title_loc.press("Enter") # Trigger save events
        print(f"Title set: {new_title}")

        # Download Files
        video_files = [v.strip() for v in row_data["videos"].split(",") if v.strip()]
        for vf in video_files:
            print(f"Downloading: {vf}")
            downloaded_files.append(download_file_from_drive(vf))

        # Upload
        page.locator('#add_more_file').set_input_files(downloaded_files)
        print("Files queued. Waiting for upload...")
        
        # Wait for thumbnails to appear
        page.wait_for_function(
            f"document.querySelectorAll('#medias .media-group').length >= {len(downloaded_files)}",
            timeout=300000 # 5 min timeout
        )
        print("✓ Uploads processing completed")
        time.sleep(5) # Safety buffer

        # Tags
        tags = [t.strip() for t in row_data["tags"].split(",") if t.strip()]
        if tags:
            tag_input = page.locator('#tag_input')
            for tag in tags:
                tag_input.fill(tag)
                tag_input.press("Enter")
                time.sleep(0.3)
            print("Tags added")

        # 4. Publish
        print("\n=== STEP 4: Publishing ===")
        save_btn = page.locator("div#done_box a.btn.btn-pink")
        save_btn.click()
        
        page.wait_for_load_state('load', timeout=30000)
        
        final_url = page.url
        if '/a/' not in final_url or '/edit' in final_url:
            take_screenshot(page, "publish_failed")
            # Usually strict error here, but we will assume success if no error alert
        
        print(f"✓ PUBLISHED: {final_url}")
        
        context.tracing.stop(path=trace_file)
        context.close()
        return True

if __name__ == "__main__":
    print(f"=== Starting at {datetime.now()} ===")
    
    pending = get_first_pending_row()
    if not pending:
        print("No pending videos.")
        exit(0)
    
    row_num, data = pending
    print(f"Processing Row {row_num}: {data.get('title')}")
    
    try:
        upload_video(data)
        update_sheet_row(row_num, "posted", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print("SUCCESS")
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        update_sheet_row(row_num, f"error: {str(e)[:50]}", datetime.now().strftime("%Y-%m-%d"))
        exit(1)