"""
Google Sheets integration.
Reads leads from, and writes call summaries back to, a Google Sheet.

Setup:
1. Create a Google Cloud project, enable Sheets API and Drive API.
2. Create a Service Account, download the JSON key as credentials.json.
3. Share your Google Sheet with the service account email (Editor).
4. Set GOOGLE_SHEETS_LEAD_SHEET_ID in .env.
"""

import logging
from datetime import datetime
from typing import Optional
import gspread
from google.oauth2.service_account import Credentials
from config import settings

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ── Column definitions ────────────────────────────────────────────────
# Must match the Google Sheet column order exactly.

LEAD_COLUMNS = [
    "lead_id",
    "company_name",
    "contact_name",
    "country",
    "phone",
    "email",
    "language",
    "member_type",
    "registration_date",
    "last_activity",
    "buyer_or_seller",
    "product_interest",
    "posted_offer",
    "posted_request",
    "assigned_salesperson",
    "last_contact_date",
    "do_not_call",
    "lead_score",
    "call_status",
    "call_summary",
    "next_action",
    "follow_up_date",
    "human_escalation",
    "escalation_reason",
    "notes",
    "source",
]

CALL_LOG_COLUMNS = [
    "call_id",
    "lead_id",
    "company_name",
    "contact_name",
    "country",
    "phone",
    "call_result",
    "duration_seconds",
    "call_date",
    "lead_type",
    "products",
    "species",
    "volume",
    "destination_market",
    "origin_preference",
    "urgency",
    "membership_potential",
    "lead_score",
    "summary",
    "next_action",
    "human_escalation_required",
    "escalation_reason",
    "follow_up_date",
    "follow_up_message",
]


def _get_client() -> gspread.Client:
    creds = Credentials.from_service_account_file(
        settings.google_sheets_credentials_file,
        scopes=SCOPES,
    )
    return gspread.authorize(creds)


def _get_sheet(tab_name: str) -> gspread.Worksheet:
    client = _get_client()
    sheet = client.open_by_key(settings.google_sheets_lead_sheet_id)
    try:
        return sheet.worksheet(tab_name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title=tab_name, rows=1000, cols=30)
        return ws


# ── Read leads ────────────────────────────────────────────────────────

def fetch_leads(max_rows: int = 500) -> list[dict]:
    """
    Read all leads from the Lead Sheet tab.
    Returns a list of dicts keyed by LEAD_COLUMNS.
    """
    ws = _get_sheet(settings.google_sheets_lead_tab)
    rows = ws.get_all_records(head=1, default_blank="", numericise_ignore=["phone"])

    leads = []
    for i, row in enumerate(rows[:max_rows]):
        cleaned = {col: row.get(col, "") for col in LEAD_COLUMNS}
        # Skip if no company name or phone
        if not cleaned.get("company_name") or not cleaned.get("phone"):
            continue
        # Skip do-not-call
        if str(cleaned.get("do_not_call", "")).lower() in ("true", "yes", "1"):
            continue
        leads.append(cleaned)

    logger.info("Fetched %d leads from Google Sheets", len(leads))
    return leads


# ── Write call log ────────────────────────────────────────────────────

def append_call_log(call_data: dict) -> None:
    """Append one call result row to the Call Log tab."""
    ws = _get_sheet(settings.google_sheets_call_log_tab)

    # Ensure header row exists
    existing = ws.row_values(1)
    if not existing:
        ws.append_row(CALL_LOG_COLUMNS)

    row = [str(call_data.get(col, "")) for col in CALL_LOG_COLUMNS]
    ws.append_row(row)
    logger.info("Appended call log for call_id=%s", call_data.get("call_id"))


# ── Update lead status ────────────────────────────────────────────────

def update_lead_status(lead_id: str, updates: dict) -> bool:
    """
    Find the row with matching lead_id and update specified columns.
    Returns True if row was found and updated.
    """
    ws = _get_sheet(settings.google_sheets_lead_tab)
    all_values = ws.get_all_values()
    if not all_values:
        return False

    header = all_values[0]
    try:
        id_col_idx = header.index("lead_id")
    except ValueError:
        logger.warning("lead_id column not found in sheet header")
        return False

    for row_idx, row in enumerate(all_values[1:], start=2):
        if len(row) > id_col_idx and row[id_col_idx] == str(lead_id):
            for col_name, value in updates.items():
                try:
                    col_idx = header.index(col_name) + 1  # 1-indexed for gspread
                    ws.update_cell(row_idx, col_idx, str(value))
                except ValueError:
                    pass
            return True

    return False


# ── Write daily report ────────────────────────────────────────────────

def write_daily_report(report: dict) -> None:
    """Write or overwrite today's daily report in the Daily Report tab."""
    ws = _get_sheet(settings.google_sheets_report_tab)
    ws.clear()

    today = datetime.now().strftime("%Y-%m-%d")
    rows = [
        ["FORDAQ CALLING AGENT — DAILY REPORT", today],
        [],
        ["METRIC", "VALUE"],
        ["Leads imported", report.get("leads_imported", 0)],
        ["Leads called", report.get("leads_called", 0)],
        ["Calls connected", report.get("calls_connected", 0)],
        ["Qualified buyers", report.get("qualified_buyers", 0)],
        ["Qualified sellers", report.get("qualified_sellers", 0)],
        ["Premium prospects", report.get("premium_prospects", 0)],
        ["Renewal prospects", report.get("renewal_prospects", 0)],
        ["Human escalations", report.get("human_escalations", 0)],
        ["Wrong numbers", report.get("wrong_numbers", 0)],
        ["No answer", report.get("no_answer", 0)],
        ["Not interested", report.get("not_interested", 0)],
        [],
        ["TOP PRODUCTS"],
    ]

    for p in report.get("top_products", []):
        rows.append([p.get("product", ""), p.get("count", "")])

    rows.append([])
    rows.append(["TOP COUNTRIES"])
    for c in report.get("top_countries", []):
        rows.append([c.get("country", ""), c.get("count", "")])

    rows.append([])
    rows.append(["BEST LEADS"])
    for lead in report.get("best_leads", []):
        rows.append([
            lead.get("company_name", ""),
            lead.get("country", ""),
            lead.get("lead_type", ""),
            lead.get("lead_score", ""),
            lead.get("next_action", ""),
        ])

    rows.append([])
    rows.append(["MARKET COMMENTS"])
    rows.append([report.get("market_comments", "")])

    ws.update("A1", rows)
    logger.info("Daily report written to Google Sheets")


# ── Sheet setup helper ────────────────────────────────────────────────

def ensure_lead_sheet_headers() -> None:
    """Create the Leads tab with correct headers if it doesn't exist."""
    ws = _get_sheet(settings.google_sheets_lead_tab)
    first_row = ws.row_values(1)
    if not first_row:
        ws.append_row(LEAD_COLUMNS)
        logger.info("Lead sheet headers created")
