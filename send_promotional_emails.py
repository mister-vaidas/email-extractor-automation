import psycopg2
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
import os
from datetime import datetime

smtplib.SMTP.debuglevel = 1

# Load environment variables
load_dotenv()

# PostgreSQL credentials
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

# Email SMTP settings
EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT"))
REPORT_RECIPIENT = os.getenv("REPORT_RECIPIENT")

# Test mode settings
TEST_MODE = os.getenv("TEST_MODE", "FALSE").upper() == "TRUE"
TEST_EMAILS = os.getenv("TEST_EMAIL", "").split(",")

# Offer link (customize per campaign)
OFFER_LINK = "https://yourwebsite.com/special-offer"

# Load email template
with open("email_template.html", "r") as file:
    EMAIL_TEMPLATE = file.read()

# Rate limit in seconds between emails
RATE_LIMIT_SECONDS = 30  # => 2 emails/minute


def fetch_recipient_emails():
    if TEST_MODE:
        print("🚧 TEST MODE: Only sending to test email addresses.")
        return TEST_EMAILS

    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS
        )
        cursor = conn.cursor()

        query = """
        SELECT email FROM (
            SELECT email FROM personal_emails
            UNION
            SELECT email FROM business_emails
        ) AS all_emails
        WHERE email NOT IN (
            SELECT email FROM unsubscribe_emails
            UNION
            SELECT email FROM sent_emails
        );
        """
        cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()
        conn.close()

        return [row[0] for row in results]

    except Exception as e:
        print(f"Database error: {e}")
        return []


def record_sent_email(email):
    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS
        )
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sent_emails (email) VALUES (%s) ON CONFLICT DO NOTHING",
            (email,),
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error logging sent email {email}: {e}")


def send_email(recipient, smtp_server):
    try:
        unsubscribe_link = f"http://35.176.53.188:5000/unsubscribe?email={recipient}"
        html_content = EMAIL_TEMPLATE.replace(
            "{{ unsubscribe_link }}", unsubscribe_link
        ).replace("{{ offer_link }}", OFFER_LINK)

        msg = MIMEMultipart("alternative")
        msg["From"] = EMAIL_ACCOUNT
        msg["To"] = recipient
        msg["Subject"] = "🎉 Special Offer Just for You!"
        msg.attach(MIMEText(html_content, "html"))

        smtp_server.send_message(msg)
        print(f"✅ Email sent to: {recipient}")
        record_sent_email(recipient)

    except Exception as e:
        raise Exception(f"Failed to send email to {recipient}: {e}")


def send_summary_email(total, success, failure, aborted=False, failed_recipients=None):
    subject = "📊 Campaign Summary Report"
    mode = "TEST MODE" if TEST_MODE else "PRODUCTION MODE"
    status = "🚫 Campaign aborted by user." if aborted else "✅ Campaign completed."
    failed_list = "\n❌ Failed recipients:\n" + "\n".join(
        f"- {email}" for email in (failed_recipients or [])
    )

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

    msg = MIMEMultipart()
    msg["From"] = EMAIL_ACCOUNT
    msg["To"] = REPORT_RECIPIENT
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
            server.send_message(msg)
        print("📩 Summary email sent to you successfully!")
    except Exception as e:
        print(f"Failed to send summary email: {e}")

    try:
        with open("cron_log.txt", "a") as log_file:
            log_file.write(body)
            log_file.write("\n" + "=" * 50 + "\n")
        print("📝 Summary logged to cron_log.txt successfully!")
    except Exception as e:
        print(f"Failed to write summary to log file: {e}")


def main():
    recipients = fetch_recipient_emails()
    total_recipients = len(recipients)
    success_count, failure_count = 0, 0
    failed_recipients = []

    print(f"Total recipients: {total_recipients}")
    if not recipients:
        print("No recipients found.")
        send_summary_email(
            total_recipients,
            success_count,
            failure_count,
            failed_recipients=failed_recipients,
        )
        return

    if TEST_MODE:
        print("🚧 TEST MODE: These recipients would receive the email:")
        for recipient in recipients:
            print(f"- {recipient}")
        print(f"Total: {total_recipients} emails would be sent.")
        send_summary_email(
            total_recipients,
            success_count,
            failure_count,
            failed_recipients=failed_recipients,
        )
        return

    confirmation = (
        input(
            f"⚠️ You are about to send emails to {total_recipients} real recipients. Confirm (yes/no): "
        )
        .strip()
        .lower()
    )
    if confirmation != "yes":
        print("🚫 Sending aborted by user.")
        send_summary_email(
            total_recipients,
            success_count,
            failure_count,
            aborted=True,
            failed_recipients=failed_recipients,
        )
        return

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)

            for i, recipient in enumerate(recipients):
                try:
                    print(f"📩 Sending promotional email to: {recipient}")
                    send_email(recipient, server)
                    success_count += 1
                except Exception as e:
                    print(e)
                    failure_count += 1
                    failed_recipients.append(recipient)

                if i < len(recipients) - 1:
                    print(
                        f"⏳ Waiting {RATE_LIMIT_SECONDS} seconds before next email..."
                    )
                    time.sleep(RATE_LIMIT_SECONDS)

        print(f"✅ Campaign completed: {success_count} sent, {failure_count} failed.")

    except Exception as e:
        print(f"SMTP error: {e}")
        failure_count = total_recipients
        failed_recipients = recipients

    send_summary_email(
        total_recipients,
        success_count,
        failure_count,
        failed_recipients=failed_recipients,
    )


if __name__ == "__main__":
    main()
