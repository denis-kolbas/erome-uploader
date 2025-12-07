# Railway Deployment Guide

## Prerequisites
- Railway account (sign up at https://railway.app)
- GitHub repository with your code
- All environment variables ready

## Step 1: Push to GitHub

Make sure all files are committed:
```bash
git add .
git commit -m "Add Railway deployment config"
git push
```

## Step 2: Create Railway Project

1. Go to https://railway.app
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose your repository
5. Railway will auto-detect the Dockerfile

## Step 3: Add Environment Variables

In Railway dashboard, go to your service → Variables tab and add:

```
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}
GOOGLE_SHEET_ID=your_sheet_id
GOOGLE_DRIVE_FOLDER_ID=your_folder_id
WEBSITE_USERNAME=your_username
WEBSITE_PASSWORD=your_password
TWO_CAPTCHA_API_KEY=your_api_key
```

**Important:** Don't include quotes around the values in Railway!

## Step 4: Choose Deployment Mode

### Option A: One-Shot Execution (Recommended for Cron)
- Keep `CMD ["python", "upload_videos.py"]` in Dockerfile
- Use external cron service (cron-job.org) to trigger deployments
- Service runs once and exits

### Option B: Continuous Running
1. Change Dockerfile CMD to:
   ```dockerfile
   CMD ["python", "upload_videos_scheduled.py"]
   ```
2. Service stays running and checks every 6 hours
3. Costs more (always running)

## Step 5: Deploy

1. Railway will automatically deploy
2. Check logs to verify it works
3. First run should process one pending video

## Step 6: Set Up Scheduling

### Using cron-job.org (Free):

1. Go to https://cron-job.org and create account
2. Create new cron job
3. Get your Railway webhook URL:
   - In Railway: Service → Settings → Webhooks
   - Create webhook, copy URL
4. In cron-job.org:
   - URL: Your Railway webhook URL
   - Schedule: `0 */6 * * *` (every 6 hours)
   - Method: POST

### Using Railway Cron (if available):
1. In Railway dashboard, go to service settings
2. Look for "Cron" or "Scheduled Runs"
3. Set schedule: `0 */6 * * *`

## Troubleshooting

### Build fails
- Check Dockerfile syntax
- Verify requirements.txt is correct
- Check Railway build logs

### Runtime errors
- Verify all environment variables are set
- Check Railway runtime logs
- Test locally with Docker first

### Browser issues
- Railway should support Chromium
- If issues persist, try headless=True in script

## Testing Locally with Docker

Before deploying, test locally:

```bash
# Build image
docker build -t video-uploader .

# Run with env file
docker run --env-file .env video-uploader
```

## Cost Estimate

Railway pricing:
- Free tier: $5 credit/month
- One-shot runs: ~$0.01-0.05 per run
- Running 4x/day: ~$1-2/month
- Continuous running: ~$5-10/month

**Recommendation:** Use one-shot with external cron for lowest cost.

## Monitoring

Check Railway logs regularly:
- Dashboard → Your Service → Logs
- Look for "✓ Upload completed successfully"
- Check for errors

## Updating

To update the script:
```bash
git add .
git commit -m "Update script"
git push
```

Railway will automatically redeploy.
