import json
import logging
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models import CallSession
from app.schemas import PatientCreate, PatientUpdate, normalize_phone
from app.services import patients as patient_service

logger = logging.getLogger(__name__)


def _json_result(payload: dict[str, Any]) -> str:
    """Vapi function results must be single-line strings."""
    return json.dumps(payload, separators=(",", ":"), default=str)


def _call_id(message: dict[str, Any], tool_call_id: str) -> str:
    call = message.get("call") or {}
    return str(call.get("id") or message.get("callId") or f"vapi-{tool_call_id}")


def _caller_phone(message: dict[str, Any]) -> str | None:
    customer = message.get("customer") or (message.get("call") or {}).get("customer") or {}
    return customer.get("number")


def check_existing_patient(arguments: dict[str, Any], db: Session) -> str:
    phone = normalize_phone(str(arguments.get("phone_number", "")))
    patient = patient_service.find_by_phone(db, phone)
    if not patient:
        return _json_result({"found": False})
    return _json_result(
        {
            "found": True,
            "patient_id": patient.patient_id,
            "first_name": patient.first_name,
            "last_name": patient.last_name,
        }
    )


def save_registration(
    arguments: dict[str, Any], message: dict[str, Any], tool_call_id: str, db: Session
) -> str:
    if arguments.get("confirmed") is not True:
        return _json_result(
            {"success": False, "reason": "Caller confirmation is required before saving."}
        )

    payload_data = {
        key: value
        for key, value in arguments.items()
        if key in PatientCreate.model_fields and value not in ("", None)
    }
    payload = PatientCreate.model_validate(payload_data)
    call_id = _call_id(message, tool_call_id)
    session = db.get(CallSession, call_id)

    if session and session.status == "completed" and session.patient_id:
        patient = patient_service.get_patient(db, session.patient_id)
        return _json_result(
            {
                "success": True,
                "action": "already_saved",
                "patient_id": patient.patient_id,
                "first_name": patient.first_name,
            }
        )

    existing = patient_service.find_by_phone(db, payload.phone_number)
    update_existing = arguments.get("update_existing") is True
    if existing and not update_existing:
        return _json_result(
            {
                "success": False,
                "duplicate": True,
                "first_name": existing.first_name,
                "last_name": existing.last_name,
                "instruction": (
                    "Ask whether the caller wants to update the existing record, "
                    "then reconfirm before retrying."
                ),
            }
        )

    if existing:
        validated_changes = {key: getattr(payload, key) for key in payload_data}
        changes = PatientUpdate.model_validate(validated_changes)
        patient = patient_service.update_patient(db, existing.patient_id, changes)
        action = "updated"
    else:
        patient = patient_service.create_patient(db, payload)
        action = "created"

    if not session:
        session = CallSession(
            call_sid=call_id,
            caller_phone=_caller_phone(message),
            current_field="complete",
        )
    session.status = "completed"
    session.patient_id = patient.patient_id
    session.collected_data = payload.model_dump(mode="json")
    db.add(session)
    db.commit()
    logger.info(
        "vapi_registration_completed action=%s patient_id=%s call_id=%s",
        action,
        patient.patient_id,
        call_id,
    )
    return _json_result(
        {
            "success": True,
            "action": action,
            "patient_id": patient.patient_id,
            "first_name": patient.first_name,
        }
    )


def handle_tool_calls(message: dict[str, Any], db: Session) -> dict[str, list[dict[str, str]]]:
    tool_calls = message.get("toolCallList") or []
    results: list[dict[str, str]] = []
    for tool_call in tool_calls:
        tool_call_id = str(tool_call.get("id", ""))
        function = tool_call.get("function") or {}
        name = tool_call.get("name") or function.get("name")
        arguments = (
            tool_call.get("arguments")
            or tool_call.get("parameters")
            or function.get("arguments")
            or {}
        )
        try:
            if name == "check_existing_patient":
                result = check_existing_patient(arguments, db)
            elif name == "save_patient_registration":
                result = save_registration(arguments, message, tool_call_id, db)
            else:
                results.append({"toolCallId": tool_call_id, "error": f"Unknown tool: {name}"})
                continue
            results.append({"toolCallId": tool_call_id, "result": result})
        except (ValidationError, ValueError) as exc:
            results.append(
                {
                    "toolCallId": tool_call_id,
                    "error": f"Validation failed: {str(exc).replace(chr(10), ' ')}",
                }
            )
        except Exception:
            db.rollback()
            logger.exception("Vapi tool execution failed", extra={"tool_name": name})
            results.append(
                {
                    "toolCallId": tool_call_id,
                    "error": "The registration service is temporarily unavailable.",
                }
            )
    return {"results": results}


def store_end_of_call(message: dict[str, Any], db: Session) -> None:
    call = message.get("call") or {}
    call_id = call.get("id")
    if not call_id:
        return
    session = db.get(CallSession, call_id)
    if not session:
        session = CallSession(
            call_sid=call_id,
            caller_phone=_caller_phone(message),
            status="ended_without_registration",
            current_field="unknown",
        )
    artifact = message.get("artifact") or {}
    transcript = []
    for item in artifact.get("messages") or []:
        text = item.get("message") or item.get("content")
        if text:
            transcript.append({"role": str(item.get("role", "unknown")), "text": str(text)})
    if not transcript and artifact.get("transcript"):
        transcript = [{"role": "transcript", "text": str(artifact["transcript"])}]
    session.transcript = transcript
    if session.status != "completed":
        session.status = "ended_without_registration"
    db.add(session)
    db.commit()
