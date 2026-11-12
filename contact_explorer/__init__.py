"""Contact Explorer — Offline, Privacy-First Contact Management System.

Enterprise-grade contact exploration, multi-field search, local deduplication,
and import/export suite with a Tkinter desktop frontend and headless HTTP REST API.
"""

from __future__ import annotations

from .models import (
    Contact,
    ContactDraft,
    DeletedContact,
    EmailAddress,
    Event,
    Folder,
    PhoneNumber,
    SmartGroup,
    Tag,
)
from .service import ContactService

__version__ = "1.0.0"
__author__ = "Contact Explorer Core Team"
__license__ = "MIT"

__all__ = [
    "Contact",
    "ContactDraft",
    "ContactService",
    "DeletedContact",
    "EmailAddress",
    "Event",
    "Folder",
    "PhoneNumber",
    "SmartGroup",
    "Tag",
    "__version__",
]
