from abc import ABC, abstractmethod


class AccountConnector(ABC):
    """Abstract interface for brokerage/bank API connectors.

    Concrete implementations handle institution-specific authentication
    and data fetching. Callers only depend on this abstract class.
    """

    @abstractmethod
    async def connect(self, account_id: int, credentials: dict) -> dict:
        """Initiate connection. Returns {redirect_url} for OAuth or {connected: True} for API key."""
        ...

    @abstractmethod
    async def handle_callback(self, account_id: int, callback_data: dict) -> bool:
        """Handle OAuth callback or finalize connection. Returns True on success."""
        ...

    @abstractmethod
    async def fetch_data(self, account_id: int) -> dict:
        """Fetch current data. Returns {holdings: [...]} for brokerage accounts."""
        ...

    @abstractmethod
    async def is_connected(self, account_id: int) -> bool:
        """Check if connection is still valid."""
        ...


# Registry of supported connectors
_CONNECTORS: dict[str, type[AccountConnector]] = {}


def register_connector(institution: str, connector_cls: type[AccountConnector]):
    _CONNECTORS[institution] = connector_cls


def get_connector(institution: str) -> AccountConnector | None:
    """Get a connector instance for the given institution, or None if not supported."""
    cls = _CONNECTORS.get(institution)
    if cls:
        return cls()
    return None


def has_connector(institution: str) -> bool:
    """Check if an API connector exists for this institution."""
    return institution in _CONNECTORS
