@echo off
REM setup.bat - Quick setup script for Windows

echo Setting up Nokia Hackathon Software Release Chatbot...

REM Install dependencies
echo Installing Python dependencies...
pip install -r requirements.txt

REM Create .env file if it doesn't exist
if not exist .env (
    echo Creating .env file from template...
    copy .env.example .env
    echo WARNING: Please edit .env file and add your actual SMTP password!
    echo You can get a Gmail app password from: https://support.google.com/accounts/answer/185833
) else (
    echo .env file already exists
)

echo Setup complete!
echo.
echo Next steps:
echo 1. Edit .env file and set your SMTP_PASSWORD
echo 2. Run the application with: streamlit run software_release_chatbot/code.py

pause
