import psycopg2
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
import os
from datetime import datetime

# Load environment variables
load_dotenv()

# PostgreSQL credentials
DB_HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASS = os.getenv('DB_PASS')

# Email SMTP settings
EMAIL_ACCOUNT = os.getenv('EMAIL_ACCOUNT')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT'))
REPORT_RECIPIENT = os.getenv('REPORT_RECIPIENT')

# Test mode settings
TEST_MODE = os.getenv('TEST_MODE', 'FALSE').upper() == 'TRUE'
TEST_EMAIL = os.getenv('TEST_EMAIL')

# Offer link (customize per campaign)
OFFER_LINK = "https://yourwebsite.com/special-offer"

# Load email template
with open("email_template.html", "r") as file:
    EMAIL_TEMPLATE = file.read()

def fetch_recipient_emails():
    if TEST_MODE:
        print("🚧 TEST MODE: Only sending to test email address.")
        return [TEST_EMAIL]

    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        cursor = conn.cursor()

        # Get emails from personal and business tables, excluding unsubscribed
        query = """
        SELECT email FROM personal_emails
        WHERE email NOT IN (SELECT email FROM unsubscribe_emails)
        UNION
        SELECT email FROM business_emails
        WHERE email NOT IN (SELECT email FROM unsubscribe_emails);
        """
        cursor.execute(query)
        results = cursor.fetchall()

        cursor.close()
        conn.close()

        return [row[0] for row in results]

    except Exception as e:
        print(f"Database error: {e}")
        return []

def send_email(recipient, smtp_server):
    try:
        # Prepare unsubscribe link
        unsubscribe_link = f"http://your-server-ip:5000/unsubscribe?email={recipient}"

        # Personalize the template
        html_content = EMAIL_TEMPLATE.replace("{{ unsubscribe_link }}", unsubscribe_link).replace("{{ offer_link }}", OFFER_LINK)

        msg = MIMEMultipart('alternative')
        msg['From'] = EMAIL_ACCOUNT
        msg['To'] = recipient
        msg['Subject'] = "🎉 Monthly Special Offer Just for You!"

        msg.attach(MIMEText(html_content, 'html'))

        smtp_server.send_message(msg)
        print(f"✅ Email sent to: {recipient}")

    except Exception as e:
        raise Exception(f"Failed to send email to {recipient}: {e}")

def send_summary_email(total, success, failure, aborted=False, failed_recipients=None):
    subject = "📊 Campaign Summary Report"

    mode = "TEST MODE" if TEST_MODE else "PRODUCTION MODE"
    status = "🚫 Campaign aborted by user." if aborted else "✅ Campaign completed."

    failed_list = ""
    if failed_recipients:
        failed_list = "\n❌ Failed recipients:\n" + "\n".join(f"- {email}" for email in failed_recipients)

    body = f"""
{status}

📊 Summary:
- Mode: {mode}
- Total intended recipients: {total}
- Emails sent successfully: {success}
- Failures: {failure}
{failed_list}

🕒 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🚀 System: Automated Email Sender
"""

    # ✅ Step 1: Log to local cron_log.txt
    log_file_path = "/home/vaidas/myProjects/email-extractor/cron_log.txt"
    try:
        with open(log_file_path, "a") as log_file:
            log_file.write(body)
            log_file.write("\n" + "="*50 + "\n")
        print("📝 Summary logged to cron_log.txt successfully!")
    except Exception as e:
        print(f"Failed to write summary to log file: {e}")

    # ✅ Step 2: Send summary email
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

        print("📩 Summary email sent to you successfully!")

    except Exception as e:
        print(f"Failed to send summary email: {e}")

def main():
    recipients = fetch_recipient_emails()
    total_recipients = len(recipients)
    success_count = 0
    failure_count = 0
    failed_recipients = []

    print(f"Total recipients: {total_recipients}")

    if not recipients:
        print("No recipients found.")
        send_summary_email(total_recipients, success_count, failure_count, failed_recipients=failed_recipients)
        return

    # Dry-run: Test mode
    if TEST_MODE:
        print("🚧 TEST MODE: These recipients would receive the email:")
        for recipient in recipients:
            print(f"- {recipient}")
        print(f"Total: {total_recipients} emails would be sent.")
        send_summary_email(total_recipients, success_count, failure_count, failed_recipients=failed_recipients)
        return

    # Production mode confirmation
    confirmation = input(f"⚠️ You are about to send emails to {total_recipients} real recipients. Are you sure? (yes/no): ").strip().lower()
    if confirmation != 'yes':
        print("🚫 Sending aborted by user.")
        send_summary_email(total_recipients, success_count, failure_count, aborted=True, failed_recipients=failed_recipients)
        return

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)

            for recipient in recipients:
                try:
                    send_email(recipient, server)
                    success_count += 1
                except Exception as e:
                    print(e)
                    failure_count += 1
                    failed_recipients.append(recipient)

        print(f"✅ Campaign completed: {success_count} sent, {failure_count} failed.")

    except Exception as e:
        print(f"SMTP error: {e}")
        failure_count = total_recipients
        failed_recipients = recipients

    # Always send summary email
    send_summary_email(total_recipients, success_count, failure_count, failed_recipients=failed_recipients)

if __name__ == "__main__":
    main()
