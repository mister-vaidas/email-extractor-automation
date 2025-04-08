import os
import shutil
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Paths
LOG_FILE = "/home/vaidas/myProjects/email-extractor/cron_log.txt"
LOGS_DIR = "/home/vaidas/myProjects/email-extractor/logs"

# Email settings
EMAIL_ACCOUNT = os.getenv('EMAIL_ACCOUNT')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT'))
REPORT_RECIPIENT = os.getenv('REPORT_RECIPIENT')

# Global summary to collect actions
log_summary = []

def rotate_log():
    if not os.path.exists(LOG_FILE):
        message = "No cron_log.txt file to rotate."
        print(message)
        log_summary.append(message)
        send_rotation_report()
        return

    os.makedirs(LOGS_DIR, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    archive_file = os.path.join(LOGS_DIR, f"cron_log_{timestamp}.txt")

    try:
        shutil.move(LOG_FILE, archive_file)
        message = f"✅ Log file rotated to: {archive_file}"
        print(message)
        log_summary.append(message)

        # Create new empty log file
        with open(LOG_FILE, "w") as new_log:
            new_log.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] New log file started after rotation.\n")

        message = "✅ New cron_log.txt created."
        print(message)
        log_summary.append(message)

        # Clean up old logs
        cleanup_old_logs()

    except Exception as e:
        error_message = f"Error rotating log file: {e}"
        print(error_message)
        log_summary.append(error_message)

    send_rotation_report()

def cleanup_old_logs():
    try:
        logs = [os.path.join(LOGS_DIR, f) for f in os.listdir(LOGS_DIR) if f.startswith("cron_log_")]
        logs.sort(reverse=True)

        logs_to_delete = logs[6:]

        for old_log in logs_to_delete:
            os.remove(old_log)
            message = f"🗑️ Deleted old log: {old_log}"
            print(message)
            log_summary.append(message)

        if not logs_to_delete:
            message = "No old logs to clean up."
            print(message)
            log_summary.append(message)
        else:
            message = f"✅ Cleaned up {len(logs_to_delete)} old logs."
            print(message)
            log_summary.append(message)

    except Exception as e:
        error_message = f"Error cleaning old logs: {e}"
        print(error_message)
        log_summary.append(error_message)

def send_rotation_report():
    subject = "🧹 Log Rotation Complete ✅"

    body = "\n".join(log_summary)
    body += f"\n\n🕒 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n🚀 System: Automated Email Sender Log Rotation"

    msg = MIMEMultipart()
    msg['From'] = EMAIL_ACCOUNT
    msg['To'] = REPORT_RECIPIENT
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
            server.send_message(msg)

        print("📩 Log rotation summary email sent successfully!")

    except Exception as e:
        print(f"Failed to send rotation summary email: {e}")

if __name__ == "__main__":
    rotate_log()
