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

# Proxy configuration - Webshare.io rotating proxy
PROXY_ENABLED = os.getenv("PROXY_ENABLED", "true").lower() == "true"
PROXY_HOST = os.getenv("PROXY_HOST", "p.webshare.io")
PROXY_PORT = os.getenv("PROXY_PORT", "80")
PROXY_USERNAME = os.getenv("PROXY_USERNAME", "mhcbvnkx-rotate")
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD", "wsramyu1qzh0")

def get_proxy_config():
    """Get proxy configuration for Playwright"""
    proxy_env_value = os.getenv("PROXY_ENABLED", "true")
    print(f"PROXY_ENABLED env value: '{proxy_env_value}' (type: {type(proxy_env_value)})")
    print(f"PROXY_ENABLED parsed: {PROXY_ENABLED}")
    
    if not PROXY_ENABLED:
        print("⚠️ Proxy is DISABLED - running without proxy")
        return None
    
    proxy = {
        'server': f'http://{PROXY_HOST}:{PROXY_PORT}',
        'username': PROXY_USERNAME,
        'password': PROXY_PASSWORD
    }
    print(f"✓ Using rotating proxy: {PROXY_HOST}:{PROXY_PORT} with user: {PROXY_USERNAME}")
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

# Screenshot counter for sequential naming
screenshot_counter = 0

def take_screenshot(page, description):
    """Take a screenshot with detailed logging"""
    global screenshot_counter
    screenshot_counter += 1
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"screenshot_{screenshot_counter:02d}_{timestamp}_{description}.png"
    
    try:
        page.screenshot(path=filename)
        current_url = page.url
        page_title = page.title()
        print(f"📸 Screenshot {screenshot_counter}: {description}")
        print(f"   URL: {current_url}")
        print(f"   Title: {page_title}")
        print(f"   File: {filename}")
    except Exception as e:
        print(f"⚠️ Failed to take screenshot: {e}")

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
    
    # Get proxy configuration
    print("\n" + "="*60)
    print("Proxy Configuration")
    print("="*60)
    proxy = get_proxy_config()
    print("="*60 + "\n")
    
    with sync_playwright() as p:
        brave_path = find_brave_executable()
        browser_args = [
            "--disable-popup-blocking",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox"
        ]
        user_data_dir = "/tmp/chrome-profile"
        
        # Use headless mode in CI/production, headed locally
        is_ci = os.getenv('CI') is not None or os.getenv('GITHUB_ACTIONS') is not None
        headless_mode = is_ci
        
        if brave_path:
            user_data_dir = "/tmp/brave-profile"
            browser_args += ["--brave-shields-up","--no-default-browser-check","--no-first-run"]

        # Browser context options
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
        
        # Start tracing
        trace_dir = "/tmp/traces"
        os.makedirs(trace_dir, exist_ok=True)
        trace_file = os.path.join(trace_dir, f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip")
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        print(f"✓ Started Playwright trace: {trace_file}")
        
        # Monitor network requests to see what's happening
        network_log = []
        def log_request(request):
            network_log.append({
                'url': request.url,
                'method': request.method,
                'headers': dict(request.headers)
            })
        
        def log_response(response):
            if 'upload' in response.url or 'album' in response.url:
                print(f"📡 Network: {response.status} {response.request.method} {response.url}")
        
        page.on('request', log_request)
        page.on('response', log_response)
        
        # Validate proxy connection by checking IP
        if proxy:
            print("\n" + "="*60)
            print("Validating Proxy Connection")
            print("="*60)
            try:
                page.goto('https://api.ipify.org?format=json', wait_until='networkidle', timeout=10000)
                ip_info = page.content()
                print(f"✓ Proxy IP check response: {ip_info}")
                
                # Also check with another service
                page.goto('https://ifconfig.me/ip', wait_until='networkidle', timeout=10000)
                ip_text = page.locator('body').text_content()
                print(f"✓ Current IP address: {ip_text.strip()}")
                print("✓ Proxy connection validated!")
            except Exception as e:
                print(f"⚠️ Proxy validation failed: {e}")
                print("⚠️ Continuing anyway...")
            print("="*60 + "\n")
        
        # Navigate to site
        print("\n" + "="*60)
        print("STEP 1: Navigate to erome.com")
        print("="*60)
        page.goto('https://www.erome.com/explore', wait_until='networkidle')
        time.sleep(1)
        take_screenshot(page, "01_initial_page")
        
        handle_age_overlay(page)
        time.sleep(1)
        take_screenshot(page, "02_after_age_verification")

        # Check if logged in by looking for upload button
        print("\n" + "="*60)
        print("STEP 2: Check login status")
        print("="*60)
        
        # Wait a bit for page to fully load
        time.sleep(2)
        
        # Check for upload button (visible when logged in)
        upload_button_check = page.locator("a#upload-album, a[href*='/upload']")
        is_logged_in = upload_button_check.count() > 0
        
        # Also check for other logged-in indicators
        user_menu = page.locator('.user-menu, .dropdown-toggle, a[href*="/user/"]')
        logout_button = page.locator('a[href*="logout"]')
        
        print(f"Upload button found: {is_logged_in}")
        print(f"User menu found: {user_menu.count() > 0}")
        print(f"Logout button found: {logout_button.count() > 0}")
        print(f"Current URL: {page.url}")
        
        # Verify session by checking cookies
        cookies = page.context.cookies()
        session_cookies = [c for c in cookies if 'session' in c['name'].lower() or 'remember' in c['name'].lower()]
        print(f"Session cookies found: {len(session_cookies)}")
        for cookie in session_cookies:
            print(f"  - {cookie['name']}: {cookie['value'][:20]}...")
        
        # If upload button not visible, we need to login
        if not is_logged_in:
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
                take_screenshot(page, f"03_login_page_attempt_{attempt}")
                
                print(f"  Filling username: {username[:3]}***")
                page.fill('input#email.form-control', username)
                time.sleep(0.5)
                
                print(f"  Filling password: ***")
                page.fill('input#password.form-control', password)
                time.sleep(0.5)
                take_screenshot(page, f"04_credentials_filled_attempt_{attempt}")
                
                print("  Solving captcha...")
                captcha_solution = solve_captcha(page)
                if not captcha_solution:
                    print(f"  ✗ Captcha solving failed on attempt {attempt}")
                    take_screenshot(page, f"05_captcha_failed_attempt_{attempt}")
                    if attempt < max_login_attempts:
                        print("  Retrying...")
                        continue
                    else:
                        raise Exception("Captcha solving failed after all attempts")
                
                print(f"  Filling captcha: {captcha_solution}")
                page.fill('input[name="captcha"]', captcha_solution)
                time.sleep(1)
                take_screenshot(page, f"06_before_submit_attempt_{attempt}")
                
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
                take_screenshot(page, f"07_after_submit_attempt_{attempt}")
                
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
                    take_screenshot(page, f"08_login_success_attempt_{attempt}")
                    break
                else:
                    print(f"  ✗ Login failed on attempt {attempt}")
                    take_screenshot(page, f"08_login_failed_attempt_{attempt}")
                    if attempt < max_login_attempts:
                        print("  Captcha was likely wrong. Retrying with new captcha...")
                        time.sleep(2)
                    else:
                        print("  ✗ All login attempts failed")
            
            if not login_successful:
                raise Exception(f"Login failed after {max_login_attempts} attempts")
        else:
            print("✓ Already logged in")

        # Navigate to upload
        print("\n" + "="*60)
        print("STEP 3: Navigate to upload page")
        print("="*60)
        
        # Find the upload button
        print("Looking for upload button...")
        
        # Try to find all possible upload buttons
        upload_selectors = [
            "a#upload-album",
            "a[href*='/upload']",
            "a[href='/user/upload']",
            ".upload-button",
            "button:has-text('Upload')",
        ]
        
        upload_button = None
        for selector in upload_selectors:
            try:
                btn = page.locator(selector).first
                if btn.count() > 0:
                    print(f"✓ Found upload button with selector: {selector}")
                    upload_button = btn
                    break
            except:
                continue
        
        if not upload_button:
            take_screenshot(page, "ERROR_no_upload_button")
            # Get all links on the page for debugging
            all_links = page.locator('a').all()
            print(f"Total links on page: {len(all_links)}")
            for i, link in enumerate(all_links[:10]):  # Show first 10
                try:
                    href = link.get_attribute('href')
                    text = link.text_content()
                    print(f"  Link {i}: href={href}, text={text}")
                except:
                    pass
            raise Exception("Upload button not found on page")
        
        upload_button.wait_for(state='visible', timeout=10000)
        print(f"Upload button is visible, current URL: {page.url}")
        
        # Get button details for debugging
        try:
            btn_href = upload_button.get_attribute('href')
            btn_text = upload_button.text_content()
            btn_id = upload_button.get_attribute('id')
            btn_class = upload_button.get_attribute('class')
            print(f"Button details: href={btn_href}, text={btn_text}, id={btn_id}, class={btn_class}")
        except Exception as e:
            print(f"Could not get button details: {e}")
        
        # Scroll to button to ensure it's in view
        upload_button.scroll_into_view_if_needed()
        time.sleep(0.5)
        
        # Check for CSRF tokens on the page
        try:
            csrf_meta = page.locator('meta[name="csrf-token"]')
            if csrf_meta.count() > 0:
                csrf_token = csrf_meta.get_attribute('content')
                print(f"CSRF token found: {csrf_token[:20]}...")
            
            # Also check for tokens in forms
            csrf_inputs = page.locator('input[name="_token"], input[name="csrf_token"], input[name="authenticity_token"]')
            if csrf_inputs.count() > 0:
                print(f"CSRF input fields found: {csrf_inputs.count()}")
        except Exception as e:
            print(f"No CSRF tokens found on page")
        
        take_screenshot(page, "before_upload_click")
        
        # Store the current URL to detect changes
        initial_url = page.url
        
        # Try multiple click methods with retries
        print("Clicking upload button...")
        click_methods = [
            ("Regular click", lambda: upload_button.click()),
            ("Force click", lambda: upload_button.click(force=True)),
            ("Click with delay", lambda: (upload_button.click(delay=100), time.sleep(0.5))),
            ("JavaScript click", lambda: page.evaluate("document.querySelector('a#upload-album, a[href*=\"/upload\"]').click()")),
            ("Dispatch click event", lambda: upload_button.dispatch_event('click')),
        ]
        
        click_succeeded = False
        for method_name, click_func in click_methods:
            try:
                print(f"  Trying: {method_name}...")
                click_func()
                print(f"  ✓ {method_name} completed")
                click_succeeded = True
                time.sleep(1)  # Give it a moment to process
                
                # Check if anything changed (URL or modal appeared)
                if page.url != initial_url or page.locator('#rules').count() > 0:
                    print(f"  ✓ {method_name} triggered a response!")
                    break
                else:
                    print(f"  ⚠️ {method_name} didn't trigger navigation, trying next method...")
            except Exception as e:
                print(f"  ✗ {method_name} failed: {e}")
                continue
        
        if not click_succeeded:
            raise Exception("All click methods failed")
        
        print("✓ Button click completed, waiting for response...")
        
        # Check for any error messages or alerts
        time.sleep(1)
        try:
            # Check for alert/error messages
            error_selectors = ['.alert-danger', '.alert-error', '.error-message', '.toast-error']
            for selector in error_selectors:
                error_elem = page.locator(selector)
                if error_elem.count() > 0:
                    error_text = error_elem.text_content()
                    print(f"⚠️ Error message detected: {error_text}")
                    take_screenshot(page, "error_message_after_click")
        except:
            pass
        
        # Wait for URL to change (polling approach)
        print("Waiting for navigation to complete...")
        max_wait = 30  # 30 seconds max
        wait_interval = 0.5
        elapsed = 0
        navigation_success = False
        popup_checked = False
        
        while elapsed < max_wait:
            current_url = page.url
            
            # Check for rules popup (appears after clicking upload button)
            if not popup_checked or elapsed % 1 == 0:  # Check every second
                try:
                    # Check multiple ways to detect the modal
                    rules_modal = page.locator('#rules')
                    
                    # Check if modal exists and is displayed
                    if rules_modal.count() > 0:
                        display_style = rules_modal.get_attribute('style')
                        modal_class = rules_modal.get_attribute('class')
                        
                        # Modal is visible if it has "display: block" or class contains "in"
                        is_visible = ('display: block' in (display_style or '')) or ('in' in (modal_class or ''))
                        
                        if is_visible:
                            print(f"⚠️ Rules popup detected! (style={display_style}, class={modal_class})")
                            take_screenshot(page, "popup_rules_modal")
                            
                            # Click the close button
                            close_button = page.locator('#rules button[data-dismiss="modal"]')
                            if close_button.count() > 0:
                                close_button.click()
                                time.sleep(1)
                                print("✓ Rules popup closed")
                                popup_checked = True
                            else:
                                print("⚠️ Close button not found, trying alternative...")
                                # Try clicking outside the modal or pressing Escape
                                page.keyboard.press('Escape')
                                time.sleep(0.5)
                except Exception as e:
                    pass  # Popup not present or already closed
            
            # Check if we've navigated to the upload/edit page
            if current_url != initial_url and '/a/' in current_url:
                print(f"✓ Navigation detected! New URL: {current_url}")
                navigation_success = True
                break
            
            # Log progress every 2 seconds
            if elapsed % 2 == 0 and elapsed > 0:
                print(f"  Still waiting... ({elapsed}s elapsed, current URL: {current_url})")
            
            time.sleep(wait_interval)
            elapsed += wait_interval
        
        if not navigation_success:
            take_screenshot(page, "ERROR_navigation_failed")
            print(f"✗ Navigation timeout. Final URL: {page.url}")
            
            # Log recent network activity
            print("\n📡 Recent network requests:")
            for req in network_log[-10:]:  # Last 10 requests
                print(f"  {req['method']} {req['url']}")
            
            # Check console for errors
            print("\n🔍 Checking for JavaScript errors...")
            try:
                console_errors = page.evaluate("""
                    () => {
                        const errors = [];
                        const originalError = console.error;
                        console.error = function(...args) {
                            errors.push(args.join(' '));
                            originalError.apply(console, args);
                        };
                        return errors;
                    }
                """)
                if console_errors:
                    print(f"Console errors: {console_errors}")
            except:
                pass
            
            # Try JavaScript click as fallback
            print("Trying JavaScript click as fallback...")
            page.evaluate("document.querySelector('a#upload-album, a[href*=\"/upload\"]').click()")
            time.sleep(5)
            
            if '/a/' in page.url:
                print(f"✓ JavaScript click worked! URL: {page.url}")
                navigation_success = True
            else:
                raise Exception(f"Failed to navigate to upload page. Current URL: {page.url}")
        
        # Wait for page to be fully loaded
        page.wait_for_load_state('domcontentloaded')
        time.sleep(2)
        
        # Final check for rules modal (in case it appears after navigation)
        try:
            rules_modal = page.locator('#rules:visible')
            if rules_modal.count() > 0:
                print("⚠️ Rules modal still present, closing again...")
                page.locator('#rules button[data-dismiss="modal"]').click()
                time.sleep(0.5)
        except Exception as e:
            pass  # Modal not present
        
        take_screenshot(page, "10_upload_page_loaded")
        print(f"✓ Successfully on upload page: {page.url}")

        # Update title
        print("\n" + "="*60)
        print("STEP 4: Update album title")
        print("="*60)
        new_title = row_data["title"]
        print(f"New title: {new_title}")
        
        # Wait for title element to be available
        title_locator = page.locator("h1#title_editable.content-editable.album-title")
        title_locator.wait_for(state='visible', timeout=10000)
        
        title_handle = title_locator.element_handle()
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
        take_screenshot(page, "13_title_updated")

        # Upload files
        print("\n" + "="*60)
        print("STEP 5: Download and upload video files")
        print("="*60)
        video_files = [v.strip() for v in row_data["videos"].split(",") if v.strip()]
        print(f"Videos to upload: {video_files}")
        
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
        
        print(f"Starting file upload for {len(downloaded_files)} file(s)...")
        file_input = page.locator('#add_more_file')
        file_input.set_input_files(downloaded_files)
        print(f"✓ Files queued for upload: {len(downloaded_files)} file(s)")
        time.sleep(2)
        take_screenshot(page, "14_files_queued")
        
        # Wait for upload to complete
        print("\n" + "="*60)
        print("STEP 6: Wait for upload to complete")
        print("="*60)
        time.sleep(5)  # Initial wait for upload to start
        take_screenshot(page, "15_upload_started")
        
        # Check for video thumbnails in #medias div (indicates upload complete)
        max_wait = 300  # 5 minutes max wait
        wait_interval = 10
        elapsed = 0
        
        while elapsed < max_wait:
            # Check if videos appear in the medias container
            media_items = page.locator('#medias .media-group, #medias video, #medias img').count()
            if media_items >= len(downloaded_files):
                print(f"✓ All {len(downloaded_files)} file(s) uploaded successfully")
                take_screenshot(page, "16_upload_complete")
                break
            
            print(f"Upload in progress... ({elapsed}s elapsed, {media_items}/{len(downloaded_files)} files visible)")
            if elapsed % 30 == 0:  # Screenshot every 30 seconds
                take_screenshot(page, f"upload_progress_{elapsed}s")
            time.sleep(wait_interval)
            elapsed += wait_interval
        
        if elapsed >= max_wait:
            print(f"⚠️ Upload timeout reached. Proceeding anyway...")
            take_screenshot(page, "16_upload_timeout")
        
        # Extra wait to ensure processing is complete
        print("Waiting additional time for upload processing...")
        time.sleep(60)  # 1 minute extra wait
        take_screenshot(page, "17_after_processing_wait")

        # Add tags
        print("\n" + "="*60)
        print("STEP 7: Add tags")
        print("="*60)
        tags = [t.strip() for t in row_data["tags"].split(",") if t.strip()]
        print(f"Tags to add: {tags}")
        
        if tags:
            tags_input = page.locator('#tag_input')
            for tag in tags:
                tags_input.fill(tag)
                tags_input.press("Enter")
                time.sleep(0.5)
            print(f"✓ Tags added: {', '.join(tags)}")
            take_screenshot(page, "18_tags_added")
        else:
            print("⚠️ No tags to add")

        # Save / publish
        print("\n" + "="*60)
        print("STEP 8: Save and publish album")
        print("="*60)
        time.sleep(3)
        take_screenshot(page, "19_before_save")
        
        save_button = page.locator("div#done_box a.btn.btn-pink")
        if save_button.count() == 0:
            take_screenshot(page, "ERROR_save_button_not_found")
            raise Exception("Save button not found - upload may have failed")
        
        # Get the redirect URL from onclick before clicking
        onclick_attr = save_button.get_attribute('onclick')
        print(f"Save button onclick: {onclick_attr}")
        
        save_button.click()
        print("✓ Clicked SAVE to publish album")
        
        # Wait for redirect (the onclick has 200ms delay, then redirects)
        time.sleep(2)
        take_screenshot(page, "20_after_save_click")
        
        # Wait for page to load after redirect (use 'load' instead of 'networkidle')
        try:
            page.wait_for_load_state('load', timeout=15000)
        except Exception as e:
            print(f"⚠️ Page load timeout (this is usually fine): {e}")
        
        time.sleep(3)
        take_screenshot(page, "21_final_page")
        
        final_url = page.url
        print(f"✓ Upload complete. Final URL: {final_url}")
        
        # Verify we're on the album page (not still on upload page)
        if '/upload' in final_url:
            take_screenshot(page, "ERROR_still_on_upload_page")
            raise Exception("Still on upload page - album may not have been created")
        elif '/a/' in final_url:
            print("✓ Successfully redirected to album page")
            take_screenshot(page, "22_SUCCESS_album_page")
        else:
            print(f"⚠️ Unexpected URL pattern: {final_url}")
            take_screenshot(page, "WARNING_unexpected_url")
        
        # Stop tracing and save
        context.tracing.stop(path=trace_file)
        print(f"✓ Trace saved to: {trace_file}")
        
        # Close context
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