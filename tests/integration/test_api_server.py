"""Integration tests for the local Contact Explorer HTTP API server."""

from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from contact_explorer.api import ContactExplorerHandler
from contact_explorer.models import ContactDraft, PhoneNumber
from contact_explorer.service import ContactService


@pytest.fixture
def test_server(temp_db_path: Path):
    """Spins up a real local test server on an ephemeral OS port and shuts down cleanly."""
    service = ContactService(temp_db_path)
    handler = type(
        "TestContactExplorerHandler",
        (ContactExplorerHandler,),
        {"service": service},
    )
    # Port 0 asks the OS for an available ephemeral port
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    host, port = server.server_address

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    base_url = f"http://{host}:{port}"
    yield base_url, service

    server.shutdown()
    server.server_close()
    service.close()


def test_api_health_check(test_server) -> None:
    base_url, _ = test_server
    with urlopen(f"{base_url}/api/health") as response:
        assert response.status == 200
        data = json.loads(response.read().decode("utf-8"))
        assert data.get("ok") is True
        assert "Contact Explorer" in data.get("service", "")


def test_api_stats_and_contacts_crud(test_server) -> None:
    base_url, service = test_server

    # 1. Check initial stats
    with urlopen(f"{base_url}/api/stats") as response:
        assert response.status == 200
        stats = json.loads(response.read().decode("utf-8"))
        assert stats["contacts"] == 0

    # 2. Create contact via POST
    contact_payload = {
        "name": "Integration User",
        "phones": [{"label": "Mobile", "number": "+91 99999 00000"}],
        "emails": [{"label": "Work", "email": "integration@test.local"}],
        "company": "API Tester Corp",
        "groups": ["AutomatedTests"],
        "tags": ["ci"],
        "is_favorite": True,
    }
    req = Request(
        f"{base_url}/api/contacts",
        data=json.dumps(contact_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req) as response:
        assert response.status == 201
        created = json.loads(response.read().decode("utf-8"))
        assert created["name"] == "Integration User"
        contact_id = created["id"]

    # 3. Fetch contacts list
    with urlopen(f"{base_url}/api/contacts") as response:
        assert response.status == 200
        contacts = json.loads(response.read().decode("utf-8"))
        assert len(contacts) == 1
        assert contacts[0]["id"] == contact_id

    # 4. Search contacts
    with urlopen(f"{base_url}/api/contacts?search=company:API") as response:
        assert response.status == 200
        search_results = json.loads(response.read().decode("utf-8"))
        assert len(search_results) == 1
        assert search_results[0]["id"] == contact_id

    # 5. Soft-delete via DELETE endpoint
    del_req = Request(
        f"{base_url}/api/contacts/{contact_id}",
        method="DELETE",
    )
    with urlopen(del_req) as response:
        assert response.status == 200
        del_data = json.loads(response.read().decode("utf-8"))
        assert del_data.get("deleted") is True

    # 6. Verify moved to trash
    with urlopen(f"{base_url}/api/trash") as response:
        assert response.status == 200
        trash_list = json.loads(response.read().decode("utf-8"))
        assert len(trash_list) == 1
        assert trash_list[0]["contact_id"] == contact_id

    # 7. Restore from trash via POST /api/trash/restore
    restore_req = Request(
        f"{base_url}/api/trash/restore",
        data=json.dumps({"contact_id": contact_id}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(restore_req) as response:
        assert response.status == 200
        restored = json.loads(response.read().decode("utf-8"))
        assert restored["name"] == "Integration User"


def test_api_options_cors(test_server) -> None:
    base_url, _ = test_server
    req = Request(f"{base_url}/api/contacts", method="OPTIONS")
    with urlopen(req) as response:
        assert response.status == 204
        assert response.headers.get("Access-Control-Allow-Origin") == "*"
