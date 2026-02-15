#!/usr/bin/env python3
"""Send email with listings attachment using Gmail API."""

import os
import base64
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase

# Gmail API scope for sending email
SCOPES = ['https://www.googleapis.com/auth/gmail.send']


def get_gmail_service():
    """Authenticate and return Gmail API service."""
    creds = None
    
    # Load existing token if available
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # If no valid credentials, do OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('client_secret.json'):
                print("❌ Error: client_secret.json not found!")
                print("Please download your client_secret.json from Google Cloud Console")
                print("and place it in this directory.")
                exit(1)
            
            flow = InstalledAppFlow.from_client_secrets_file(
                'client_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save token for future runs
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    return build('gmail', 'v1', credentials=creds)


def create_message_with_attachment(sender, to, subject, body, attachment_path):
    """Create email message with attachment."""
    message = MIMEMultipart()
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject
    
    # Add body
    msg_body = MIMEText(body)
    message.attach(msg_body)
    
    # Add attachment
    with open(attachment_path, 'r', encoding='utf-8') as f:
        attachment_content = f.read()
    
    msg_attachment = MIMEText(attachment_content)
    filename = os.path.basename(attachment_path)
    msg_attachment.add_header(
        'Content-Disposition',
        f'attachment; filename="{filename}"'
    )
    message.attach(msg_attachment)
    
    # Encode to base64
    raw = base64.urlsafe_b64encode(message.as_bytes())
    return {'raw': raw.decode()}


def send_message(service, user_id, message):
    """Send email via Gmail API."""
    try:
        sent_message = service.users().messages().send(
            userId=user_id, body=message
        ).execute()
        print(f'✅ Email sent! Message Id: {sent_message["id"]}')
        return sent_message
    except Exception as e:
        print(f'❌ Error sending email: {e}')
        return None


def main():
    # Email configuration
    SENDER = 'c2501038@gmail.com'
    RECIPIENT = 'c2501038@gmail.com'  # Change if you want to send elsewhere
    SUBJECT = 'Business Listings - Filtered Results'
    BODY = '''Hi,

Attached are the filtered business listings from Seek Business.

Summary:
- Filtered from 281 total listings
- 31 listings passed the filter criteria

Excluded categories:
- Retail, Food & Drink, Hospitality, Tourism
- Driving Schools, Beauty, Gyms, Mechanics, Sports
- Cleaning, Dry Cleaning, Laundromat
- Pest Control, Automotive, Taxi
- Courier, Truck Freight, Removals
- Garden, Lawn, Mowing, Nursery
- Air Conditioning, Carpet/Flooring, Electrical
- Dog Grooming, Pet Grooming
- Refund Biz

Best regards,
Business Searcher
'''
    ATTACHMENT = 'prefilter_pass_listings.txt'
    
    print('🔐 Authenticating with Gmail API...')
    service = get_gmail_service()
    
    print('📧 Creating email with attachment...')
    message = create_message_with_attachment(
        SENDER, RECIPIENT, SUBJECT, BODY, ATTACHMENT
    )
    
    print('📤 Sending email...')
    send_message(service, 'me', message)


if __name__ == '__main__':
    main()
