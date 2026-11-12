"""Shared pytest fixtures for Contact Explorer unit and integration tests."""

from __future__ import annotations

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from contact_explorer.models import ContactDraft, EmailAddress, PhoneNumber
from contact_explorer.service import ContactService


@pytest.fixture
def temp_db_path() -> Generator[Path, None, None]:
    """Provides an isolated, clean SQLite database path and cleans up temporary files."""
    handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    handle.close()
    db_path = Path(handle.name)

    yield db_path

    for suffix in ("", "-wal", "-shm"):
        db_path.with_name(db_path.name + suffix).unlink(missing_ok=True)


@pytest.fixture
def service(temp_db_path: Path) -> Generator[ContactService, None, None]:
    """Provides an initialized ContactService using an isolated temporary database."""
    svc = ContactService(temp_db_path)
    yield svc
    svc.close()


@pytest.fixture
def sample_draft() -> ContactDraft:
    """Returns a rich contact draft with multiple attributes."""
    return ContactDraft(
        name="Aditi Rao",
        phones=[
            PhoneNumber("+91 98765 00001", "Mobile"),
            PhoneNumber("+91 11 2345 6789", "Work"),
        ],
        emails=[
            EmailAddress("aditi.rao@enterprisecorp.com", "Work"),
            EmailAddress("aditi@personal.net", "Personal"),
        ],
        company="Enterprise Corp",
        address="Cyber City, Gurugram, Haryana",
        note="Principal Security Architect",
        groups=["Work", "Security"],
        tags=["vip", "architect"],
        is_favorite=True,
    )
