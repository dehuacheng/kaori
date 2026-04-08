import asyncio
import json

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from kaori.models.finance import (
    AccountCreate,
    AccountUpdate,
    HoldingCreate,
    HoldingUpdate,
    HoldingBulkRequest,
)
from kaori.services import portfolio_service, stock_price_service

router = APIRouter(prefix="/finance", tags=["api-finance"])


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------


@router.get("/accounts")
async def list_accounts(type: str | None = None):
    accounts = await portfolio_service.list_accounts(account_type=type)
    return {"accounts": accounts}


@router.post("/accounts")
async def create_account(body: AccountCreate):
    account = await portfolio_service.create_account(
        name=body.name,
        account_type=body.account_type,
        institution=body.institution,
        notes=body.notes,
    )
    return account


@router.get("/accounts/{account_id}")
async def get_account(account_id: int):
    account = await portfolio_service.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.put("/accounts/{account_id}")
async def update_account(account_id: int, body: AccountUpdate):
    account = await portfolio_service.update_account(
        account_id, name=body.name, notes=body.notes,
    )
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.delete("/accounts/{account_id}")
async def delete_account(account_id: int):
    deleted = await portfolio_service.delete_account(account_id)
    return {"id": account_id, "deleted": deleted}


# ---------------------------------------------------------------------------
# Holdings
# ---------------------------------------------------------------------------


@router.get("/accounts/{account_id}/holdings")
async def list_holdings(account_id: int):
    account = await portfolio_service.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    holdings = await portfolio_service.list_holdings(account_id)
    return {"account_id": account_id, "holdings": holdings}


@router.post("/accounts/{account_id}/holdings")
async def create_holding(account_id: int, body: HoldingCreate):
    account = await portfolio_service.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    holding = await portfolio_service.create_holding(
        account_id,
        ticker=body.ticker,
        shares=body.shares,
        cost_basis=body.cost_basis,
        notes=body.notes,
    )
    return holding


@router.put("/holdings/{holding_id}")
async def update_holding(holding_id: int, body: HoldingUpdate):
    holding = await portfolio_service.update_holding(
        holding_id,
        ticker=body.ticker,
        shares=body.shares,
        cost_basis=body.cost_basis,
        notes=body.notes,
    )
    if not holding:
        raise HTTPException(status_code=404, detail="Holding not found")
    return holding


@router.delete("/holdings/{holding_id}")
async def delete_holding(holding_id: int):
    deleted = await portfolio_service.delete_holding(holding_id)
    return {"id": holding_id, "deleted": deleted}


@router.post("/accounts/{account_id}/holdings/bulk")
async def bulk_replace_holdings(account_id: int, body: HoldingBulkRequest):
    account = await portfolio_service.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    result = await portfolio_service.bulk_replace_holdings(
        account_id, [h.model_dump() for h in body.holdings],
    )
    return {"account_id": account_id, **result}


# ---------------------------------------------------------------------------
# Import (Screenshot/PDF + LLM extraction)
# ---------------------------------------------------------------------------


@router.post("/accounts/{account_id}/import")
async def import_holdings(
    account_id: int,
    files: list[UploadFile] = File(...),
):
    account = await portfolio_service.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    saved_paths = []
    file_datas = []
    import_type = "screenshot"

    for f in files:
        data = await f.read()
        content_type = f.content_type or ""
        file_datas.append(data)

        if "pdf" in content_type:
            import_type = "pdf"
            from kaori.config import STATEMENTS_DIR
            import uuid as _uuid
            path = f"{_uuid.uuid4()}.pdf"
            (STATEMENTS_DIR / path).write_bytes(data)
            saved_paths.append(path)
        else:
            from kaori.storage.file_store import save_photo
            path = save_photo(data)
            saved_paths.append(path)

    # Store all paths as JSON array
    file_path = json.dumps(saved_paths) if len(saved_paths) > 1 else saved_paths[0]

    # Create import record
    analysis = await portfolio_service.create_import(account_id, import_type, file_path)

    # Prepare LLM data
    if import_type == "screenshot":
        from kaori.storage.file_store import get_resized_image_bytes
        llm_images = [get_resized_image_bytes(p) for p in saved_paths]
    else:
        llm_images = file_datas

    asyncio.create_task(
        portfolio_service.run_import_analysis(
            analysis["id"], llm_images, import_type, account["institution"],
        )
    )

    return {"analysis_id": analysis["id"], "status": "pending", "files_count": len(files)}


@router.get("/imports/{analysis_id}")
async def get_import_analysis(analysis_id: int):
    analysis = await portfolio_service.get_import(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    result = dict(analysis)
    if result.get("extracted_json"):
        result["extracted"] = json.loads(result["extracted_json"])
    return result


@router.post("/imports/{analysis_id}/confirm")
async def confirm_import(analysis_id: int, body: HoldingBulkRequest):
    analysis = await portfolio_service.get_import(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis["status"] != "done":
        raise HTTPException(status_code=400, detail="Analysis not yet complete")
    result = await portfolio_service.confirm_import(
        analysis_id, [h.model_dump() for h in body.holdings],
    )
    return result


# ---------------------------------------------------------------------------
# Institution API Sync
# ---------------------------------------------------------------------------


@router.get("/accounts/{account_id}/sync-status")
async def sync_status(account_id: int):
    account = await portfolio_service.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    from kaori.services.account_sync import has_connector
    return {
        "account_id": account_id,
        "institution": account["institution"],
        "has_api_connector": has_connector(account["institution"]),
        "sync_method": account["sync_method"],
        "last_synced_at": account.get("last_synced_at"),
    }


# ---------------------------------------------------------------------------
# Portfolio Summary
# ---------------------------------------------------------------------------


@router.get("/portfolio/summary")
async def portfolio_summary(date: str | None = None):
    from datetime import date as date_cls
    target = date or date_cls.today().isoformat()
    return await portfolio_service.get_portfolio_summary(target)


@router.post("/portfolio/refresh-prices")
async def refresh_prices():
    return await stock_price_service.refresh_all_prices()


@router.post("/portfolio/snapshot")
async def take_snapshot(
    date: str | None = None,
    use_historical_close: bool = False,
):
    return await portfolio_service.take_snapshot(
        date,
        use_historical_close=use_historical_close,
    )
