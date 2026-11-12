"""Unit tests for Contact Explorer domain models."""

from __future__ import annotations

from contact_explorer.models import (
    Contact,
    ContactDraft,
    DeletedContact,
    EmailAddress,
    Event,
    Folder,
    PhoneNumber,
    SmartGroup,
    Tag,
    new_id,
    now_ms,
)


def test_phone_number_serialization() -> None:
    phone = PhoneNumber(number="+91 99999 88888", label="Work", id=42)
    data = phone.to_dict()
    assert data == {"id": 42, "label": "Work", "number": "+91 99999 88888"}


def test_email_address_serialization() -> None:
    email = EmailAddress(email="dev@example.org", label="Work", id=7)
    data = email.to_dict()
    assert data == {"id": 7, "label": "Work", "email": "dev@example.org"}


def test_contact_draft_properties() -> None:
    empty_draft = ContactDraft(name="Test User")
    assert empty_draft.phone == ""
    assert empty_draft.email == ""

    rich_draft = ContactDraft(
        name="Test User",
        phones=[PhoneNumber("12345"), PhoneNumber("67890")],
        emails=[EmailAddress("one@example.com"), EmailAddress("two@example.com")],
    )
    assert rich_draft.phone == "12345"
    assert rich_draft.email == "one@example.com"


def test_contact_model_properties_and_serialization() -> None:
    cid = new_id("cnt-")
    now = now_ms()
    contact = Contact(
        id=cid,
        name="Vikram Seth",
        phones=[PhoneNumber("+91 91234 56789", "Mobile")],
        emails=[EmailAddress("vikram@seth.in", "Home")],
        company="Global Media",
        address="New Delhi, India",
        note="Author & Journalist",
        created_at=now,
        updated_at=now,
        times_contacted=3,
        is_favorite=True,
        groups=["Authors", "Media"],
        tags=["vip"],
    )

    assert contact.primary_phone == "+91 91234 56789"
    assert contact.primary_email == "vikram@seth.in"
    assert contact.last_modified == now

    data = contact.to_dict()
    assert data["id"] == cid
    assert data["name"] == "Vikram Seth"
    assert data["phone"] == "+91 91234 56789"
    assert data["email"] == "vikram@seth.in"
    assert data["company"] == "Global Media"
    assert data["is_favorite"] is True
    assert data["groups"] == ["Authors", "Media"]
    assert data["tags"] == ["vip"]


def test_folder_model_serialization() -> None:
    folder = Folder(
        id="f-1", name="Engineering", parent_folder_id=None, created_at=1000, contact_count=5
    )
    data = folder.to_dict()
    assert data == {
        "id": "f-1",
        "name": "Engineering",
        "parent_folder_id": None,
        "created_at": 1000,
        "contact_count": 5,
    }


def test_tag_model_serialization() -> None:
    tag = Tag(id="t-1", name="client", contact_count=8)
    assert tag.to_dict() == {"id": "t-1", "name": "client", "contact_count": 8}


def test_deleted_contact_and_event_serialization() -> None:
    deleted = DeletedContact(
        contact_id="c-del",
        name="Old Contact",
        deleted_at=2000,
        snapshot={"name": "Old Contact"},
    )
    assert deleted.to_dict()["contact_id"] == "c-del"

    event = Event(
        id=1,
        contact_id="c-1",
        contact_name="Alice",
        action="CREATE",
        details="Created contact",
        occurred_at=3000,
    )
    assert event.to_dict()["action"] == "CREATE"


def test_smart_group_serialization() -> None:
    smart = SmartGroup(id="sg-1", name="Acme Staff", field="company", value="Acme", created_at=4000)
    data = smart.to_dict()
    assert data["name"] == "Acme Staff"
    assert data["field"] == "company"
    assert data["value"] == "Acme"
