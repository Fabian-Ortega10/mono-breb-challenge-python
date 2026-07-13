import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    PORT = int(os.getenv("PORT", "3000"))
    BASE_URL = os.getenv("MONO_BASE_URL", "https://breb-participant.sandbox.mono.la")
    CLIENT_ID = os.getenv("MONO_CLIENT_ID", "")
    CLIENT_SECRET = os.getenv("MONO_CLIENT_SECRET", "")
    SCOPES = os.getenv(
        "MONO_SCOPES",
        "collections outgoing_transfers target_resolutions tenant_accounts:readonly",
    )
    TENANT_ACCOUNT_ID = os.getenv("MONO_TENANT_ACCOUNT_ID", "")
    WEBHOOK_SECRET = os.getenv("MONO_WEBHOOK_SECRET", "")


config = Config()
