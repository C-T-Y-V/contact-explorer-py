"""Domain models shared by the Python backend and the Tkinter frontend."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid4()}"


@dataclass
class PhoneNumber:
    number: str
    label: str = "Mobile"
    id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "label": self.label, "number": self.number}


@dataclass
class EmailAddress:
    email: str
    label: str = "Home"
    id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "label": self.label, "email": self.email}


@dataclass
class ContactDraft:
    name: str
    phones: list[PhoneNumber] = field(default_factory=list)
    emails: list[EmailAddress] = field(default_factory=list)
    company: str = ""
    address: str = ""
    note: str = ""
    groups: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    is_favorite: bool = False
    photo_uri: str | None = None

    @property
    def phone(self) -> str:
        return self.phones[0].number if self.phones else ""

    @property
    def email(self) -> str:
        return self.emails[0].email if self.emails else ""


@dataclass
class Contact:
    id: str
    name: str
    phones: list[PhoneNumber] = field(default_factory=list)
    emails: list[EmailAddress] = field(default_factory=list)
    company: str = ""
    address: str = ""
    note: str = ""
    created_at: int = 0
    updated_at: int = 0
    times_contacted: int = 0
    is_favorite: bool = False
    groups: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    photo_uri: str | None = None

    @property
    def primary_phone(self) -> str:
        return self.phones[0].number if self.phones else ""

    @property
    def primary_email(self) -> str:
        return self.emails[0].email if self.emails else ""

    @property
    def last_modified(self) -> int:
        return self.updated_at

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["phones"] = [phone.to_dict() for phone in self.phones]
        data["emails"] = [email.to_dict() for email in self.emails]
        data["phone"] = self.primary_phone
        data["email"] = self.primary_email
        data["notes"] = self.note
        data["folder_ids"] = []
        return data


@dataclass
class Folder:
    id: str
    name: str
    parent_folder_id: str | None = None
    created_at: int = 0
    contact_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "parent_folder_id": self.parent_folder_id,
            "created_at": self.created_at,
            "contact_count": self.contact_count,
        }


@dataclass
class Tag:
    id: str
    name: str
    contact_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "contact_count": self.contact_count}


@dataclass
class DeletedContact:
    contact_id: str
    name: str
    deleted_at: int
    snapshot: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "contact_id": self.contact_id,
            "name": self.name,
            "deleted_at": self.deleted_at,
            "snapshot": self.snapshot,
        }


@dataclass
class Event:
    id: int
    contact_id: str | None
    contact_name: str
    action: str
    details: str
    occurred_at: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "contact_id": self.contact_id,
            "contact_name": self.contact_name,
            "action": self.action,
            "details": self.details,
            "occurred_at": self.occurred_at,
        }


@dataclass
class SmartGroup:
    id: str
    name: str
    field: str
    value: str
    created_at: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "field": self.field,
            "value": self.value,
            "created_at": self.created_at,
        }
