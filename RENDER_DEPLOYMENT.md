# Render.com Deployment Guide

## Why Render?
- ✅ **Free tier is permanent** (not a trial)
- ✅ 750 hours/month free compute
- ✅ Built-in cron job support
- ✅ Supports Docker + Playwright
- ✅ Easy setup from GitHub

## Step 1: Sign Up

1. Go to https://render.com
2. Sign up with GitHub (easiest)
3. Authorize Render to access your repos

## Step 2: Create Cron Job

1. Click **"New +"** → **"Cron Job"**
2. Connect your repository: `denis-kolbas/erome-uploader`
3. Configure:
   - **Name:** video-uploader
   - **Region:** Choose closest to you
   - **Branch:** main
   - **Runtime:** Docker
   - **Dockerfile Path:** ./Dockerfile
   - **Schedule:** `0 */6 * * *` (every 6 hours)
   - **Plan:** Free

## Step 3: Add Environment Variables

In the "Environment" section, add these variables:

```
GOOGLE_SERVICE_ACCOUNT_JSON
GOOGLE_SHEET_ID
GOOGLE_DRIVE_FOLDER_ID
WEBSITE_USERNAME
WEBSITE_PASSWORD
TWO_CAPTCHA_API_KEY
RENDER_ENVIRONMENT=production
```

**Important:** 
- Click "Add Environment Variable" for each one
- Paste the full JSON for GOOGLE_SERVICE_ACCOUNT_JSON (no quotes needed)
- Don't wrap values in quotes

## Step 4: Deploy

1. Click **"Create Cron Job"**
2. Render will build your Docker image
3. First build takes ~5-10 minutes
4. Check logs to verify it works

## Cron Schedule Options

Change the schedule in render.yaml or in the dashboard:

- `0 */6 * * *` - Every 6 hours (4 times/day)
- `0 */8 * * *` - Every 8 hours (3 times/day)
- `0 9,15,21 * * *` - At 9am, 3pm, 9pm
- `0 0,12 * * *` - Twice daily (midnight and noon)

## Monitoring

1. Go to your cron job in Render dashboard
2. Click **"Logs"** to see execution history
3. Each run will show:
   - ✓ Upload completed successfully
   - Or error messages if something fails

## Troubleshooting

### Build Fails
- Check Dockerfile syntax
- Verify all files are pushed to GitHub
- Check build logs in Render dashboard

### Runtime Errors
- Verify all environment variables are set correctly
- Check if GOOGLE_SERVICE_ACCOUNT_JSON is valid JSON
- Look at runtime logs for specific errors

### Cron Not Running
- Verify schedule syntax is correct
- Check if service is suspended (free tier suspends after inactivity)
- Render free tier cron jobs run reliably

### Browser Issues
- Script automatically runs headless on Render
- If captcha fails, check TWO_CAPTCHA_API_KEY
- Chromium is included in Docker image

## Testing Before Deploy

Test locally with Docker:

```bash
# Build
docker build -t video-uploader .

# Run with env file
docker run --env-file .env video-uploader
```

## Cost

Render Free Tier:
- 750 hours/month free
- Cron jobs count only when running
- Each run ~5-10 minutes
- 4 runs/day × 30 days = 120 runs/month
- ~10 hours/month total usage
- **Completely free!**

## Updating

To update your script:

```bash
git add .
git commit -m "Update script"
git push
```

Render will automatically rebuild and deploy.

## Alternative: Manual Trigger

If you want to trigger manually instead of cron:

1. Create as "Background Worker" instead of "Cron Job"
2. Use Render API to trigger runs
3. Or use external service like cron-job.org

## Advantages Over Railway

- ✅ Truly free (not trial)
- ✅ Built-in cron support
- ✅ 750 hours/month (vs Railway's $5 credit)
- ✅ Same Docker support
- ✅ Better for scheduled tasks

## Next Steps

1. Push updated code to GitHub
2. Create Render account
3. Set up cron job
4. Add environment variables
5. Deploy and monitor logs

Good luck! 🚀
