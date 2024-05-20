from flask import Flask, render_template, request
import imapclient
import email
from email.header import decode_header
from dotenv import load_dotenv
import os
import re
from datetime import datetime, timezone, timedelta

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

def extract_email_info(msg):
    sender = msg["From"]
    recipient = msg["To"]
    date = msg["Date"]
    subject = msg["Subject"]
    
    return {
        "sender": sender,
        "recipient": recipient,
        "date": date,
        "subject": subject
    }

def get_latest_netflix_email(recipient_email):
    username = os.getenv("IMAP_USERNAME")
    password = os.getenv("IMAP_PASSWORD")
    imap_server = os.getenv("IMAP_SERVER")

    mail = imapclient.IMAPClient(imap_server, ssl=True)
    mail.login(username, password)
    mail.select_folder("INBOX")

    messages = mail.search(['FROM', 'envaprem@gmail.com'])
    messages.sort(reverse=True)  # Sort messages by date in descending order

    email_content = None
    email_info = None

    # Define subject patterns in various languages
    subject_patterns = [
        r"Netflix\s*temporary\s*access\s*code",  # English
        r"Kode\s*akses\s*sementara\s*Netflix-mu",  # Indonesian
        # Add more patterns here if needed
    ]

    for msg_id in messages:
        data = mail.fetch([msg_id], ['RFC822'])
        msg = email.message_from_bytes(data[msg_id][b'RFC822'])
        subject, encoding = decode_header(msg["Subject"])[0]
        if isinstance(subject, bytes):
            subject = subject.decode(encoding if encoding else "utf-8")
        
        # Check if the subject matches any of the defined patterns
        if any(re.search(pattern, subject, re.IGNORECASE) for pattern in subject_patterns) and recipient_email in msg["To"]:
            # Check if the email is within the last 5 minutes
            email_date = email.utils.parsedate_to_datetime(msg["Date"])
            now = datetime.now(timezone.utc)
            if now - email_date > timedelta(minutes=10):
                continue  # Skip this email if it's older than 5 minutes

            payload = msg.get_payload()
            if payload:
                if isinstance(payload, list):
                    payload = payload[0]
                if payload.get_content_type() == 'text/plain':
                    email_content = payload.get_payload(decode=True).decode()
                    email_info = extract_email_info(msg)
            break  # Stop after finding the latest matching email within the time frame

    mail.logout()

    return email_content, email_info

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        recipient_email = request.form['email']
        email_content, email_info = get_latest_netflix_email(recipient_email)
        if email_content and email_info:
            return render_template('result.html', email_content=email_content, email_info=email_info)
        else:
            error_message = "No matching email found or email is older than 10 minutes. please send again"
            return render_template('index.html', error=error_message)
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
