import imaplib
import email
import re
import psycopg2
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import csv

def log_message(message):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} {message}")

# Load environment variables from .env file
load_dotenv()

# Email account credentials
IMAP_SERVER = os.getenv('IMAP_SERVER')
EMAIL_ACCOUNT = os.getenv('EMAIL_ACCOUNT')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT'))
REPORT_RECIPIENT = os.getenv('REPORT_RECIPIENT')

# PostgreSQL credentials
DB_HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASS = os.getenv('DB_PASS')

# Define personal email domains
PERSONAL_DOMAINS = ['gmail.com', 'outlook.com', 'yahoo.com', 'live.com']

# Date filter (last 14 days)
DATE_FILTER = (datetime.now() - timedelta(days=14)).strftime('%d-%b-%Y')

# Global counters for report
report_data = {
    'inbox_emails': 0,
    'sent_emails': 0,
    'total_emails': 0,
    'personal_emails': 0,
    'business_emails': 0,
    'new_personal_emails': 0,
    'new_business_emails': 0
}

# Storage for newly processed emails (for CSV)
new_personal_emails = set()
new_business_emails = set()

def extract_email_addresses(msg):
    emails = set()
    for header in ['From', 'To', 'Cc', 'Bcc']:
        raw = msg.get(header)
        if raw:
            parts = raw.split(',')
            for part in parts:
                match = re.search(r'[\w\.-]+@[\w\.-]+\.[\w]{2,}', part)
                if match:
                    emails.add(match.group(0).strip().lower())
    return emails

def process_mailbox(mail, mailbox_name):
    log_message(f"Processing mailbox: {mailbox_name} since {DATE_FILTER}")
    mail.select(mailbox_name)

    # Search emails from the last 14 days
    typ, data = mail.search(None, f'(SINCE {DATE_FILTER})')
    email_ids = data[0].split()
    log_message(f"Found {len(email_ids)} emails in {mailbox_name} since {DATE_FILTER}")

    if mailbox_name == "INBOX":
        report_data['inbox_emails'] = len(email_ids)
    elif mailbox_name == "INBOX.Sent":
        report_data['sent_emails'] = len(email_ids)

    all_emails = set()

    for i, eid in enumerate(email_ids, 1):
        typ, msg_data = mail.fetch(eid, '(RFC822)')
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        extracted = extract_email_addresses(msg)
        all_emails.update(extracted)

        if i % 100 == 0 or i == len(email_ids):
            log_message(f"Processed {i}/{len(email_ids)} emails in {mailbox_name}...")

    return all_emails

def save_to_postgres(emails):
    log_message("Connecting to PostgreSQL...")
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )
    cursor = conn.cursor()

    personal_emails = set()
    business_emails = set()

    for email_address in emails:
        domain = email_address.split('@')[-1]
        if domain in PERSONAL_DOMAINS:
            personal_emails.add(email_address)
        else:
            business_emails.add(email_address)

    report_data['personal_emails'] = len(personal_emails)
    report_data['business_emails'] = len(business_emails)
    report_data['total_emails'] = len(emails)

    # Insert personal emails
    for email_address in personal_emails:
        try:
            cursor.execute(
                "INSERT INTO personal_emails (email) VALUES (%s) ON CONFLICT (email) DO NOTHING RETURNING email;",
                (email_address,)
            )
            result = cursor.fetchone()
            if result:
                new_personal_emails.add(email_address)
        except Exception as e:
            log_message(f"Error inserting personal email {email_address}: {e}")

    # Insert business emails
    for email_address in business_emails:
        try:
            cursor.execute(
                "INSERT INTO business_emails (email) VALUES (%s) ON CONFLICT (email) DO NOTHING RETURNING email;",
                (email_address,)
            )
            result = cursor.fetchone()
            if result:
                new_business_emails.add(email_address)
        except Exception as e:
            log_message(f"Error inserting business email {email_address}: {e}")

    conn.commit()
    cursor.close()
    conn.close()
    log_message("Emails saved to PostgreSQL successfully!")

    # Update report data with new counts
    report_data['new_personal_emails'] = len(new_personal_emails)
    report_data['new_business_emails'] = len(new_business_emails)

def generate_csv(personal_emails, business_emails):
    filename = f"email_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Category", "Email"])

        for email_address in sorted(personal_emails):
            writer.writerow(["Personal", email_address])

        for email_address in sorted(business_emails):
            writer.writerow(["Business", email_address])

    log_message(f"CSV file created: {filename}")
    return filename

def send_report(csv_attachment):
    log_message("Sending report email...")

    subject = f"Email Extraction Report - {datetime.now().strftime('%Y-%m-%d')}"

    if report_data['new_personal_emails'] == 0 and report_data['new_business_emails'] == 0:
        new_email_summary = "⚠️ No new emails were added in this cycle."
    else:
        new_email_summary = (
            f"🆕 New Emails Added This Run:\n"
            f"- Personal emails: {report_data['new_personal_emails']}\n"
            f"- Business emails: {report_data['new_business_emails']}"
        )

    body = f"""
✅ Email extraction completed!

📅 Date Filter: {DATE_FILTER} and newer

📨 Mailbox Summary:
- Inbox emails processed: {report_data['inbox_emails']}
- Sent emails processed: {report_data['sent_emails']}

📊 Extraction Summary:
- Total unique emails extracted: {report_data['total_emails']}
- Personal emails found: {report_data['personal_emails']}
- Business emails found: {report_data['business_emails']}

{new_email_summary}

🗂️ Database: {DB_NAME}

✅ Status: Completed successfully!
"""

    msg = MIMEMultipart()
    msg['From'] = EMAIL_ACCOUNT
    msg['To'] = REPORT_RECIPIENT
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    # Attach the CSV file
    with open(csv_attachment, "rb") as attachment:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= {os.path.basename(csv_attachment)}",
        )
        msg.attach(part)

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
            server.send_message(msg)
        log_message("Report email sent successfully!")
    except Exception as e:
        log_message(f"Failed to send report email: {e}")

def main():
    log_message(f"Starting email extraction ({DATE_FILTER} and newer)...")
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)

    inbox_emails = process_mailbox(mail, "INBOX")
    sent_emails = process_mailbox(mail, "INBOX.Sent")

    all_emails = inbox_emails.union(sent_emails)

    save_to_postgres(all_emails)

    mail.logout()
    log_message("Email extraction completed!")

    # Generate CSV
    csv_file = generate_csv(new_personal_emails, new_business_emails)

    # Send report with CSV attachment
    send_report(csv_file)

    # Auto-cleanup: remove CSV file after sending email
    try:
        os.remove(csv_file)
        log_message(f"Temporary CSV file '{csv_file}' deleted successfully!")
    except Exception as e:
        log_message(f"Error deleting temporary CSV file: {e}")

    log_message("Script completed successfully!")

if __name__ == "__main__":
    main()
