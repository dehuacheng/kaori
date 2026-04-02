from fastapi import Header, HTTPException

from kaori.config import API_TOKEN


async def verify_token(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    if authorization[7:] != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
