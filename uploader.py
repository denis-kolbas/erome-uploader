import os
import time
import shutil
import json
import requests
import urllib.parse
from datetime import datetime
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
try:
    from playwright_stealth import stealth_sync
    STEALTH_AVAILABLE = True
except ImportError:
    print("⚠️ playwright-stealth not available, continuing without it")
    STEALTH_AVAILABLE = False

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

# Load environment variables
load_dotenv()

# --- HARDCODED COOKIES ---
# Ensure these are fresh from your browser!
RAW_XSRF_TOKEN = "eyJpdiI6IlNya3J1aXF1M2FuRldqV3RGSFgzcnc9PSIsInZhbHVlIjoiU0V5STVaOWJIVFFIRmJoSHFKak51Y3JNQ1wvaHIxT09EQjlPc1pOZEg3RE9Uak5nM3plcVkzZ1RyMk5wbWd3cXdsMmNGejB5QXphejlzWmtnejdrT3ZBPT0iLCJtYWMiOiJkMzdkZjkxOWIwMTQxZWE4MzdmMDc5ZGYzYmVhYTA3ZjMzODYwODg4MTZiNGMwYjNkNTNlZGJhMDQwMmUwN2RhIn0%3D" 
RAW_EROME_SESSION = "eyJpdiI6InJWazB0bzMzWW5BWExaK3I2YVlxekE9PSIsInZhbHVlIjoidzRsUFBrWStnQm80Tk9CWXBBbDYyRXlldGkxNkltVGh1OXdPcDJDYVhFK204Rlc5TERzamZ0QnU3dTRTcDk3M2pHNzdsTWtXZXZRZHlwSzR2REZld0E9PSIsIm1hYyI6IjgxMzY1MmQ5NjRiYzE1MmEyYWM2MGZkNjU4YWUxMTgyYTVjMGY2ZTM1ODFmNTMyZmI1YTVjYmFkYzIwOWJmYWEifQ%3D%3D"

# --- CONFIG ---
SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SHEET_NAME = "calendar"
DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
VIDEO_DOWNLOAD_PATH = "/tmp/Ero/videos"

PROXY_ENABLED = os.getenv("PROXY_ENABLED", "true").lower() == "true"
PROXY_HOST = os.getenv("PROXY_HOST", "p.webshare.io")
PROXY_PORT = os.getenv("PROXY_PORT", "80")
PROXY_USERNAME = os.getenv("PROXY_USERNAME", "mhcbvnkx-rotate")
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD", "wsramyu1qzh0")

# --- HELPERS ---

def find_brave_executable():
    """Locate Brave browser binary"""
    candidates = [
        "/usr/bin/brave-browser",
        "/usr/bin/brave",
        shutil.which("brave-browser"),
        shutil.which("brave"),
        "C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe",
        "C:\\Program Files (x86)\\BraveSoftware\\Brave-Browser\\Application\\brave.exe",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None

def get_proxy_config_dict():
    if not PROXY_ENABLED: return None
    return {
        'server': f'http://{PROXY_HOST}:{PROXY_PORT}',
        'username': PROXY_USERNAME,
        'password': PROXY_PASSWORD
    }

def get_proxy_string():
    if not PROXY_ENABLED: return None
    return f"http://{PROXY_USERNAME}:{PROXY_PASSWORD}@{PROXY_HOST}:{PROXY_PORT}"

# Init Google
if not os.path.exists(VIDEO_DOWNLOAD_PATH): os.makedirs(VIDEO_DOWNLOAD_PATH)
creds_info = json.loads(SERVICE_ACCOUNT_JSON)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.readonly"]
creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
sheets_service = build('sheets', 'v4', credentials=creds)
drive_service = build('drive', 'v3', credentials=creds)

def get_first_pending_row():
    try:
        sheet_range = f"{SHEET_NAME}!A1:E"
        sheet_data = sheets_service.spreadsheets().values().get(spreadsheetId=SHEET_ID, range=sheet_range).execute()
        rows = sheet_data.get("values", [])
        if len(rows) < 2: return None
        header = rows[0]
        for i, row in enumerate(rows[1:], start=2):
            status_idx = header.index("status")
            if len(row) <= status_idx or row[status_idx] == "":
                return i, dict(zip(header, row))
        return None
    except Exception as e:
        print(f"✗ Sheet Error: {e}")
        return None

def update_sheet_row(row_number, status, timestamp):
    values = [[status, timestamp]]
    body = {"values": values}
    range_to_update = f"{SHEET_NAME}!D{row_number}:E{row_number}"
    sheets_service.spreadsheets().values().update(
        spreadsheetId=SHEET_ID, range=range_to_update, valueInputOption="RAW", body=body
    ).execute()

def download_file_from_drive(file_name):
    print(f"   Downloading from Drive: {file_name}...")
    file_name_with_ext = f"{file_name}.mp4" if not file_name.endswith('.mp4') else file_name
    query = f"name='{file_name_with_ext}' and '{DRIVE_FOLDER_ID}' in parents and trashed=false"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    if not files: raise Exception(f"File not found in Drive: {file_name_with_ext}")
    file_id = files[0]["id"]
    request = drive_service.files().get_media(fileId=file_id)
    save_path = os.path.join(VIDEO_DOWNLOAD_PATH, file_name_with_ext)
    fh = io.FileIO(save_path, 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done: status, done = downloader.next_chunk()
    fh.close()
    return save_path

# --- PHASE 1: API (GET URL) ---

def get_edit_url_via_api():
    print("Step 1: Requesting Token via API...")
    decoded_xsrf = urllib.parse.unquote(RAW_XSRF_TOKEN)
    proxies = None
    proxy_str = get_proxy_string()
    if proxy_str: proxies = {"http": proxy_str, "https": proxy_str}

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "X-XSRF-TOKEN": decoded_xsrf,
        "Cookie": f"XSRF-TOKEN={RAW_XSRF_TOKEN}; erome_session={RAW_EROME_SESSION}"
    })

    try:
        r = session.post("https://gr.erome.com/user/upload/token", proxies=proxies, timeout=30)
        if r.status_code != 200:
            print(f"   ✗ API Token Refused: {r.status_code}")
            return None
        try: token = r.json().get('token')
        except: token = r.text.strip().replace('"', '')
        print(f"   ✓ Token: {token[:10]}...")

        url = f"https://www.erome.com/user/upload?token={token}"
        r = session.get(url, allow_redirects=False, proxies=proxies, timeout=30)
        if r.status_code == 302:
            edit_url = r.headers['Location']
            print(f"   ✓ Edit URL: {edit_url}")
            return edit_url
        return None
    except Exception as e:
        print(f"   ✗ API Error: {e}")
        return None

# --- PHASE 2: PLAYWRIGHT (BRAVE) ---

def handle_popups(page):
    """
    Destroys popups/overlays instead of clicking them.
    Clicking the disclaimer causes a redirect which breaks automation.
    """
    print("   Checking for Popups/Overlays...")
    
    # 1. DELETE THE DISCLAIMER (Don't Click It)
    try:
        if page.locator('#disclaimer').is_visible(timeout=3000):
            print("   ⚠️ Disclaimer detected. Removing from DOM...")
            page.evaluate("document.getElementById('disclaimer').remove()")
            page.evaluate("document.body.style.overflow = 'visible'")
            print("   ✓ Disclaimer removed")
    except Exception:
        pass

    # 2. Close Rules Modal
    try:
        if page.locator('#rules').is_visible(timeout=2000):
            print("   ⚠️ Rules Modal detected. Closing...")
            page.locator('#rules button[data-dismiss="modal"]').click()
            try: page.wait_for_selector('.modal-backdrop', state='detached', timeout=3000)
            except: pass 
            print("   ✓ Rules Modal closed")
    except Exception:
        pass

def upload_video_hybrid(row_data):
    # 1. Download
    video_names = [v.strip() for v in row_data["videos"].split(",") if v.strip()]
    downloaded_files = []
    
    try:
        for v in video_names:
            downloaded_files.append(download_file_from_drive(v))
            
        # 2. Get URL
        edit_url = get_edit_url_via_api()
        if not edit_url: raise Exception("Failed to get API URL")
            
        # 3. Playwright with Brave
        print("\nStep 2: Switching to Brave Browser...")
        brave_path = find_brave_executable()
        if brave_path:
            print(f"   ✓ Found Brave at: {brave_path}")
        else:
            print("   ⚠️ Brave not found! Falling back to standard Chromium")
        
        with sync_playwright() as p:
            proxy_conf = get_proxy_config_dict()
            
            browser = p.chromium.launch(
                executable_path=brave_path,
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
                proxy=proxy_conf
            )
            
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            
            # Inject Cookies
            context.add_cookies([
                {"name": "erome_session", "value": RAW_EROME_SESSION.replace("%3D", "=") if "%3D" in RAW_EROME_SESSION else RAW_EROME_SESSION, "domain": ".erome.com", "path": "/"},
                {"name": "XSRF-TOKEN", "value": RAW_XSRF_TOKEN, "domain": ".erome.com", "path": "/"}
            ])
            print("   ✓ Cookies injected")
            
            page = context.new_page()
            if STEALTH_AVAILABLE: stealth_sync(page)

            print(f"   Navigating to: {edit_url}")
            page.goto(edit_url, timeout=60000)
            page.wait_for_load_state('domcontentloaded')
            time.sleep(2)

            # --- HANDLE POPUPS ---
            handle_popups(page)
            time.sleep(1)

            # --- TYPING TITLE (SAFE BRUTE FORCE) ---
            print("   Typing Title...")
            new_title = row_data["title"]
            
            try:
                # 1. Visual Typing
                title_box = page.locator("h1#title_editable")
                title_box.click(force=True)
                time.sleep(0.5)
                page.keyboard.press("Control+A") 
                page.keyboard.press("Backspace")
                page.keyboard.type(new_title, delay=50)
                
                # 2. Trigger Events
                page.keyboard.press("Tab") # Blur
                
                # 3. FORCE SET HIDDEN INPUT (Crucial Fix)
                # This guarantees the server gets the title even if JS listeners fail
                print("   Applying title safety patch...")
                page.evaluate(f"""
                    // Update visual
                    document.getElementById('title_editable').innerText = "{new_title}";
                    // Update hidden input
                    var hiddenInput = document.getElementById('album_title');
                    if(hiddenInput) {{ hiddenInput.value = "{new_title}"; }}
                """)
                time.sleep(1)
                print(f"   ✓ Title set (Visual & Hidden Input)")

            except Exception as e:
                print(f"   ⚠️ Error setting title: {e}")

            # --- UPLOAD ---
            print(f"   Uploading {len(downloaded_files)} files...")
            page.set_input_files('#add_more_file', downloaded_files)
            
            print("   Waiting for processing...")
            try:
                page.wait_for_function(
                    f"document.querySelectorAll('#medias .media-group').length >= {len(downloaded_files)}",
                    timeout=300000
                )
                print("   ✓ Uploads processed")
            except:
                print("   ⚠️ Timeout waiting for thumbnails (check screenshot)")
                page.screenshot(path="upload_timeout.png")
            
            time.sleep(5)

            # --- TAGS ---
            tags = [t.strip() for t in row_data["tags"].split(",") if t.strip()]
            if tags:
                print("   Adding Tags...")
                tag_input = page.locator('#tag_input')
                for tag in tags:
                    tag_input.fill(tag)
                    time.sleep(0.2)
                    tag_input.press("Enter")
                    time.sleep(0.5)

            # --- PUBLISHING ---
            print("   Publishing (Waiting 5s)...")
            time.sleep(5) 
            
            save_btn = page.locator("div#done_box a.btn.btn-pink")
            save_btn.scroll_into_view_if_needed()
            
            print("   Clicking SAVE...")
            save_btn.click(force=True)
            
            print("   Waiting for redirection...")
            start_time = time.time()
            success = False
            
            while time.time() - start_time < 60:
                current_url = page.url
                if "/edit" not in current_url and "/a/" in current_url:
                    print(f"   ✓ REDIRECT DETECTED: {current_url}")
                    success = True
                    break
                
                if page.locator(".alert-danger").is_visible():
                    err = page.locator(".alert-danger").text_content()
                    print(f"   ✗ Error on page: {err}")
                    break
                    
                time.sleep(1)
                
            if not success:
                print(f"   ✗ Failed to redirect. Stuck on: {page.url}")
                page.screenshot(path="stuck_on_publish.png")
                raise Exception("Publish click didn't redirect")
            
            print(f"✓ SUCCESS! Published: {page.url}")
            return True

    except Exception as e:
        print(f"✗ Process Failed: {e}")
        raise e
    finally:
        for f in downloaded_files:
            if os.path.exists(f): os.remove(f)

if __name__ == "__main__":
    print(f"=== Hybrid Brave Uploader Starting at {datetime.now()} ===")
    pending = get_first_pending_row()
    if not pending:
        print("No pending videos.")
        exit(0)
    
    row_num, data = pending
    print(f"Processing Row {row_num}: {data.get('title')}")
    
    try:
        upload_video_hybrid(data)
        update_sheet_row(row_num, "posted", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        try: update_sheet_row(row_num, f"error: {str(e)[:50]}", datetime.now().strftime("%Y-%m-%d"))
        except: pass
        exit(1)