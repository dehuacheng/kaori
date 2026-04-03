"""Charles Schwab Trader API connector.

Uses the schwab-py SDK for OAuth 2.0 authentication and holdings retrieval.
Requires: pip install schwab-py

Setup:
1. Register an app at https://developer.schwab.com/
2. Set SCHWAB_APP_KEY and SCHWAB_APP_SECRET environment variables
3. Use the connect endpoint to initiate OAuth flow
"""
import logging

from kaori.services.account_sync import AccountConnector, register_connector

logger = logging.getLogger("kaori.account_sync.schwab")


class SchwabConnector(AccountConnector):

    async def connect(self, account_id: int, credentials: dict) -> dict:
        # TODO: Implement OAuth 2.0 flow using schwab-py
        # 1. Build authorization URL
        # 2. Return redirect URL for user to authorize
        raise NotImplementedError("Schwab connector not yet implemented — use screenshot/PDF import")

    async def handle_callback(self, account_id: int, callback_data: dict) -> bool:
        # TODO: Exchange authorization code for tokens
        # Store tokens in financial_accounts.api_credentials
        raise NotImplementedError

    async def fetch_data(self, account_id: int) -> dict:
        # TODO: Fetch positions via Accounts & Trading endpoint
        # Return {"holdings": [{"ticker": ..., "shares": ..., "cost_basis": ...}, ...]}
        raise NotImplementedError

    async def is_connected(self, account_id: int) -> bool:
        # TODO: Check if tokens are still valid (access token: 30min, refresh: 7 days)
        return False


# Register this connector
register_connector("schwab", SchwabConnector)
