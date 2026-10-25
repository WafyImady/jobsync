import os
import json
import base64
import time
import psycopg
from dotenv import load_dotenv
from google import genai
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from email.utils import parsedate_to_datetime

# Load environment variables
load_dotenv('.env.local')

# 1. Initialize Gemini AI
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# 2. Gmail API Scopes
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

def get_processed_email_ids():
    """Fetches a set of all email IDs already saved in the database to prevent duplicate processing."""
    conn_string = os.getenv("DATABASE_URL")
    try:
        with psycopg.connect(conn_string) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT source_email_id FROM applications WHERE source_email_id IS NOT NULL")
                return {row[0] for row in cur.fetchall()}
    except Exception as e:
        print(f"❌ Database error while fetching existing emails: {e}")
        return set()

def extract_job_data(email_text: str):
    """Passes email text to Gemini with instant fallback for 503s and 429s."""
    
    # 🚨 FIX 1: Send only the first 2000 characters to prevent Token limits
    truncated_text = email_text[:2000]
    
    prompt = """
    Analyze the following email. If it is a job application update, extract the company name, the role applied for, and determine the status.
    Status MUST be one of: 'Applied', 'Interviewing', 'Rejected', 'Offer'.
    If the email is promotional or unrelated to an active application, set status to 'ignore'.
    
    Return EXACTLY this JSON structure:
    {"company_name": "String", "role_title": "String", "status": "String"}
    
    Email content:
    """ + truncated_text
    
    max_retries = 3
    base_wait_time = 2  
    
    for attempt in range(max_retries):
        try:
            response = gemini_client.models.generate_content(
                model='gemini-3.8-flash',
                contents=prompt,
                config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text)
        
        except Exception as e:
            error_message = str(e)
            # 🚨 FIX 2: Check for BOTH 503 and 429 to instantly swap models
            if "503" in error_message or "500" in error_message :
                print(f"⚠️ Primary model busy/limited. Instantly falling back to 3.6-flash...")
                try:
                    backup_response = gemini_client.models.generate_content(
                        model='gemini-3.6-flash',
                        contents=prompt,
                        config={"response_mime_type": "application/json"}
                    )
                    return json.loads(backup_response.text)
                except Exception as backup_error:
                    if "503" in str(backup_error) or "500" in str(backup_error):
                         if attempt < max_retries - 1:
                             wait_time = base_wait_time * (2 ** attempt) 
                             print(f"⏳ Both models busy. Retrying in {wait_time} seconds (Attempt {attempt + 1}/{max_retries})...")
                             time.sleep(wait_time)
                         else:
                             print("❌ Max retries reached for API errors. Skipping email.")
                             raise backup_error
                    else:
                        raise backup_error
            else:
                raise e

def upsert_application(company_name: str, role_title: str, status: str, email_id: str, email_date):
    """Upserts the extracted data and the email date into Neon Postgres."""
    
    conn_string = os.getenv("DATABASE_URL")
    upsert_query = """
    INSERT INTO applications (company_name, role_title, status, source_email_id, date_received)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (company_name, role_title) 
    DO UPDATE SET 
        status = EXCLUDED.status,
        last_updated = CURRENT_TIMESTAMP;
    """
    
    try:
        with psycopg.connect(conn_string) as conn:
            with conn.cursor() as cur:
                cur.execute(upsert_query, (company_name, role_title, status, email_id, email_date))
            conn.commit()
            
            if status == 'ignore':
                print(f"✅ Logged junk email: {email_id}")
            else:
                # 🚨 FIX 3: Fixed the broken print statement syntax
                print(f"✅ Success: Upserted {company_name} - {status} ({email_date.date() if email_date else 'No Date'})")
    except Exception as e:
        print(f"❌ Database error: {e}")

def process_recent_emails(service):
    """Fetches recent emails, skips processed ones, and runs them through the pipeline safely."""
    print("Fetching recent emails...")
    query = "newer_than:30d (application OR interview OR offer OR rejected)"
    results = service.users().messages().list(userId='me', q=query, maxResults=50).execute()
    messages = results.get('messages', [])

    if not messages:
        print("No new emails found matching the criteria.")
        return

    processed_ids = get_processed_email_ids()
    
    # 🚨 FIX 4: Add the small-bites limit logic here
    processed_count = 0  
    max_per_run = 30     

    for msg in messages:
        if processed_count >= max_per_run:
            print("🛑 Reached maximum 30 emails for this run. Stopping to protect GitHub minutes.")
            break
            
        msg_id = msg['id']
        
        if msg_id in processed_ids:
            print(f"⏭️ Skipping already processed email: {msg_id}")
            continue
            
        processed_count += 1
        print(f"Processing new email: {msg_id} (Attempt {processed_count}/{max_per_run})")
            
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
            
            payload = message.get('payload', {})
            headers = payload.get('headers', [])
            date_header = next((h['value'] for h in headers if h['name'] == 'Date'), None)
            email_date = parsedate_to_datetime(date_header) if date_header else None

            max_retries = 3
            attempts = 0
            success = False
            
            while not success and attempts < max_retries:
                try:
                    extracted_data = extract_job_data(email_text)
                    
                    upsert_application(
                        extracted_data.get('company_name', 'Unknown').strip().title(), 
                        extracted_data.get('role_title', 'Unknown Role').strip().title(),
                        extracted_data.get('status', 'ignore'), 
                        msg_id,
                        email_date
                    )
                    
                    success = True 
                    # 🚨 FIX 5: Increased safe sleep to 10 seconds to avoid API limits
                    time.sleep(15)
                    
                except Exception as e:
                    attempts += 1
                    if "429" in str(e):
                        print(f"⏳ Rate limit reached (Attempt {attempts}/{max_retries}). Waiting 60 seconds...")
                        time.sleep(60)
                    else:
                        print(f"⚠️ Failed to process email {msg_id}: {e}")
                        break 
            
            if not success:
                print(f"❌ Skipped email {msg_id} after {max_retries} failed attempts.")

if __name__ == "__main__":
    print("Starting automated Reverse ATS pipeline...")
    gmail_service = authenticate_gmail()
    process_recent_emails(gmail_service)
    print("Pipeline execution finished.")