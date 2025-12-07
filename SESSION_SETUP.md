# Session Setup Guide

This guide explains how to bypass the IP restrictions by using a stored browser session instead of logging in from GitHub Actions.

## Why This Works

The website blocks datacenter IPs (like GitHub Actions) on the **login page** to prevent brute force attacks. However, once you have a valid session cookie, the upload functionality works fine even from GitHub's servers.

## Setup Steps

### 1. Run the Session Saver Script Locally

On your local machine (with a residential IP), run:

```bash
python save_session.py
```

This will:
- Open a browser
- Log you in to the website
- Save your session to `storage_state.json`

### 2. Copy the Session Data

After the script completes, copy the entire content of `storage_state.json`.

### 3. Add to GitHub Secrets

1. Go to your GitHub repository
2. Navigate to: **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `BROWSER_STATE`
5. Value: Paste the entire JSON content from `storage_state.json`
6. Click **Add secret**

### 4. Done!

Your GitHub Actions workflow will now:
- Skip the login process entirely
- Use your stored session cookies
- Upload videos without needing a proxy
- Work reliably from GitHub's datacenter IPs

## Session Maintenance

Sessions typically last for weeks or months, but they will eventually expire. When that happens:

1. You'll see an error: `Stored session is invalid`
2. Simply run `python save_session.py` again locally
3. Update the `BROWSER_STATE` secret with the new session data

## Local Development

When running locally, the script will automatically use `storage_state.json` if it exists. You don't need to set the `BROWSER_STATE` environment variable.

## Troubleshooting

**"Session expired" error:**
- Run `save_session.py` again to get a fresh session
- Update the GitHub secret

**"No browser state found" warning:**
- Make sure you've added the `BROWSER_STATE` secret to GitHub
- Check that the JSON is valid (no extra quotes or formatting issues)

**Login fails in save_session.py:**
- Check your credentials in `.env`
- Verify your 2Captcha API key is valid
- Make sure you're running from a residential IP (not VPN/proxy)
