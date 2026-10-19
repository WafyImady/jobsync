import os
import json
import base64
import psycopg
from dotenv import load_dotenv
from google import genai
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Load environment variables
load_dotenv('.env.local')

# 1. Initialize Gemini AI with the new official package
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# 2. Gmail API Scopes (Read-only)
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def authenticate_gmail():
    """Handles OAuth 2.0 flow and generates/loads token.json."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            
    return build('gmail', 'v1', credentials=creds)

def extract_job_data(email_text: str):
    """Passes email text to Gemini to extract company and status."""
    prompt = """
    Analyze the following email. If it is a job application update, extract the company name and determine the status.
    Status MUST be one of: 'Applied', 'Interviewing', 'Rejected', 'Offer'.
    If the email is promotional or unrelated to an active application, set status to 'ignore'.
    
    Return EXACTLY this JSON structure:
    {"company_name": "String", "status": "String"}
    
    Email content:
    """ + email_text
    
    response = gemini_client.models.generate_content(
        model='gemini-3.8-flash',
        contents=prompt,
        config={"response_mime_type": "application/json"}
    )
    return json.loads(response.text)

def upsert_application(company_name: str, status: str, email_id: str):
    """Upserts the extracted data into Neon Postgres."""
    if status == 'ignore':
        print(f"Ignored unrelated email: {email_id}")
        return

    conn_string = os.getenv("DATABASE_URL")
    upsert_query = """
    INSERT INTO applications (company_name, status, source_email_id)
    VALUES (%s, %s, %s)
    ON CONFLICT (source_email_id) 
    DO UPDATE SET 
        status = EXCLUDED.status,
        last_updated = CURRENT_TIMESTAMP;
    """
    
    try:
        with psycopg.connect(conn_string) as conn:
            with conn.cursor() as cur:
                cur.execute(upsert_query, (company_name, status, email_id))
            conn.commit()
            print(f"✅ Success: Upserted {company_name} - {status}")
    except Exception as e:
        print(f"❌ Database error: {e}")

def process_recent_emails(service):
    """Fetches recent emails and runs them through the pipeline."""
    print("Fetching recent emails...")
    query = "newer_than:7d (application OR interview OR status OR update)"
    results = service.users().messages().list(userId='me', q=query, maxResults=50).execute()
    messages = results.get('messages', [])

    if not messages:
        print("No new emails found matching the criteria.")
        return

    for msg in messages:
        msg_id = msg['id']
        message = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
        
        payload = message.get('payload', {})
        body_data = ""
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    body_data = part['body'].get('data', '')
                    break
        else:
            body_data = payload.get('body', {}).get('data', '')

        if body_data:
            email_text = base64.urlsafe_b64decode(body_data).decode('utf-8')
            
            try:
                extracted_data = extract_job_data(email_text)
                upsert_application(extracted_data.get('company_name', 'Unknown'), extracted_data.get('status', 'ignore'), msg_id)
            except Exception as e:
                print(f"⚠️ Failed to process email {msg_id}: {e}")

if __name__ == "__main__":
    print("Starting automated Reverse ATS pipeline...")
    gmail_service = authenticate_gmail()
    process_recent_emails(gmail_service)
    print("Pipeline execution finished.")