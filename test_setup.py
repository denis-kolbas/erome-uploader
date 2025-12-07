"""
Test script to verify your Google Sheets/Drive setup
Run this to debug connection issues
"""
import os
import json
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

load_dotenv()

print("=== Testing Google Sheets/Drive Setup ===\n")

# Check environment variables
print("1. Checking environment variables...")
SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

if not SERVICE_ACCOUNT_JSON:
    print("✗ GOOGLE_SERVICE_ACCOUNT_JSON is not set")
    exit(1)
else:
    print("✓ GOOGLE_SERVICE_ACCOUNT_JSON is set")

if not SHEET_ID:
    print("✗ GOOGLE_SHEET_ID is not set")
    exit(1)
else:
    print(f"✓ GOOGLE_SHEET_ID: {SHEET_ID}")

if not DRIVE_FOLDER_ID:
    print("✗ GOOGLE_DRIVE_FOLDER_ID is not set")
    exit(1)
else:
    print(f"✓ GOOGLE_DRIVE_FOLDER_ID: {DRIVE_FOLDER_ID}")

# Parse service account JSON
print("\n2. Parsing service account JSON...")
try:
    creds_info = json.loads(SERVICE_ACCOUNT_JSON)
    service_email = creds_info.get("client_email")
    print(f"✓ Service account email: {service_email}")
    print(f"\n⚠️  Make sure you shared your Sheet and Drive folder with: {service_email}")
except json.JSONDecodeError as e:
    print(f"✗ Invalid JSON: {e}")
    exit(1)

# Set up credentials
print("\n3. Setting up credentials...")
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly"
]
try:
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    print("✓ Credentials created")
except Exception as e:
    print(f"✗ Failed to create credentials: {e}")
    exit(1)

# Test Sheets API
print("\n4. Testing Google Sheets API...")
try:
    sheets_service = build('sheets', 'v4', credentials=creds)
    
    # Get sheet metadata
    sheet_metadata = sheets_service.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    sheet_title = sheet_metadata.get('properties', {}).get('title', 'Unknown')
    print(f"✓ Connected to sheet: {sheet_title}")
    
    # List all tabs
    sheets = sheet_metadata.get('sheets', [])
    print(f"\n  Available tabs:")
    for sheet in sheets:
        tab_name = sheet.get('properties', {}).get('title', 'Unknown')
        print(f"    - {tab_name}")
    
    # Check if 'calendar' tab exists
    tab_names = [s.get('properties', {}).get('title') for s in sheets]
    if 'calendar' in tab_names:
        print(f"\n✓ 'calendar' tab exists")
        
        # Try to read data
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range='calendar!A1:E'
        ).execute()
        rows = result.get('values', [])
        print(f"✓ Read {len(rows)} rows from 'calendar' tab")
        
        if rows:
            print(f"\n  Header row: {rows[0]}")
            if len(rows) > 1:
                print(f"  First data row: {rows[1]}")
    else:
        print(f"\n✗ 'calendar' tab NOT found!")
        print(f"  Please rename one of your tabs to 'calendar' or update SHEET_NAME in upload_videos.py")
        
except Exception as e:
    print(f"✗ Sheets API error: {e}")
    if "404" in str(e):
        print("\n  Possible causes:")
        print("  - Sheet ID is incorrect")
        print("  - Service account doesn't have access to the sheet")
        print(f"\n  Make sure you shared the sheet with: {service_email}")
    exit(1)

# Test Drive API
print("\n5. Testing Google Drive API...")
try:
    drive_service = build('drive', 'v3', credentials=creds)
    
    # Get folder info
    folder = drive_service.files().get(fileId=DRIVE_FOLDER_ID, fields='name,id').execute()
    print(f"✓ Connected to folder: {folder.get('name')}")
    
    # List files in folder
    query = f"'{DRIVE_FOLDER_ID}' in parents and trashed=false"
    results = drive_service.files().list(
        q=query,
        fields="files(id, name, mimeType)",
        pageSize=10
    ).execute()
    files = results.get('files', [])
    
    print(f"✓ Found {len(files)} files in folder")
    if files:
        print(f"\n  First few files:")
        for f in files[:5]:
            print(f"    - {f.get('name')} ({f.get('mimeType')})")
    else:
        print("  ⚠️  Folder is empty")
        
except Exception as e:
    print(f"✗ Drive API error: {e}")
    if "404" in str(e):
        print("\n  Possible causes:")
        print("  - Folder ID is incorrect")
        print("  - Service account doesn't have access to the folder")
        print(f"\n  Make sure you shared the folder with: {service_email}")
    exit(1)

print("\n" + "="*50)
print("✓ All tests passed! Your setup looks good.")
print("="*50)
