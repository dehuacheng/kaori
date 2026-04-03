"""Moomoo (Futu) OpenAPI connector.

Uses the moomoo-api SDK for position retrieval.
Requires: pip install moomoo-api

Setup:
1. Enable OpenAPI in the Moomoo app
2. Set connection details via the connect endpoint
"""
import logging

from kaori.services.account_sync import AccountConnector, register_connector

logger = logging.getLogger("kaori.account_sync.moomoo")


class MoomooConnector(AccountConnector):

    async def connect(self, account_id: int, credentials: dict) -> dict:
        # TODO: Validate API connection using moomoo-api
        # credentials: {"host": "127.0.0.1", "port": 11111, "trade_password": "..."}
        raise NotImplementedError("Moomoo connector not yet implemented — use screenshot/PDF import")

    async def handle_callback(self, account_id: int, callback_data: dict) -> bool:
        # Moomoo doesn't use OAuth — connection is direct
        return True

    async def fetch_data(self, account_id: int) -> dict:
        # TODO: Use trd_ctx.position_list_query() to fetch positions
        # Return {"holdings": [{"ticker": ..., "shares": ..., "cost_basis": ...}, ...]}
        raise NotImplementedError

    async def is_connected(self, account_id: int) -> bool:
        # TODO: Try a test query to check connection
        return False


# Register this connector
register_connector("moomoo", MoomooConnector)
