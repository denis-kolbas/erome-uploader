import os
import time
import shutil
import json
import urllib.parse
from datetime import datetime
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

# Load environment variables
load_dotenv()

try:
    from playwright_stealth import stealth_sync
    STEALTH_AVAILABLE = True
except ImportError:
    print("⚠️ playwright-stealth not available. ADD 'playwright-stealth' to requirements.txt")
    STEALTH_AVAILABLE = False

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

# --- HARDCODED COOKIES ---
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
    candidates = [
        "/usr/bin/brave-browser",
        "/usr/bin/brave",
        shutil.which("brave-browser"),
        shutil.which("brave"),
        "C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
    ]
    for path in candidates:
        if path and os.path.exists(path): return path
    return None

def get_proxy_config_dict():
    if not PROXY_ENABLED: return None
    return {
        'server': f'http://{PROXY_HOST}:{PROXY_PORT}',
        'username': PROXY_USERNAME,
        'password': PROXY_PASSWORD
    }

# Init Google
if not os.path.exists(VIDEO_DOWNLOAD_PATH): os.makedirs(VIDEO_DOWNLOAD_PATH)
try:
    creds_info = json.loads(SERVICE_ACCOUNT_JSON)
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.readonly"]
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    sheets_service = build('sheets', 'v4', credentials=creds)
    drive_service = build('drive', 'v3', credentials=creds)
except Exception as e:
    print(f"Google Init Failed: {e}")
    # Don't exit here to allow testing without google if needed, but usually we exit
    pass 

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

# --- POPUP HANDLER ---
def handle_popups(page):
    try:
        # 1. Remove Disclaimer (Don't click, just delete)
        if page.locator('#disclaimer').is_visible(timeout=3000):
            print("   ⚠️ Disclaimer detected. Removing from DOM...")
            page.evaluate("document.getElementById('disclaimer').remove()")
            page.evaluate("document.body.style.overflow = 'visible'")
            print("   ✓ Disclaimer removed")
    except: pass

    try:
        # 2. Close Rules
        if page.locator('#rules').is_visible(timeout=2000):
            print("   ⚠️ Rules Modal detected. Closing...")
            page.locator('#rules button[data-dismiss="modal"]').click()
            try: page.wait_for_selector('.modal-backdrop', state='detached', timeout=3000)
            except: pass
            print("   ✓ Rules Modal closed")
    except: pass

# --- MAIN UPLOAD LOGIC ---

def upload_video_full(row_data):
    # 1. Download Files
    video_names = [v.strip() for v in row_data["videos"].split(",") if v.strip()]
    downloaded_files = []
    
    try:
        for v in video_names:
            downloaded_files.append(download_file_from_drive(v))

        # 2. Start Playwright
        print("\nStep 2: Starting Browser...")
        brave_path = find_brave_executable()
        
        with sync_playwright() as p:
            proxy_conf = get_proxy_config_dict()
            browser = p.chromium.launch(
                executable_path=brave_path,
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
                proxy=proxy_conf
            )
            
            # 3. Inject Cookies
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            
            # Clean cookies (fix URL encoding chars)
            clean_session = RAW_EROME_SESSION.replace("%3D", "=") if "%3D" in RAW_EROME_SESSION else RAW_EROME_SESSION
            clean_xsrf = RAW_XSRF_TOKEN.replace("%3D", "=") if "%3D" in RAW_XSRF_TOKEN else RAW_XSRF_TOKEN
            
            context.add_cookies([
                {"name": "erome_session", "value": clean_session, "domain": ".erome.com", "path": "/"},
                {"name": "XSRF-TOKEN", "value": RAW_XSRF_TOKEN, "domain": ".erome.com", "path": "/"}
            ])
            print("   ✓ Cookies injected")

            # 4. API Handshake (USING BROWSER CONTEXT TO AVOID SSL ERRORS)
            print("   Performing Handshake via Browser API...")
            api_request = context.request
            
            decoded_xsrf = urllib.parse.unquote(RAW_XSRF_TOKEN)
            
            # A. Get Token
            token_resp = api_request.post(
                "https://gr.erome.com/user/upload/token",
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "X-XSRF-TOKEN": decoded_xsrf
                }
            )
            
            if not token_resp.ok:
                raise Exception(f"API Token Failed: {token_resp.status} {token_resp.text()}")
            
            try: token = token_resp.json().get('token')
            except: token = token_resp.text().strip().replace('"', '')
            print(f"   ✓ Token: {token[:10]}...")

            # B. Get Redirect URL (Edit URL)
            # We must use context.request.get to follow the redirect logic properly
            # Or manually construct it. Let's manually construct to avoid 302 handling issues in headless.
            # Usually: https://www.erome.com/user/upload?token={token} -> 302 -> /a/xxxx/edit
            
            # We will use the PAGE to navigate to the token URL. 
            # This is safer than API following redirects which might get blocked.
            
            page = context.new_page()
            if STEALTH_AVAILABLE: stealth_sync(page)
            
            handshake_url = f"https://www.erome.com/user/upload?token={token}"
            print(f"   Navigating to Handshake URL: {handshake_url}")
            
            page.goto(handshake_url, timeout=60000)
            
            # Wait for redirect to /edit
            try:
                page.wait_for_url("**/a/*/edit", timeout=30000)
                print(f"   ✓ Landed on Edit Page: {page.url}")
            except:
                print("   ⚠️ Redirect slow or failed. Checking page content...")
                if "login" in page.url:
                    raise Exception("Cookies expired - redirected to login")
            
            time.sleep(2)
            handle_popups(page)

            # 5. Type Title (Safety Patch)
            print("   Typing Title...")
            new_title = row_data["title"]
            try:
                title_box = page.locator("h1#title_editable")
                title_box.click(force=True)
                page.keyboard.press("Control+A"); page.keyboard.press("Backspace")
                page.keyboard.type(new_title, delay=50)
                page.keyboard.press("Tab")
                
                # FORCE HIDDEN INPUT
                page.evaluate(f"""
                    document.getElementById('title_editable').innerText = "{new_title}";
                    var h = document.getElementById('album_title');
                    if(h) h.value = "{new_title}";
                """)
                print(f"   ✓ Title set: {new_title}")
            except Exception as e:
                print(f"   ⚠️ Title Error: {e}")

            # 6. Upload
            print(f"   Uploading {len(downloaded_files)} files...")
            page.set_input_files('#add_more_file', downloaded_files)
            
            try:
                page.wait_for_function(
                    f"document.querySelectorAll('#medias .media-group').length >= {len(downloaded_files)}",
                    timeout=300000
                )
                print("   ✓ Uploads processed")
            except:
                print("   ⚠️ Upload timeout (proceeding)")
            
            time.sleep(5)

            # 7. Tags
            tags = [t.strip() for t in row_data["tags"].split(",") if t.strip()]
            if tags:
                tag_input = page.locator('#tag_input')
                for tag in tags:
                    tag_input.fill(tag)
                    time.sleep(0.2)
                    tag_input.press("Enter")
                    time.sleep(0.5)

            # 8. Publish
            print("   Publishing...")
            time.sleep(3)
            save_btn = page.locator("div#done_box a.btn.btn-pink")
            save_btn.scroll_into_view_if_needed()
            save_btn.click(force=True)
            
            start = time.time()
            success = False
            while time.time() - start < 60:
                if "/edit" not in page.url and "/a/" in page.url:
                    success = True
                    break
                if page.locator(".alert-danger").is_visible():
                    print(f"   ✗ Error: {page.locator('.alert-danger').text_content()}")
                    break
                time.sleep(1)
            
            if not success:
                page.screenshot(path="failed_publish.png")
                raise Exception("Publish failed or timed out")
            
            print(f"✓ PUBLISHED: {page.url}")
            return True

    except Exception as e:
        print(f"✗ Failed: {e}")
        raise e
    finally:
        for f in downloaded_files:
            if os.path.exists(f): os.remove(f)

if __name__ == "__main__":
    print(f"=== Erome Uploader v3 (Brave API) Starting {datetime.now()} ===")
    
    # Check dependencies
    if not STEALTH_AVAILABLE:
        print("!!! WARNING: playwright-stealth is missing. Install it to avoid bans !!!")

    pending = get_first_pending_row()
    if not pending:
        print("No pending videos.")
        exit(0)
    
    row_num, data = pending
    print(f"Processing Row {row_num}: {data.get('title')}")
    
    try:
        upload_video_full(data)
        update_sheet_row(row_num, "posted", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    except Exception as e:
        print(f"FATAL: {e}")
        try: update_sheet_row(row_num, f"error: {str(e)[:100]}", datetime.now().strftime("%Y-%m-%d"))
        except: pass
        exit(1)