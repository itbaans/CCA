import hmac
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.services.vapi import handle_tool_calls, store_end_of_call

router = APIRouter(prefix="/vapi", tags=["Vapi voice agent"])
settings = get_settings()


def _authenticate(request: Request) -> None:
    expected = settings.vapi_webhook_secret
    if not expected:
        if settings.is_test:
            return
        raise HTTPException(status_code=503, detail="Vapi webhook secret is not configured")
    supplied = request.headers.get("X-Vapi-Secret", "")
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        supplied = authorization[7:]
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Invalid Vapi webhook credentials")


@router.post("/webhook")
async def vapi_webhook(
    request: Request, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _authenticate(request)
    payload = await request.json()
    message = payload.get("message") or {}
    message_type = message.get("type")
    if message_type == "tool-calls":
        return handle_tool_calls(message, db)
    if message_type == "end-of-call-report":
        store_end_of_call(message, db)
    return {"received": True}
