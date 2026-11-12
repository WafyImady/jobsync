import os
import json
import base64
import random
import re
import time
from html.parser import HTMLParser
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
gemini_client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY"),
    http_options={'timeout': 30000} # 30 seconds in milliseconds
)

# 2. Gmail API Scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

TRANSIENT_MODEL_STATUSES = {'429', '500', '503', '504'}
TRANSIENT_MODEL_ERRORS = (
    'deadline_exceeded',
    'resource_exhausted',
    'temporarily unavailable',
    'timed out',
    'timeout',
    'connection reset',
)


class GeminiDailyQuotaExceeded(Exception):
    pass


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = []

    def handle_data(self, data):
        self.text.append(data)


def _is_transient_model_error(error):
    status_codes = {
        str(getattr(error, attribute, ''))
        for attribute in ('code', 'status_code')
    }
    response = getattr(error, 'response', None)
    if response is not None:
        status_codes.add(str(getattr(response, 'status_code', '')))

    message = str(error).lower()
    status_codes.update(re.findall(r'\b(?:429|500|503|504)\b', message))
    return bool(status_codes & TRANSIENT_MODEL_STATUSES) or any(
        marker in message for marker in TRANSIENT_MODEL_ERRORS
    )


def _is_daily_quota_error(error):
    message = str(error).lower()
    return 'per day' in message and ('quota' in message or 'limit exceeded' in message)


def _decode_part(part):
    data = part.get('body', {}).get('data')
    if not data:
        return ''
    padded_data = data + '=' * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded_data).decode('utf-8', errors='replace')


def _email_body(payload):
    plain_text = []
    html_text = []
    parts = [payload]

    while parts:
        part = parts.pop()
        mime_type = part.get('mimeType', '').lower()
        if mime_type in ('text/plain', 'text/html'):
            decoded = _decode_part(part)
            if decoded.strip():
                (plain_text if mime_type == 'text/plain' else html_text).append(decoded)
        parts.extend(reversed(part.get('parts', [])))

    if plain_text:
        return plain_text[0]
    if html_text:
        extractor = _HTMLTextExtractor()
        extractor.feed(html_text[0])
        return ' '.join(' '.join(extractor.text).split())
    return ''


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
    """Fetches email IDs recorded after successful processing."""
    conn_string = os.getenv("DATABASE_URL")
    with psycopg.connect(conn_string) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS worker_processed_emails (
                    source_email_id TEXT PRIMARY KEY,
                    outcome TEXT NOT NULL DEFAULT 'processed',
                    processed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                INSERT INTO worker_processed_emails (source_email_id)
                SELECT source_email_id
                FROM applications
                WHERE source_email_id IS NOT NULL
                ON CONFLICT (source_email_id) DO NOTHING
            """)
            cur.execute("SELECT source_email_id FROM worker_processed_emails")
            return {row[0] for row in cur.fetchall()}


def record_processed_email(email_id, outcome='processed'):
    conn_string = os.getenv("DATABASE_URL")
    with psycopg.connect(conn_string) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO worker_processed_emails (source_email_id, outcome)
                VALUES (%s, %s)
                ON CONFLICT (source_email_id)
                DO UPDATE SET outcome = EXCLUDED.outcome
                """,
                (email_id, outcome)
            )

def extract_job_data(email_text: str):
    """Extracts job data, falling back and retrying transient Gemini failures."""
    
    # 🚨 FIX 1: Send only the first 2000 characters to prevent Token limits
    truncated_text = email_text[:2000]
    
    prompt = """
    Analyze the following email. If it is a job application update, extract the company name, the role applied for, and determine the status.
    Status MUST be one of: 'Applied', 'Interviewing', 'Rejected', 'Offer'.
    If the email is promotional or unrelated to an active application, set status to 'ignore'.
    CRITICAL: Ignore job board platforms like 'Indeed', 'LinkedIn', 'JobStreet', 'Hiredly', or 'Glassdoor' for the company name. Extract the ACTUAL hiring company.
    
    Return EXACTLY this JSON structure:
    {"company_name": "String", "role_title": "String", "status": "String"}
    
    Email content:
    """ + truncated_text
    
    max_retries = 3
    models = ('gemini-3.8-flash', 'gemini-3.6-flash')
    last_error = None

    for attempt in range(max_retries):
        for model_index, model in enumerate(models):
            try:
                response = gemini_client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config={"response_mime_type": "application/json"}
                )
                extracted_data = json.loads(response.text)
                if not isinstance(extracted_data, dict):
                    raise ValueError("Gemini response must be a JSON object")
                valid_statuses = {
                    'applied': 'Applied',
                    'interviewing': 'Interviewing',
                    'rejected': 'Rejected',
                    'offer': 'Offer',
                    'ignore': 'ignore',
                }
                for field in ('company_name', 'role_title', 'status'):
                    if not isinstance(extracted_data.get(field), str) or not extracted_data[field].strip():
                        raise ValueError(f"Gemini response has an invalid {field}")
                status = extracted_data['status'].strip().lower()
                if status not in valid_statuses:
                    raise ValueError(f"Gemini response has an invalid status: {status}")
                extracted_data['company_name'] = extracted_data['company_name'].strip()
                extracted_data['role_title'] = extracted_data['role_title'].strip()
                extracted_data['status'] = valid_statuses[status]
                return extracted_data
            except Exception as error:
                if _is_daily_quota_error(error):
                    raise GeminiDailyQuotaExceeded(
                        "Gemini daily request quota is exhausted; stopping AI processing for this run."
                    ) from error
                if not _is_transient_model_error(error):
                    raise
                last_error = error
                if model_index == 0:
                    print("⚠️ Primary model busy or timed out; trying fallback model...")
                else:
                    print(f"⚠️ Fallback model also failed transiently: {error}")

        if attempt < max_retries - 1:
            wait_time = min(30, 5 * (2 ** attempt)) + random.uniform(0, 2)
            print(
                f"⏳ Both models unavailable. Retrying in {wait_time:.1f} seconds "
                f"(retry {attempt + 1}/{max_retries - 1})..."
            )
            time.sleep(wait_time)

    raise last_error

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
    
    with psycopg.connect(conn_string) as conn:
        with conn.cursor() as cur:
            cur.execute(upsert_query, (company_name, role_title, status, email_id, email_date))

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
    
    attempted_count = 0
    recorded_count = 0
    failed_count = 0
    deferred_count = 0
    quota_exhausted = False
    max_per_run = 30

    for message_index, msg in enumerate(messages):
        if attempted_count >= max_per_run:
            print("🛑 Reached maximum 30 emails for this run. Stopping to protect GitHub minutes.")
            break
            
        msg_id = msg['id']
        
        if msg_id in processed_ids:
            print(f"⏭️ Skipping already processed email: {msg_id}")
            continue
            
        attempted_count += 1
        print(f"Processing email {attempted_count}/{max_per_run}: {msg_id}")

        try:
            message = service.users().messages().get(
                userId='me', id=msg_id, format='full'
            ).execute()
            payload = message.get('payload', {})
            email_text = _email_body(payload)

            if not email_text:
                print(f"⚠️ Skipping email {msg_id}: no readable plain-text or HTML body.")
                record_processed_email(msg_id, 'skipped_no_body')
                processed_ids.add(msg_id)
                recorded_count += 1
                continue

            headers = payload.get('headers', [])
            date_header = next(
                (header['value'] for header in headers if header['name'].lower() == 'date'),
                None
            )
            subject_header = next(
                (header['value'] for header in headers if header['name'].lower() == 'subject'),
                'No Subject'
            )
            email_date = parsedate_to_datetime(date_header) if date_header else None
            combined_text = f"Subject: {subject_header}\n\nEmail Body:\n{email_text}"
            extracted_data = extract_job_data(combined_text)

            company_name = extracted_data['company_name'].title()
            role_title = extracted_data['role_title'].title()
            status = extracted_data['status']

            upsert_application(company_name, role_title, status, msg_id, email_date)
            record_processed_email(msg_id)
            processed_ids.add(msg_id)
            recorded_count += 1

            if status.lower() == 'ignore':
                print(f"✅ Logged junk email: {msg_id}")
            else:
                received_date = email_date.date() if email_date else 'No Date'
                print(f"✅ Success: Upserted {company_name} - {status} ({received_date})")
            time.sleep(15)
        except GeminiDailyQuotaExceeded as error:
            deferred_count += 1
            quota_exhausted = True
            print(f"⏸️ Deferring remaining emails because Gemini daily quota is exhausted: {error}")
            break
        except psycopg.Error:
            raise
        except Exception as error:
            failed_count += 1
            print(f"⚠️ Failed to process email {msg_id}; it can be retried next run: {error}")

    if quota_exhausted:
        deferred_count += sum(
            1 for message in messages[message_index + 1:]
            if message['id'] not in processed_ids
        )

    summary = (
        f"Worker summary: {attempted_count} attempted, "
        f"{recorded_count} recorded as processed or skipped, "
        f"{failed_count} failed and eligible for retry, {deferred_count} deferred."
    )
    print(summary)

    if failed_count or deferred_count:
        print("::warning::The worker completed with emails eligible for a later retry.")

    summary_path = os.getenv('GITHUB_STEP_SUMMARY')
    if summary_path:
        with open(summary_path, 'a', encoding='utf-8') as summary_file:
            summary_file.write(
                "## Worker run summary\n\n"
                f"- Attempted: {attempted_count}\n"
                f"- Recorded as processed or skipped: {recorded_count}\n"
                f"- Failed and eligible for retry: {failed_count}\n"
                f"- Deferred: {deferred_count}\n"
            )

if __name__ == "__main__":
    print("Starting automated Reverse ATS pipeline...")
    gmail_service = authenticate_gmail()
    process_recent_emails(gmail_service)
    print("Pipeline execution finished.")