import pytest

pytestmark = pytest.mark.anyio


async def test_create_and_retrieve_patient(client, patient_payload):
    patient_payload["date_of_birth"] = "04/12/1988"
    created = await client.post("/patients", json=patient_payload)
    assert created.status_code == 201
    body = created.json()
    assert body["error"] is None
    assert body["data"]["phone_number"] == "5125550199"
    assert body["data"]["state"] == "TX"
    assert body["data"]["preferred_language"] == "English"
    assert body["data"]["date_of_birth"] == "1988-04-12"
    assert body["data"]["created_at"].endswith("Z")

    retrieved = await client.get(f"/patients/{body['data']['patient_id']}")
    assert retrieved.status_code == 200
    assert retrieved.json()["data"]["last_name"] == "O'Neil-Smith"


async def test_list_filters_and_paginates(client, patient_payload):
    await client.post("/patients", json=patient_payload)
    other = {**patient_payload, "first_name": "Alex", "last_name": "Jones", "phone_number": "2025550114"}
    await client.post("/patients", json=other)

    result = await client.get("/patients", params={"last_name": "o'neil-smith", "limit": 1})
    assert result.status_code == 200
    assert result.json()["data"]["total"] == 1
    assert result.json()["data"]["items"][0]["first_name"] == "Jane"

    by_phone = await client.get("/patients", params={"phone_number": "+1 202-555-0114"})
    assert by_phone.json()["data"]["items"][0]["first_name"] == "Alex"


async def test_partial_update_preserves_other_fields(client, patient_payload):
    patient_id = (await client.post("/patients", json=patient_payload)).json()["data"]["patient_id"]
    response = await client.put(f"/patients/{patient_id}", json={"city": "Dallas"})
    assert response.status_code == 200
    assert response.json()["data"]["city"] == "Dallas"
    assert response.json()["data"]["first_name"] == "Jane"


async def test_update_revalidates_required_fields(client, patient_payload):
    patient_id = (await client.post("/patients", json=patient_payload)).json()["data"]["patient_id"]
    response = await client.put(f"/patients/{patient_id}", json={"first_name": None})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_soft_delete_hides_record(client, patient_payload):
    patient_id = (await client.post("/patients", json=patient_payload)).json()["data"]["patient_id"]
    deleted = await client.delete(f"/patients/{patient_id}")
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted_at"]
    assert (await client.get(f"/patients/{patient_id}")).status_code == 404
    assert (await client.get("/patients")).json()["data"]["total"] == 0


async def test_validation_errors_use_envelope(client, patient_payload):
    patient_payload["date_of_birth"] = "2999-01-01"
    patient_payload["phone_number"] = "123"
    response = await client.post("/patients", json=patient_payload)
    assert response.status_code == 422
    assert response.json()["data"] is None
    assert response.json()["error"]["code"] == "validation_error"
    assert len(response.json()["error"]["details"]) == 2


async def test_invalid_filter_uses_envelope(client):
    response = await client.get("/patients?phone_number=123")
    assert response.status_code == 422
    assert response.json()["data"] is None


async def test_not_found_uses_envelope(client):
    response = await client.get("/patients/not-a-real-id")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "patient_not_found"


async def test_health_and_dashboard(client):
    assert (await client.get("/health")).json()["data"]["status"] == "healthy"
    dashboard = await client.get("/")
    assert dashboard.status_code == 200
    assert "Patient registrations" in dashboard.text
