# Security Setup Guide

## Environment Variables Setup

This application uses environment variables to store sensitive information like passwords and API keys. **Never commit sensitive data to version control.**

### 1. Create your local .env file

```bash
# Copy the example file
cp .env.example .env
```

### 2. Set your environment variables

**Option A: Using .env file (for development)**
Edit the `.env` file and add your actual values:
```bash
SMTP_PASSWORD=your_actual_gmail_app_password
```

**Option B: Using system environment variables**

**Windows (PowerShell):**
```powershell
$env:SMTP_PASSWORD="your_actual_gmail_app_password"
```

**Windows (Command Prompt):**
```cmd
set SMTP_PASSWORD=your_actual_gmail_app_password
```

**Linux/Mac:**
```bash
export SMTP_PASSWORD="your_actual_gmail_app_password"
```

### 3. For Production Deployment

**Streamlit Cloud (Community Cloud):**
1. Deploy your app from GitHub to Streamlit Cloud
2. Go to your app's dashboard on [share.streamlit.io](https://share.streamlit.io)
3. Click the "⚙️ Settings" button (or three dots menu → "Settings")
4. Navigate to the "Secrets" tab
5. Add your environment variables in TOML format:
```toml
SMTP_PASSWORD = "your_actual_gmail_app_password"
```
6. Click "Save"
7. Your app will automatically restart with the new secrets

**Docker:**
```dockerfile
ENV SMTP_PASSWORD=your_password
```

**Kubernetes:**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: app-secrets
type: Opaque
stringData:
  smtp-password: your_password
```

**Other Cloud Platforms:**
- **AWS**: Use AWS Secrets Manager or Parameter Store
- **Azure**: Use Azure Key Vault
- **GCP**: Use Google Secret Manager
- **Heroku**: Use Config Vars in dashboard

### 4. Getting Gmail App Password

1. Enable 2-Factor Authentication on your Gmail account
2. Go to Google Account settings
3. Navigate to Security → 2-Step Verification → App passwords
4. Generate an app password for your application
5. Use this 16-character password (not your regular Gmail password)

### 5. Security Best Practices

✅ **DO:**
- Use environment variables for all secrets
- Use app passwords instead of regular passwords
- Keep `.env` files in `.gitignore`
- Use dedicated service accounts for production
- Rotate passwords regularly
- Use cloud secret management services in production

❌ **DON'T:**
- Commit passwords to version control
- Share passwords in plain text
- Use personal accounts for production services
- Hard-code secrets in source code
- Use the same password across environments
