# JobSync: Automated Reverse ATS

JobSync is a custom-built, automated “Reverse Applicant Tracking System” designed to put the job seeker in control. Instead of manually updating spreadsheets, this system automatically monitors a synced inbox, uses AI to extract application updates, and visualizes the job hunt on an interactive Kanban board.

## 🚀 The “Reverse ATS” Concept

Standard ATS platforms are enterprise tools used by companies to ingest resumes, parse data, and move applicants through a pipeline. JobSync flips this dynamic. It acts as an ATS for the applicant by using automated data pipelines and Large Language Models (LLMs) to track companies, roles, and interview stages without manual data entry.

## 🛠️ Tech Stack

**Frontend (Dashboard)**

- **Framework:** Next.js 16 (App Router)
- **Styling:** Tailwind CSS (v3 with PostCSS)
- **UI/UX:** Custom Material Design-inspired dark mode interface
- **Interactivity:** `@dnd-kit` for drag-and-drop Kanban functionality
- **State Management:** React Hooks for real-time search and dynamic metric calculations

**Backend & Data Pipeline**

- **Automation:** Python script executed via GitHub Actions
- **Email Ingestion:** Gmail API (processes up to 30 emails per batch)
- **AI Extraction:** Google Gemini API (`gemini-3.8-flash` with automatic fallback to `3.6-flash` for rate limiting)
- **Database:** Neon PostgreSQL (serverless DB connected via `psycopg`)

## ✨ Key Features

- **Automated Data Entry:** A Python pipeline runs on a schedule to fetch recent emails, filtering for keywords like “application”, “interview”, “offer”, or “rejected”.
- **AI Parsing & Classification:** Gemini analyzes the email content to extract the company name, role title, and exact pipeline status, while intelligently ignoring junk or promotional emails.
- **Interactive Kanban Board:** A fully draggable board with distinct columns (Applied, Interviewing, Offer, Rejected) to visualize the job hunt.
- **Dynamic Metrics Dashboard:** Live-calculating statistic cards tracking active pipeline volume, weekly application velocity, interview rates, and offer conversion percentages.
- **Real-time Search:** Instant, client-side filtering across all columns by company name or role title.

## ⚙️ How It Works

1. **Trigger:** GitHub Actions runs the `worker.py` script on a set cron schedule.
2. **Fetch:** The script authenticates with the Gmail API and fetches the latest batch of unread emails.
3. **Analyze:** Email bodies are decoded and sent to the Gemini API with a strict JSON schema prompt to extract the `company_name`, `role_title`, and `status`.
4. **Store:** The extracted data is upserted into a Neon PostgreSQL database.
5. **Visualize:** The Next.js frontend queries the database and renders the updated state on the JobSync dashboard.

## 📦 Setup & Installation

To run this project locally, you will need to set up the following environment variables in a `.env.local` file:

```
DATABASE_URL="your_neon_postgres_connection_string"
GEMINI_API_KEY="your_google_gemini_api_key"
```

*Note: You must also generate a `credentials.json` file from the Google Cloud Console for Gmail API access.*

**Run the Frontend:**

```bash
npm install
npm run dev
```

**Run the Pipeline (Manual):**

```bash
python worker.py
```
