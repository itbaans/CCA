import json

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models import CallSession, Patient

pytestmark = pytest.mark.anyio


def tool_payload(name, arguments, *, call_id="call-123", tool_id="tool-123"):
    return {
        "message": {
            "type": "tool-calls",
            "call": {"id": call_id, "customer": {"number": "+15125550199"}},
            "toolCallList": [{"id": tool_id, "name": name, "arguments": arguments}],
        }
    }


def registration(**overrides):
    data = {
        "first_name": "Jane",
        "last_name": "Doe",
        "date_of_birth": "04/12/1988",
        "sex": "Female",
        "phone_number": "5125550199",
        "email": None,
        "address_line_1": "1400 Congress Avenue",
        "address_line_2": None,
        "city": "Austin",
        "state": "TX",
        "zip_code": "78701",
        "insurance_provider": None,
        "insurance_member_id": None,
        "preferred_language": "English",
        "emergency_contact_name": None,
        "emergency_contact_phone": None,
        "confirmed": True,
        "update_existing": False,
    }
    return {**data, **overrides}


async def test_vapi_lookup_returns_not_found(client):
    response = await client.post(
        "/vapi/webhook",
        json=tool_payload("check_existing_patient", {"phone_number": "5125550199"}),
    )
    assert response.status_code == 200
    result = json.loads(response.json()["results"][0]["result"])
    assert result == {"found": False}


async def test_vapi_accepts_nested_function_tool_payload(client):
    payload = tool_payload("check_existing_patient", {"phone_number": "5125550199"})
    tool_call = payload["message"]["toolCallList"][0]
    tool_call["function"] = {
        "name": tool_call.pop("name"),
        "arguments": tool_call.pop("arguments"),
    }

    response = await client.post("/vapi/webhook", json=payload)

    assert response.status_code == 200
    result = json.loads(response.json()["results"][0]["result"])
    assert result == {"found": False}


async def test_vapi_save_creates_patient_and_is_idempotent(client):
    payload = tool_payload("save_patient_registration", registration())
    first = await client.post("/vapi/webhook", json=payload)
    result = json.loads(first.json()["results"][0]["result"])
    assert result["success"] is True
    assert result["action"] == "created"

    second = await client.post("/vapi/webhook", json=payload)
    repeated = json.loads(second.json()["results"][0]["result"])
    assert repeated["action"] == "already_saved"
    with SessionLocal() as db:
        assert len(list(db.scalars(select(Patient)))) == 1


async def test_vapi_refuses_unconfirmed_save(client):
    response = await client.post(
        "/vapi/webhook",
        json=tool_payload("save_patient_registration", registration(confirmed=False)),
    )
    result = json.loads(response.json()["results"][0]["result"])
    assert result["success"] is False
    assert "confirmation" in result["reason"]


async def test_vapi_duplicate_requires_update_consent(client):
    await client.post(
        "/vapi/webhook",
        json=tool_payload("save_patient_registration", registration(), call_id="call-first"),
    )
    duplicate = await client.post(
        "/vapi/webhook",
        json=tool_payload("save_patient_registration", registration(), call_id="call-second"),
    )
    result = json.loads(duplicate.json()["results"][0]["result"])
    assert result["duplicate"] is True

    updated = await client.post(
        "/vapi/webhook",
        json=tool_payload(
            "save_patient_registration",
            registration(update_existing=True, address_line_1="2 Main Street"),
            call_id="call-second",
        ),
    )
    update_result = json.loads(updated.json()["results"][0]["result"])
    assert update_result["action"] == "updated"
    with SessionLocal() as db:
        assert db.scalar(select(Patient)).address_line_1 == "2 Main Street"


async def test_vapi_validation_error_uses_tool_result_contract(client):
    response = await client.post(
        "/vapi/webhook",
        json=tool_payload(
            "save_patient_registration", registration(phone_number="123"), tool_id="bad-tool"
        ),
    )
    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["toolCallId"] == "bad-tool"
    assert "Validation failed" in result["error"]


async def test_end_of_call_report_stores_transcript(client):
    response = await client.post(
        "/vapi/webhook",
        json={
            "message": {
                "type": "end-of-call-report",
                "call": {"id": "call-ended", "customer": {"number": "+15125550199"}},
                "artifact": {
                    "messages": [
                        {"role": "assistant", "message": "What is your name?"},
                        {"role": "user", "message": "Jane Doe"},
                    ]
                },
            }
        },
    )
    assert response.json() == {"received": True}
    with SessionLocal() as db:
        session = db.get(CallSession, "call-ended")
        assert session.status == "ended_without_registration"
        assert session.transcript[1]["text"] == "Jane Doe"


async def test_vapi_rejects_invalid_webhook_secret(client):
    response = await client.post(
        "/vapi/webhook", json={"message": {"type": "status-update"}},
        headers={"X-Vapi-Secret": "wrong"},
    )
    assert response.status_code == 401
