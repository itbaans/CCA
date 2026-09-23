from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import Envelope, PatientCreate, PatientList, PatientRead, PatientUpdate, normalize_phone
from app.services import patients as patient_service

router = APIRouter(prefix="/patients", tags=["Patients"])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=Envelope)
async def list_patients(
    db: DbSession,
    last_name: str | None = Query(default=None, min_length=1, max_length=50),
    date_of_birth: date | None = None,
    phone_number: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Envelope:
    try:
        normalized_phone = normalize_phone(phone_number) if phone_number else None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    records, total = patient_service.list_patients(
        db,
        last_name=last_name,
        date_of_birth=date_of_birth,
        phone_number=normalized_phone,
        limit=limit,
        offset=offset,
    )
    result = PatientList(
        items=[PatientRead.model_validate(record) for record in records],
        total=total,
        limit=limit,
        offset=offset,
    )
    return Envelope(data=result.model_dump(mode="json"))


@router.get("/{patient_id}", response_model=Envelope)
async def retrieve_patient(patient_id: str, db: DbSession) -> Envelope:
    patient = patient_service.get_patient(db, patient_id)
    return Envelope(data=PatientRead.model_validate(patient).model_dump(mode="json"))


@router.post("", response_model=Envelope, status_code=status.HTTP_201_CREATED)
async def create_patient(payload: PatientCreate, db: DbSession) -> Envelope:
    patient = patient_service.create_patient(db, payload)
    return Envelope(data=PatientRead.model_validate(patient).model_dump(mode="json"))


@router.put("/{patient_id}", response_model=Envelope)
async def update_patient(patient_id: str, payload: PatientUpdate, db: DbSession) -> Envelope:
    patient = patient_service.update_patient(db, patient_id, payload)
    return Envelope(data=PatientRead.model_validate(patient).model_dump(mode="json"))


@router.delete("/{patient_id}", response_model=Envelope)
async def delete_patient(patient_id: str, db: DbSession) -> Envelope:
    patient = patient_service.soft_delete_patient(db, patient_id)
    return Envelope(
        data={"patient_id": patient.patient_id, "deleted_at": patient.deleted_at.isoformat()}
    )
