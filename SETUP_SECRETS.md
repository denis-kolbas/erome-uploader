# GitHub Secrets Setup Guide

## Step-by-Step Instructions

### 1. Go to Repository Settings

Navigate to: https://github.com/denis-kolbas/erome-uploader/settings/secrets/actions

Or:
1. Go to your repository
2. Click **Settings** tab
3. Click **Secrets and variables** → **Actions** (left sidebar)
4. Click **New repository secret**

### 2. Add Each Secret

Click "New repository secret" and add these one by one:

---

#### Secret 1: GOOGLE_SERVICE_ACCOUNT_JSON

**Name:** `GOOGLE_SERVICE_ACCOUNT_JSON`

**Value:** Your entire service account JSON file content. It should look like:

```json
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "abc123...",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIE...\n-----END PRIVATE KEY-----\n",
  "client_email": "your-service-account@your-project.iam.gserviceaccount.com",
  "client_id": "123456789",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/..."
}
```

**Important:** 
- Copy the ENTIRE JSON (including the curly braces)
- Don't add extra quotes around it
- Keep all the newlines in the private_key field

---

#### Secret 2: GOOGLE_SHEET_ID

**Name:** `GOOGLE_SHEET_ID`

**Value:** The ID from your Google Sheet URL

Example: If your sheet URL is:
```
https://docs.google.com/spreadsheets/d/1ABC123xyz456/edit
```

The ID is: `1ABC123xyz456`

---

#### Secret 3: GOOGLE_DRIVE_FOLDER_ID

**Name:** `GOOGLE_DRIVE_FOLDER_ID`

**Value:** The ID from your Google Drive folder URL

Example: If your folder URL is:
```
https://drive.google.com/drive/folders/1XYZ789abc123
```

The ID is: `1XYZ789abc123`

---

#### Secret 4: WEBSITE_USERNAME

**Name:** `WEBSITE_USERNAME`

**Value:** Your Erome username (just the username, no quotes)

---

#### Secret 5: WEBSITE_PASSWORD

**Name:** `WEBSITE_PASSWORD`

**Value:** Your Erome password (just the password, no quotes)

---

#### Secret 6: TWO_CAPTCHA_API_KEY

**Name:** `TWO_CAPTCHA_API_KEY`

**Value:** Your 2Captcha API key

Get it from: https://2captcha.com/enterpage

---

## Verify Secrets Are Set

After adding all secrets, you should see 6 secrets listed:

- ✅ GOOGLE_SERVICE_ACCOUNT_JSON
- ✅ GOOGLE_SHEET_ID
- ✅ GOOGLE_DRIVE_FOLDER_ID
- ✅ WEBSITE_USERNAME
- ✅ WEBSITE_PASSWORD
- ✅ TWO_CAPTCHA_API_KEY

## Test the Workflow

1. Go to **Actions** tab
2. Click **Video Uploader** workflow
3. Click **Run workflow** → **Run workflow**
4. Wait for it to complete
5. Check the logs for any errors

## Common Issues

### "Expecting value: line 1 column 1"
- GOOGLE_SERVICE_ACCOUNT_JSON is empty or not valid JSON
- Make sure you copied the entire JSON file content
- Don't wrap it in extra quotes

### "Missing required environment variables"
- One or more secrets are not set
- Check spelling of secret names (must be EXACT)
- Re-add the missing secrets

### "Login failed"
- Check WEBSITE_USERNAME and WEBSITE_PASSWORD are correct
- Verify TWO_CAPTCHA_API_KEY is valid and has balance

### "File not found in Drive"
- Check GOOGLE_DRIVE_FOLDER_ID is correct
- Verify service account has access to the folder
- Make sure video files exist in the folder

## Getting Google Service Account JSON

If you don't have a service account yet:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable Google Sheets API and Google Drive API
4. Go to **IAM & Admin** → **Service Accounts**
5. Click **Create Service Account**
6. Give it a name, click **Create**
7. Skip role assignment (click **Continue**)
8. Click **Done**
9. Click on the service account email
10. Go to **Keys** tab
11. Click **Add Key** → **Create new key**
12. Choose **JSON** format
13. Download the JSON file
14. Copy the entire content and paste as secret

### Share Google Sheet and Drive Folder

After creating service account:

1. Copy the service account email (looks like: `name@project.iam.gserviceaccount.com`)
2. Share your Google Sheet with this email (Editor access)
3. Share your Google Drive folder with this email (Viewer access)

## Need Help?

Check the workflow logs for detailed error messages:
1. Go to **Actions** tab
2. Click on the failed workflow run
3. Click on the **upload** job
4. Expand the **Run uploader** step
5. Read the error message
