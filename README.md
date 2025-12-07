# Video Uploader - Automated with GitHub Actions

Automatically uploads videos from Google Drive to Erome using GitHub Actions scheduling.

## Features

- ✅ Reads pending videos from Google Sheets
- ✅ Downloads videos from Google Drive
- ✅ Uploads to Erome with title and tags
- ✅ Handles login with 2Captcha
- ✅ Runs automatically every 6 hours
- ✅ Completely free (GitHub Actions)

## Setup

### 1. Fork/Clone this repository

### 2. Add GitHub Secrets

Go to your repository → Settings → Secrets and variables → Actions → New repository secret

Add these secrets:

- `GOOGLE_SERVICE_ACCOUNT_JSON` - Your Google service account JSON (entire JSON object)
- `GOOGLE_SHEET_ID` - Your Google Sheet ID
- `GOOGLE_DRIVE_FOLDER_ID` - Your Google Drive folder ID
- `WEBSITE_USERNAME` - Erome username
- `WEBSITE_PASSWORD` - Erome password
- `TWO_CAPTCHA_API_KEY` - Your 2Captcha API key

### 3. Enable GitHub Actions

1. Go to the **Actions** tab in your repository
2. Click "I understand my workflows, go ahead and enable them"
3. The workflow will run automatically every 6 hours

### 4. Manual Trigger (Optional)

You can manually trigger the workflow:
1. Go to **Actions** tab
2. Click "Video Uploader" workflow
3. Click "Run workflow"

## Schedule

Default schedule: Every 6 hours (`0 */6 * * *`)

To change the schedule, edit `.github/workflows/uploader.yml`:

```yaml
schedule:
  - cron: '0 */8 * * *'  # Every 8 hours
  - cron: '0 9,15,21 * * *'  # 9am, 3pm, 9pm daily
```

## Google Sheets Format

Your sheet should have these columns:

| title | videos | tags | status | timestamp |
|-------|--------|------|--------|-----------|
| Video Title | video1,video2 | tag1,tag2,tag3 | | |

- **title**: Album title
- **videos**: Comma-separated video filenames (without .mp4)
- **tags**: Comma-separated tags
- **status**: Leave empty (script fills "posted" or "error")
- **timestamp**: Leave empty (script fills with date/time)

## How It Works

1. GitHub Actions runs the script on schedule
2. Script checks Google Sheets for first empty row
3. Downloads videos from Google Drive
4. Logs into Erome (handles captcha with 2Captcha)
5. Creates album with title and tags
6. Uploads videos
7. Updates sheet with "posted" status
8. Cleans up downloaded files

## Monitoring

Check workflow runs:
1. Go to **Actions** tab
2. Click on a workflow run to see logs
3. Look for "✓ Upload completed successfully"

## Troubleshooting

### Workflow not running
- Check if Actions are enabled in repository settings
- Verify schedule syntax in workflow file
- GitHub Actions may have delays (up to 15 minutes)

### Upload fails
- Check workflow logs for error messages
- Verify all secrets are set correctly
- Test GOOGLE_SERVICE_ACCOUNT_JSON is valid JSON
- Check 2Captcha balance

### Login fails
- Verify WEBSITE_USERNAME and WEBSITE_PASSWORD
- Check if 2Captcha is working (check balance)
- Look for "Login failed" in logs

## Local Testing

To test locally:

```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Create .env file with your credentials
cp .env.example .env
# Edit .env with your values

# Run script
python upload_videos.py
```

## Cost

**Completely FREE!**

- GitHub Actions: 2000 minutes/month free (private repos), unlimited for public
- Each run: ~5-10 minutes
- 4 runs/day × 30 days = 120 runs = ~20 hours/month
- Well within free tier

## Notes

- Script runs in headless mode on GitHub Actions
- Videos are temporarily downloaded to `/tmp` and cleaned up after upload
- If a video is missing from Drive, it's skipped (doesn't fail entire upload)
- Only processes one pending row per run

## License

MIT
