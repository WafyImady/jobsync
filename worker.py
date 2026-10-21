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
    """Passes email text to Gemini with 3.6-flash fallback and exponential backoff for 503s."""
    
    truncated_text = email_text[:3000]
    
    prompt = """
    Analyze the following email. If it is a job application update, extract the company name and determine the status.
    Status MUST be one of: 'Applied', 'Interviewing', 'Rejected', 'Offer'.
    If the email is promotional or unrelated to an active application, set status to 'ignore'.
    
    Return EXACTLY this JSON structure:
    {"company_name": "String", "status": "String"}
    
    Email content:
    """ + truncated_text
    
    max_retries = 3
    base_wait_time = 2  # Start with a 2-second wait
    
    for attempt in range(max_retries):
        try:
            # Try primary model first
            response = gemini_client.models.generate_content(
                model='gemini-3.8-flash',
                contents=prompt,
                config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text)
        
        except Exception as e:
            error_message = str(e)
            if "503" in error_message or "500" in error_message:
                print(f"⚠️ Primary model 503. Falling back to 3.6-flash...")
                try:
                    # Fallback to secondary model
                    backup_response = gemini_client.models.generate_content(
                        model='gemini-3.6-flash',
                        contents=prompt,
                        config={"response_mime_type": "application/json"}
                    )
                    return json.loads(backup_response.text)
                except Exception as backup_error:
                    if "503" in str(backup_error) or "500" in str(backup_error):
                         # If BOTH fail with 503, apply backoff
                         if attempt < max_retries - 1:
                             wait_time = base_wait_time * (2 ** attempt) # Wait 2s, then 4s...
                             print(f"⏳ Both models 503. Retrying in {wait_time} seconds (Attempt {attempt + 1}/{max_retries})...")
                             time.sleep(wait_time)
                         else:
                             print("❌ Max retries reached for 503 errors. Skipping email.")
                             raise backup_error # Give up after 3 tries
                    else:
                        raise backup_error
            else:
                # If it's a 429 or other error, let the main loop handle it
                raise e

def upsert_application(company_name: str, status: str, email_id: str, email_date):
    """Upserts the extracted data and the email date into Neon Postgres."""
    
    conn_string = os.getenv("DATABASE_URL")
    upsert_query = """
    INSERT INTO applications (company_name, status, source_email_id, date_received)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (source_email_id) 
    DO UPDATE SET 
        status = EXCLUDED.status,
        last_updated = CURRENT_TIMESTAMP;
    """
    
    try:
        with psycopg.connect(conn_string) as conn:
            with conn.cursor() as cur:
                # Add email_date to the variables passed to SQL
                cur.execute(upsert_query, (company_name, status, email_id, email_date))
            conn.commit()
            
            if status == 'ignore':
                print(f"✅ Logged junk email: {email_id}")
            else:
                print(f"✅ Success: Upserted {company_name} - {status} ({email_date.date()})")
    except Exception as e:
        print(f"❌ Database error: {e}")

def process_recent_emails(service):
    """Fetches recent emails, skips processed ones, and runs them through the pipeline."""
    print("Fetching recent emails...")
    query = "newer_than:2d (application OR interview OR offer OR rejected)"
    results = service.users().messages().list(userId='me', q=query, maxResults=50).execute()
    messages = results.get('messages', [])

    if not messages:
        print("No new emails found matching the criteria.")
        return

    # 1. Get the list of emails we already processed from the database
    processed_ids = get_processed_email_ids()

    for msg in messages:
        msg_id = msg['id']
        
        # 2. Skip if the email is already in the database
        if msg_id in processed_ids:
            print(f"⏭️ Skipping already processed email: {msg_id}")
            continue
            
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
            
            # 🚨 THE NEW DATE EXTRACTION LOGIC
            payload = message.get('payload', {})
            headers = payload.get('headers', [])
            date_header = next((h['value'] for h in headers if h['name'] == 'Date'), None)
            email_date = parsedate_to_datetime(date_header) if date_header else None
            
            success = False
            while not success:
                try:
                    extracted_data = extract_job_data(email_text)
                    
                    # Pass the new email_date into the upsert function
                    upsert_application(
                        extracted_data.get('company_name', 'Unknown'), 
                        extracted_data.get('status', 'ignore'), 
                        msg_id,
                        email_date
                    )
                    
                    success = True 
                    time.sleep(5)
                    
                except Exception as e:
                    if "429" in str(e):
                        print("⏳ Rate limit reached. Waiting 60 seconds before retrying this email...")
                        time.sleep(60) # Wait a full minute, then the while loop tries THIS email again
                    else:
                        print(f"⚠️ Failed to process email {msg_id}: {e}")
                        break # If it is a different error, break the loop and move on

if __name__ == "__main__":
    print("Starting automated Reverse ATS pipeline...")
    gmail_service = authenticate_gmail()
    process_recent_emails(gmail_service)
    print("Pipeline execution finished.")