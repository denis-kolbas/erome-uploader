# Railway Cron Setup Instructions

Since Railway doesn't have built-in cron scheduling, you have two options:

## Option 1: Use Railway Cron Trigger (Recommended)

1. Deploy your service to Railway
2. Go to your service settings
3. Add a "Cron Job" trigger
4. Set schedule (e.g., `0 */6 * * *` for every 6 hours)
5. Railway will restart your service on schedule

## Option 2: External Cron Service

Use a free service like:
- **cron-job.org** - Free, reliable
- **EasyCron** - Free tier available
- **GitHub Actions** - Can trigger Railway deployments

### Setup with cron-job.org:

1. Create account at https://cron-job.org
2. Create new cron job
3. Set URL to trigger Railway deployment webhook
4. Set schedule (e.g., every 6 hours)

## Option 3: Add Internal Scheduler

Modify the script to run continuously with sleep intervals.
See `upload_videos_scheduled.py` for example.

## Recommended Schedule

For a few times per day:
- `0 */6 * * *` - Every 6 hours (4 times/day)
- `0 */8 * * *` - Every 8 hours (3 times/day)
- `0 9,15,21 * * *` - At 9am, 3pm, 9pm (3 times/day)
