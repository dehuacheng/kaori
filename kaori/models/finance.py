from pydantic import BaseModel


class AccountCreate(BaseModel):
    name: str
    account_type: str = "brokerage"
    institution: str
    notes: str | None = None


class AccountUpdate(BaseModel):
    name: str | None = None
    notes: str | None = None


class HoldingCreate(BaseModel):
    ticker: str
    shares: float
    cost_basis: float | None = None
    notes: str | None = None


class HoldingUpdate(BaseModel):
    ticker: str | None = None
    shares: float | None = None
    cost_basis: float | None = None
    notes: str | None = None


class HoldingBulkEntry(BaseModel):
    ticker: str
    shares: float
    cost_basis: float | None = None
    description: str | None = None


class HoldingBulkRequest(BaseModel):
    holdings: list[HoldingBulkEntry]
