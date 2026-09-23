import os

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///./data/test.db"
os.environ["VAPI_WEBHOOK_SECRET"] = "test-secret"

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Vapi-Secret": "test-secret"},
    ) as test_client:
        yield test_client


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def patient_payload():
    return {
        "first_name": "Jane",
        "last_name": "O'Neil-Smith",
        "date_of_birth": "1988-04-12",
        "sex": "Female",
        "phone_number": "(512) 555-0199",
        "email": "jane@example.com",
        "address_line_1": "1400 Congress Avenue",
        "city": "Austin",
        "state": "tx",
        "zip_code": "78701",
    }
