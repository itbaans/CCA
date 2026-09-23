from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter(tags=["Operations"])


@router.get("/health")
async def health(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    return {"data": {"status": "healthy"}, "error": None}
