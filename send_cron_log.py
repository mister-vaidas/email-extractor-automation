from dotenv import load_dotenv
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.mime.text import MIMEText
import os
from datetime import datetime

# Load environment variables
load_dotenv()

# Email credentials from .env
EMAIL_ACCOUNT = os.getenv('EMAIL_ACCOUNT')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT'))
REPORT_RECIPIENT = os.getenv('REPORT_RECIPIENT')

# Log file path
LOG_FILE_PATH = '/home/vaidas/myProjects/email-extractor/cron_log.txt'
LOGS_DIR = '/home/vaidas/myProjects/email-extractor/logs'

def send_cron_log():
    if not os.path.exists(LOG_FILE_PATH):
        print("Log file does not exist. Nothing to send.")
        return

    subject = f"Cron Log Report - {datetime.now().strftime('%Y-%m-%d')}"
    body = "Attached is the monthly cron log report for your email extraction automation."

    msg = MIMEMultipart()
    msg['From'] = EMAIL_ACCOUNT
    msg['To'] = REPORT_RECIPIENT
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    with open(LOG_FILE_PATH, "rb") as attachment:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= {os.path.basename(LOG_FILE_PATH)}",
        )
        msg.attach(part)

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
            server.send_message(msg)
        print("Cron log email sent successfully!")

        # After successful email, rotate the log
        rotate_log()

    except Exception as e:
        print(f"Failed to send cron log email: {e}")

def rotate_log():
    try:
        # Ensure logs directory exists
        os.makedirs(LOGS_DIR, exist_ok=True)

        # Create archive filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        archive_file = os.path.join(LOGS_DIR, f"cron_log_{timestamp}.txt")

        # Move log file to archive
        os.rename(LOG_FILE_PATH, archive_file)
        print(f"Log file archived to: {archive_file}")

        # Create new empty log file
        with open(LOG_FILE_PATH, 'w') as new_log:
            new_log.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] New log file started after rotation.\n")

        print("New cron log file created successfully!")

        # Clean up old logs
        cleanup_old_logs()

    except Exception as e:
        print(f"Error rotating log file: {e}")

def cleanup_old_logs():
    try:
        logs = [os.path.join(LOGS_DIR, f) for f in os.listdir(LOGS_DIR) if f.startswith("cron_log_")]
        logs.sort(reverse=True)  # Most recent first

        # Keep only the latest 6 logs
        logs_to_delete = logs[6:]

        for old_log in logs_to_delete:
            os.remove(old_log)
            print(f"Old log deleted: {old_log}")

        if not logs_to_delete:
            print("No old logs to clean up.")
        else:
            print(f"Cleaned up {len(logs_to_delete)} old logs.")

    except Exception as e:
        print(f"Error cleaning up old logs: {e}")

if __name__ == "__main__":
    send_cron_log()
