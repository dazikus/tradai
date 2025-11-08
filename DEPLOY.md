# 🚀 Deploy to Render.com

## Step 1: Push to GitHub

```bash
git add .
git commit -m "Prepare for Render deployment"
git push
```

## Step 2: Deploy on Render

1. Go to **[render.com](https://render.com)** and sign up (use GitHub)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository
4. Render will auto-detect the `render.yaml` config!
5. Click **"Create Web Service"**

That's it! Render will:
- Install dependencies from `requirements.txt`
- Start the app with gunicorn
- Give you a URL like: `https://tradai-xxxx.onrender.com`

## Auto-Deploy

Every time you push to GitHub, Render automatically deploys the new version! 🎉

## Keep It Awake (Optional)

Free tier sleeps after 15 min inactivity. To prevent this:

1. Go to **[uptimerobot.com](https://uptimerobot.com)** (free)
2. Add a monitor for your Render URL
3. Set it to ping every 5 minutes

Done! Your app stays awake 24/7.

## Access Your App

- **Web Interface**: `https://your-app.onrender.com`
- **API Endpoint**: `https://your-app.onrender.com/api/live-games`
- **Health Check**: `https://your-app.onrender.com/api/health`

## Troubleshooting

If deployment fails, check Render logs:
- Click on your service
- Go to "Logs" tab
- Look for errors

Common issues:
- Missing dependencies → check `requirements.txt`
- Port issues → already handled with `PORT` env var

