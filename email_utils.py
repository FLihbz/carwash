import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
import os

YOUR_EMAIL = os.getenv("YOUR_EMAIL", "your_email@example.com")
YOUR_PASSWORD = os.getenv("YOUR_PASSWORD", "your_password")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.example.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))

def send_email(subject, body, to_email):
    msg = MIMEMultipart()
    msg['From'] = YOUR_EMAIL
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(YOUR_EMAIL, YOUR_PASSWORD)
            server.sendmail(YOUR_EMAIL, to_email, msg.as_string())
            logging.info(f"Email sent successfully to {to_email}")
            return True
    except Exception as e:
        logging.error(f"Failed to send email to {to_email}: {e}")
        return False
