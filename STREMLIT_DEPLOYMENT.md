# Streamlit Cloud Deployment Guide

## 🚀 Deploying to Streamlit Community Cloud

### Prerequisites
1. GitHub repository with your code (already done!)
2. Gmail App Password (see SECURITY.md for setup instructions)
3. Streamlit Community Cloud account (free at [share.streamlit.io](https://share.streamlit.io))

### Step-by-Step Deployment

#### 1. **Connect to Streamlit Cloud**
- Go to [share.streamlit.io](https://share.streamlit.io)
- Sign in with your GitHub account
- Click "New app"

#### 2. **Configure Your App**
- **Repository**: Select your GitHub repo (nokia_hackathon-main)
- **Branch**: main (or your default branch)
- **Main file path**: `software_release_chatbot/code.py`
- **App URL**: Choose a custom URL (optional)

#### 3. **Set Environment Variables (CRITICAL)**
⚠️ **This step is essential for email functionality to work!**

1. After creating the app, click the "⚙️ Settings" button in your app dashboard
2. Navigate to the "**Secrets**" tab
3. Add your secrets in TOML format:

```toml
# Secrets for Nokia Hackathon Release Chatbot
SMTP_PASSWORD = "your_16_character_gmail_app_password"

# Add other secrets as needed
# API_KEY = "your_api_key_here"
```

4. Click "**Save**"
5. Your app will automatically restart with the new secrets

#### 4. **Deploy**
- Click "Deploy!" 
- Wait for the deployment to complete (usually 2-3 minutes)
- Your app will be live at `https://your-app-name.streamlit.app`

### 🔐 Security Notes for Streamlit Cloud

✅ **What Streamlit Cloud Does Right:**
- Secrets are encrypted and never exposed in logs
- Environment variables are isolated per app
- Secrets are not visible in the public repository
- Automatic HTTPS encryption

✅ **Best Practices:**
- Use dedicated Gmail account for the chatbot
- Use Gmail App Passwords (not your regular password)
- Regularly rotate your app passwords
- Monitor your app's email usage

### 🛠 Troubleshooting

**App won't start?**
- Check that `software_release_chatbot/code.py` path is correct
- Verify all dependencies are in `requirements.txt`
- Check the logs in Streamlit Cloud dashboard

**Email not working?**
- Verify `SMTP_PASSWORD` is set in Secrets tab
- Ensure you're using a Gmail App Password (not regular password)
- Check that 2FA is enabled on your Gmail account

**App updates not deploying?**
- Push changes to your GitHub repository
- Streamlit Cloud auto-deploys on git push
- Check the "Deployments" tab for build logs

### 📝 Managing Your Deployed App

**View Logs:**
- Go to your app dashboard
- Click "Manage app" → "Logs"

**Update Secrets:**
- Settings → Secrets tab → Edit → Save
- App automatically restarts

**Restart App:**
- Three dots menu → "Reboot app"

**Delete App:**
- Settings → "Delete app" (be careful!)

### 🔄 Automatic Updates

Your Streamlit Cloud app automatically redeploys when you:
- Push code changes to your GitHub repository
- Update secrets in the Streamlit dashboard

No manual redeployment needed! 🎉

### 📊 Usage Limits (Free Tier)

Streamlit Community Cloud free tier includes:
- ✅ Unlimited public apps
- ✅ 1GB RAM per app
- ✅ 1 CPU core per app
- ✅ Community support
- ⚠️ Apps sleep after inactivity (wake up automatically when accessed)

Perfect for hackathons and demos!
