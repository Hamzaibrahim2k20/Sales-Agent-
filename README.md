# Fordaq Lead Activation Agent — MVP v1

A semi-automated calling agent that calls Fordaq members, qualifies buyers and sellers,
logs structured call outcomes, scores leads, and flags hot opportunities for human follow-up.

## What It Does

| Step | Who | What |
|------|-----|------|
| Import leads | System | Reads from CSV or Google Sheets |
| Score leads | System | 0–100 score, urgency, membership potential |
| Make calls | Voice agent (Vapi/Retell) | Calls with the right script |
| Qualify | AI agent | Buyer/seller, products, species, volume, markets |
| Log results | System | Structured JSON → DB + Google Sheets |
| Escalate | Human | Pricing, invoices, complaints, renewals |
| Report | System | Daily report → dashboard + Google Sheets |

## Architecture

```
Google Sheets / CSV
        ↓
Lead Import + Deduplication
        ↓
Lead Scoring Engine
        ↓
Call Queue  →  Voice Agent (Vapi / Retell)
                       ↓
              Webhook → FastAPI
                       ↓
         Claude extracts structured output
                       ↓
    DB + Google Sheets + Dashboard
                       ↓
        Human Follow-up Queue
```

## Quick Start

### 1. Install dependencies

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — fill in your API keys
```

Required keys for MVP:
- `VAPI_API_KEY` — get from [app.vapi.ai](https://app.vapi.ai)
- `ANTHROPIC_API_KEY` — get from [console.anthropic.com](https://console.anthropic.com)
- `PUBLIC_BASE_URL` — your public server URL (for webhooks)

Optional (for Google Sheets sync):
- `GOOGLE_SHEETS_CREDENTIALS_FILE` — service account JSON
- `GOOGLE_SHEETS_LEAD_SHEET_ID` — your sheet ID

### 3. Start the server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open: http://localhost:8000 → dashboard
API docs: http://localhost:8000/docs

### 4. Import leads from CSV

```bash
# Preview (dry run)
python scripts/import_csv.py templates/lead_sheet_template.csv --dry-run

# Import
python scripts/import_csv.py your_leads.csv
```

### 5. Make your first call

```bash
curl -X POST http://localhost:8000/api/v1/calls/initiate \
  -H "Content-Type: application/json" \
  -d '{"lead_id": "FDQ-001"}'
```

Or use the dashboard → Call Queue → Click "Call".

## Voice Platform Setup

### Option A: Vapi (Recommended for MVP)

1. Create account at [app.vapi.ai](https://app.vapi.ai)
2. Add a phone number (US/UK/EU available)
3. Create an Assistant using `templates/vapi_assistant_config.json`
4. Copy the Assistant ID and Phone Number ID to `.env`
5. Set webhook URL in Vapi dashboard to `https://your-domain.com/webhooks/vapi`

### Option B: Retell

1. Create account at [retellai.com](https://www.retellai.com)
2. Create an agent, add a phone number
3. Copy Agent ID and API key to `.env`
4. Set `VOICE_PROVIDER=retell` in `.env`
5. Set webhook URL to `https://your-domain.com/webhooks/retell`

## Google Sheets Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project → Enable Sheets API + Drive API
3. Create a Service Account → Download JSON key → save as `credentials.json`
4. Create a Google Sheet using `templates/lead_sheet_template.csv` as the structure
5. Share the sheet with your service account email (Editor)
6. Copy the Sheet ID from the URL into `.env`

### Lead Sheet Columns

| Column | Description |
|--------|-------------|
| lead_id | Unique ID (FDQ-001, etc.) |
| company_name | Company name |
| contact_name | Person to speak to |
| country | Country |
| phone | Phone number (international format) |
| email | Email |
| language | en, fr, de, ar, etc. |
| member_type | free, bronze, silver, gold, expired |
| registration_date | YYYY-MM-DD |
| last_activity | YYYY-MM-DD |
| buyer_or_seller | buyer / seller / both |
| product_interest | What they buy or sell |
| posted_offer | TRUE/FALSE |
| posted_request | TRUE/FALSE |
| assigned_salesperson | Name of Fordaq sales owner |
| last_contact_date | YYYY-MM-DD |
| do_not_call | TRUE/FALSE |
| lead_score | Auto-filled after scoring |
| call_status | pending / connected / no_answer / etc. |
| call_summary | Auto-filled after call |
| next_action | Auto-filled after call |
| follow_up_date | YYYY-MM-DD |
| human_escalation | TRUE/FALSE |
| escalation_reason | Text |
| notes | Free notes |
| source | google_sheets / csv_import / manual |

## Lead Scoring

Scores are 0–100. Higher = higher priority.

**Buyer signals:**
- Posted clear request: +25
- Has phone + email: +10
- Regular/monthly demand: +20
- Clear product specs: +15
- Import-relevant market: +10
- Requested supplier contact: +15
- Decision maker confirmed: +5

**Seller signals:**
- Has export-ready products: +25
- Has current stock: +15
- Has target markets: +15
- Has certification/specs: +10
- Export country origin: +10
- Decision maker confirmed: +10

**Priority:**
- 80–100 → Hot → Follow up today
- 50–79  → Warm → Follow up this week
- <50    → Cold → Nurture

## Human Escalation Rules

The agent escalates when the lead says any of:
- "What is the membership price"
- "Can I get a discount"
- "I want an invoice"
- "I want to renew"
- "I had a bad experience / complaint"
- "A company cheated me"
- "I want advertising / banner"
- "I want to speak to a manager"
- "I want a refund"

The agent collects details only. All commercial decisions are made by the human team.

## API Reference

Full interactive docs at `/docs`.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/leads/` | GET | List all leads |
| `/api/v1/leads/` | POST | Create a lead |
| `/api/v1/leads/queue` | GET | Prioritised call queue |
| `/api/v1/leads/sync-from-sheets` | POST | Pull leads from Google Sheets |
| `/api/v1/leads/bulk-import` | POST | Import leads from JSON |
| `/api/v1/calls/initiate` | POST | Start a call |
| `/api/v1/calls/bulk-initiate` | POST | Queue multiple calls |
| `/api/v1/calls/` | GET | List call logs |
| `/webhooks/vapi` | POST | Vapi call-end webhook |
| `/webhooks/retell` | POST | Retell call-end webhook |
| `/api/v1/reports/today` | GET | Today's report |
| `/api/v1/reports/generate` | POST | Generate report |
| `/api/v1/dashboard/stats` | GET | Dashboard stats |
| `/api/v1/dashboard/escalations` | GET | Pending escalations |
| `/api/v1/dashboard/hot-leads` | GET | Hot leads list |

## Daily Workflow

```
Morning:
1. python scripts/import_csv.py new_leads.csv   (or sync from Sheets)
2. Open dashboard → review hot leads + escalations
3. Start call queue from dashboard

During the day:
4. Calls run → results auto-log to DB + Sheets
5. Hot leads / escalations appear in dashboard

End of day:
6. python scripts/run_daily_report.py --sync-sheets
7. Review report + action escalations
```

## File Structure

```
├── main.py                    # FastAPI app
├── config.py                  # Settings from .env
├── database.py                # SQLAlchemy setup
├── models.py                  # Lead, CallLog, DailyReport
├── schemas.py                 # Pydantic schemas
├── api/
│   ├── leads.py               # Lead CRUD endpoints
│   ├── calls.py               # Call initiation endpoints
│   ├── webhooks.py            # Vapi/Retell webhook receivers
│   ├── reports.py             # Report endpoints
│   └── dashboard.py           # Dashboard stats endpoints
├── services/
│   ├── lead_scoring.py        # 0–100 scoring engine
│   ├── vapi_client.py         # Vapi + Retell clients
│   ├── google_sheets.py       # Google Sheets read/write
│   ├── call_processor.py      # Transcript → structured JSON
│   ├── follow_up.py           # Email draft generator
│   └── report_generator.py    # Daily report builder
├── agent/
│   └── system_prompt.py       # Master prompt + call scripts
├── knowledge_base/
│   ├── fordaq_overview.md
│   ├── membership_rules.md
│   ├── product_categories.md
│   ├── objections.md
│   ├── forbidden_claims.md
│   ├── escalation_rules.md
│   └── country_rules.md
├── templates/
│   ├── lead_sheet_template.csv
│   └── vapi_assistant_config.json
├── scripts/
│   ├── import_csv.py
│   ├── score_all_leads.py
│   └── run_daily_report.py
└── dashboard/
    ├── index.html
    └── static/
        ├── style.css
        └── app.js
```

## Compliance Notes

- The agent always identifies itself as calling from Fordaq
- Opt-out requests are respected immediately and logged
- Do-not-call flag prevents re-calling
- GDPR mode enabled by default
- Call recordings: check local laws before enabling
- EU: review ePrivacy Directive requirements for automated calling per country
- Saudi Arabia / Gulf: avoid calls on Fridays
- See `knowledge_base/country_rules.md` for country-specific guidance

## Development Phases

- **Phase 1 (this MVP):** CSV + Vapi + Google Sheets + structured notes
- **Phase 2:** Automatic Fordaq export → deduplication → CRM notes → email drafts
- **Phase 3:** Fordaq admin integration + renewal logic + full compliance dashboard
