from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_env: str = "development"
    secret_key: str = "change-me"
    api_key: str = "change-me"

    # Database
    database_url: str = "sqlite:///./fordaq_agent.db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Vapi
    vapi_api_key: str = ""
    vapi_phone_number_id: str = ""
    vapi_assistant_id: str = ""
    vapi_webhook_secret: str = ""

    # Retell
    retell_api_key: str = ""
    retell_agent_id: str = ""
    retell_phone_number: str = ""

    # Google Sheets
    google_sheets_credentials_file: str = "credentials.json"
    google_sheets_lead_sheet_id: str = ""
    google_sheets_lead_tab: str = "Leads"
    google_sheets_call_log_tab: str = "Call Log"
    google_sheets_report_tab: str = "Daily Report"

    # Anthropic
    anthropic_api_key: str = ""

    # Calling config
    voice_provider: str = "vapi"
    max_calls_per_day: int = 100
    call_start_hour: int = 9
    call_end_hour: int = 18
    retry_no_answer_after_hours: int = 24
    max_call_retries: int = 3
    call_timeout_seconds: int = 60

    # Compliance
    company_name: str = "Fordaq"
    identify_as: str = "Fordaq Lead Activation Team"
    caller_id_name: str = "Fordaq"
    opt_out_phrase: str = "stop calling"
    gdpr_mode: bool = True

    # Public URL
    public_base_url: str = "https://your-domain.com"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
