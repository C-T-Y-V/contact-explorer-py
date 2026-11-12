"""Application backend: persistence, contact operations and domain workflows."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from . import intelligence, transfer
from .database import Database
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
    new_id,
    now_ms,
)


TRASH_RETENTION_MS = 30 * 24 * 60 * 60 * 1000
DEFAULT_GROUPS = ("Classmates", "Hostelmates", "Family", "Friends")


class ContactService:
    """The complete offline backend used by both UI and optional HTTP API."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db = Database(db_path)
        self._seed_default_groups()
        self.purge_old_deleted()

    @property
    def db_path(self) -> Path:
        return self.db.path

    def close(self) -> None:
        self.db.close()

    # ── Conversion helpers ──────────────────────────────────────────────

    @staticmethod
    def draft_from_payload(payload: dict[str, Any]) -> ContactDraft:
        def as_bool(value: Any) -> bool:
            if isinstance(value, str):
                return value.strip().casefold() in {"1", "true", "yes", "y", "on"}
            return bool(value)

        def phone_items() -> list[PhoneNumber]:
            raw = payload.get("phones")
            if raw is None:
                raw = [payload.get("phone", "")]
            if isinstance(raw, str):
                raw = [item.strip() for item in raw.split(";")]
            result: list[PhoneNumber] = []
            for item in raw or []:
                if isinstance(item, dict):
                    number = str(item.get("number", item.get("value", ""))).strip()
                    label = str(item.get("label", "Mobile")).strip() or "Mobile"
                else:
                    number = str(item).strip()
                    label = "Mobile"
                if number:
                    result.append(PhoneNumber(number=number, label=label))
            return result

        def email_items() -> list[EmailAddress]:
            raw = payload.get("emails")
            if raw is None:
                raw = [payload.get("email", "")]
            if isinstance(raw, str):
                raw = [item.strip() for item in raw.split(";")]
            result: list[EmailAddress] = []
            for item in raw or []:
                if isinstance(item, dict):
                    email = str(item.get("email", item.get("value", ""))).strip()
                    label = str(item.get("label", "Home")).strip() or "Home"
                else:
                    email = str(item).strip()
                    label = "Home"
                if email:
                    result.append(EmailAddress(email=email, label=label))
            return result

        groups = payload.get("groups", payload.get("categories", []))
        if not groups:
            groups = payload.get("folder_ids", [])
        tags = payload.get("tags", [])
        if isinstance(groups, str):
            groups = [item.strip() for item in groups.split(";") if item.strip()]
        if isinstance(tags, str):
            tags = [item.strip() for item in tags.split(";") if item.strip()]
        return ContactDraft(
            name=str(payload.get("name", "")).strip(),
            phones=phone_items(),
            emails=email_items(),
            company=str(payload.get("company", "")).strip(),
            address=str(payload.get("address", "")).strip(),
            note=str(payload.get("note", payload.get("notes", ""))).strip(),
            groups=[str(item).strip() for item in groups or [] if str(item).strip()],
            tags=[str(item).strip() for item in tags or [] if str(item).strip()],
            is_favorite=as_bool(payload.get("is_favorite", payload.get("isFavorite", payload.get("favorite", False)))),
            photo_uri=payload.get("photo_uri"),
        )

    @staticmethod
    def _contact_to_dict(contact: Contact, folder_ids: list[str] | None = None) -> dict[str, Any]:
        data = contact.to_dict()
        data["folder_ids"] = folder_ids or []
        data["groups"] = list(contact.groups)
        data["tags"] = list(contact.tags)
        data["is_favorite"] = contact.is_favorite
        data["isFavorite"] = contact.is_favorite
        data["notes"] = contact.note
        return data

    def _seed_default_groups(self) -> None:
        with self.db.transaction() as conn:
            count = conn.execute("SELECT COUNT(*) FROM folders").fetchone()[0]
            if count:
                return
            timestamp = now_ms()
            for name in DEFAULT_GROUPS:
                conn.execute(
                    "INSERT INTO folders(id, name, parent_folder_id, created_at) VALUES (?, ?, NULL, ?)",
                    (new_id("group-"), name, timestamp),
                )

    def _row_to_contact(self, conn: sqlite3.Connection, row: sqlite3.Row) -> Contact:
        contact_id = row["id"]
        phones = [
            PhoneNumber(number=item["number"], label=item["label"], id=item["id"])
            for item in conn.execute(
                "SELECT id, label, number FROM contact_phones WHERE contact_id = ? ORDER BY id",
                (contact_id,),
            )
        ]
        emails = [
            EmailAddress(email=item["email"], label=item["label"], id=item["id"])
            for item in conn.execute(
                "SELECT id, label, email FROM contact_emails WHERE contact_id = ? ORDER BY id",
                (contact_id,),
            )
        ]
        groups = [
            item["name"]
            for item in conn.execute(
                "SELECT f.name FROM folders f JOIN contact_groups cg ON cg.group_id = f.id "
                "WHERE cg.contact_id = ? ORDER BY f.name COLLATE NOCASE",
                (contact_id,),
            )
        ]
        tags = [
            item["name"]
            for item in conn.execute(
                "SELECT t.name FROM tags t JOIN contact_tags ct ON ct.tag_id = t.id "
                "WHERE ct.contact_id = ? ORDER BY t.name COLLATE NOCASE",
                (contact_id,),
            )
        ]
        return Contact(
            id=contact_id,
            name=row["name"],
            phones=phones,
            emails=emails,
            company=row["company"] or "",
            address=row["address"] or "",
            note=row["note"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            times_contacted=row["times_contacted"],
            is_favorite=bool(row["is_favorite"]),
            groups=groups,
            tags=tags,
            photo_uri=row["photo_uri"],
        )

    def _get_contact_locked(self, conn: sqlite3.Connection, contact_id: str) -> Contact | None:
        row = conn.execute("SELECT * FROM contacts WHERE id = ?", (str(contact_id),)).fetchone()
        return self._row_to_contact(conn, row) if row else None

    def _group_id_locked(self, conn: sqlite3.Connection, value: str, create: bool = True) -> str | None:
        value = str(value).strip()
        if not value:
            return None
        row = conn.execute("SELECT id FROM folders WHERE id = ?", (value,)).fetchone()
        if row:
            return row["id"]
        row = conn.execute("SELECT id FROM folders WHERE name = ? COLLATE NOCASE", (value,)).fetchone()
        if row:
            return row["id"]
        if not create:
            return None
        group_id = new_id("group-")
        conn.execute(
            "INSERT INTO folders(id, name, parent_folder_id, created_at) VALUES (?, ?, NULL, ?)",
            (group_id, value, now_ms()),
        )
        return group_id

    def _tag_id_locked(self, conn: sqlite3.Connection, value: str, create: bool = True) -> str | None:
        value = str(value).strip()
        if not value:
            return None
        row = conn.execute("SELECT id FROM tags WHERE id = ?", (value,)).fetchone()
        if row:
            return row["id"]
        row = conn.execute("SELECT id FROM tags WHERE name = ? COLLATE NOCASE", (value,)).fetchone()
        if row:
            return row["id"]
        if not create:
            return None
        tag_id = new_id("tag-")
        conn.execute("INSERT INTO tags(id, name) VALUES (?, ?)", (tag_id, value))
        return tag_id

    def _record_event_locked(
        self,
        conn: sqlite3.Connection,
        contact_id: str | None,
        contact_name: str,
        action: str,
        details: str,
    ) -> None:
        conn.execute(
            "INSERT INTO contact_events(contact_id, contact_name, action, details, occurred_at) VALUES (?, ?, ?, ?, ?)",
            (contact_id, contact_name, action, details, now_ms()),
        )

    def _folder_ids_locked(self, conn: sqlite3.Connection, contact_id: str) -> list[str]:
        return [
            row["group_id"]
            for row in conn.execute(
                "SELECT group_id FROM contact_groups WHERE contact_id = ? ORDER BY group_id",
                (contact_id,),
            )
        ]

    # ── Contacts ─────────────────────────────────────────────────────────

    def get_contact(self, contact_id: str) -> Contact | None:
        with self.db.lock:
            return self._get_contact_locked(self.db.connection, str(contact_id))

    def list_contacts(self) -> list[Contact]:
        with self.db.lock:
            rows = self.db.connection.execute("SELECT * FROM contacts ORDER BY name COLLATE NOCASE").fetchall()
            return [self._row_to_contact(self.db.connection, row) for row in rows]

    def search_contacts(self, query: str, contacts: Iterable[Contact] | None = None) -> list[Contact]:
        return intelligence.search_contacts(contacts if contacts is not None else self.list_contacts(), query)

    def _save_contact_locked(
        self,
        conn: sqlite3.Connection,
        draft: ContactDraft,
        contact_id: str | None = None,
        record_event: bool = True,
        event_action: str = "UPDATED",
    ) -> str:
        if not draft.name.strip():
            raise ValueError("A contact name is required.")
        if contact_id is None:
            contact_id = new_id("contact-")
            timestamp = now_ms()
            conn.execute(
                "INSERT INTO contacts(id, name, company, address, note, photo_uri, is_favorite, created_at, updated_at, times_contacted) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
                (
                    contact_id,
                    draft.name.strip(),
                    draft.company.strip(),
                    draft.address.strip(),
                    draft.note.strip(),
                    draft.photo_uri,
                    int(draft.is_favorite),
                    timestamp,
                    timestamp,
                ),
            )
            event_action = "CREATED"
        else:
            existing = conn.execute("SELECT id FROM contacts WHERE id = ?", (str(contact_id),)).fetchone()
            if not existing:
                contact_id = new_id("contact-")
                timestamp = now_ms()
                conn.execute(
                    "INSERT INTO contacts(id, name, company, address, note, photo_uri, is_favorite, created_at, updated_at, times_contacted) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
                    (
                        contact_id,
                        draft.name.strip(),
                        draft.company.strip(),
                        draft.address.strip(),
                        draft.note.strip(),
                        draft.photo_uri,
                        int(draft.is_favorite),
                        timestamp,
                        timestamp,
                    ),
                )
                event_action = "CREATED"
            else:
                conn.execute(
                    "UPDATE contacts SET name = ?, company = ?, address = ?, note = ?, photo_uri = ?, "
                    "is_favorite = ?, updated_at = ? WHERE id = ?",
                    (
                        draft.name.strip(),
                        draft.company.strip(),
                        draft.address.strip(),
                        draft.note.strip(),
                        draft.photo_uri,
                        int(draft.is_favorite),
                        now_ms(),
                        str(contact_id),
                    ),
                )

        conn.execute("DELETE FROM contact_phones WHERE contact_id = ?", (contact_id,))
        conn.execute("DELETE FROM contact_emails WHERE contact_id = ?", (contact_id,))
        conn.execute("DELETE FROM contact_groups WHERE contact_id = ?", (contact_id,))
        conn.execute("DELETE FROM contact_tags WHERE contact_id = ?", (contact_id,))
        seen_phones: set[str] = set()
        for phone in draft.phones:
            number = phone.number.strip()
            if not number or number in seen_phones:
                continue
            seen_phones.add(number)
            conn.execute(
                "INSERT INTO contact_phones(contact_id, label, number) VALUES (?, ?, ?)",
                (contact_id, phone.label.strip() or "Mobile", number),
            )
        seen_emails: set[str] = set()
        for email in draft.emails:
            address = email.email.strip()
            if not address or address.casefold() in seen_emails:
                continue
            seen_emails.add(address.casefold())
            conn.execute(
                "INSERT INTO contact_emails(contact_id, label, email) VALUES (?, ?, ?)",
                (contact_id, email.label.strip() or "Home", address),
            )
        for value in draft.groups:
            group_id = self._group_id_locked(conn, value)
            if group_id:
                conn.execute("INSERT OR IGNORE INTO contact_groups(contact_id, group_id) VALUES (?, ?)", (contact_id, group_id))
        for value in draft.tags:
            tag_id = self._tag_id_locked(conn, value)
            if tag_id:
                conn.execute("INSERT OR IGNORE INTO contact_tags(contact_id, tag_id) VALUES (?, ?)", (contact_id, tag_id))
        if record_event:
            self._record_event_locked(conn, contact_id, draft.name.strip(), event_action, "Contact details saved.")
        return contact_id

    def save_contact(self, contact_id: str | None, draft: ContactDraft | dict[str, Any]) -> Contact:
        if isinstance(draft, dict):
            draft = self.draft_from_payload(draft)
        with self.db.transaction() as conn:
            saved_id = self._save_contact_locked(conn, draft, contact_id)
            contact = self._get_contact_locked(conn, saved_id)
            assert contact is not None
            return contact

    def delete_contacts(self, contact_ids: Iterable[str], move_to_trash: bool = True) -> int:
        ids = list(dict.fromkeys(str(item) for item in contact_ids))
        deleted = 0
        with self.db.transaction() as conn:
            for contact_id in ids:
                contact = self._get_contact_locked(conn, contact_id)
                if not contact:
                    continue
                if move_to_trash:
                    snapshot = self._contact_to_dict(contact, self._folder_ids_locked(conn, contact_id))
                    conn.execute(
                        "INSERT OR REPLACE INTO deleted_contacts(contact_id, name, deleted_at, snapshot_json) VALUES (?, ?, ?, ?)",
                        (contact_id, contact.name, now_ms(), json.dumps(snapshot, ensure_ascii=False)),
                    )
                conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
                self._record_event_locked(
                    conn,
                    contact_id,
                    contact.name,
                    "DELETED" if move_to_trash else "PURGED",
                    "Moved to Recycle Bin." if move_to_trash else "Removed permanently.",
                )
                deleted += 1
        return deleted

    def toggle_favorite(self, contact_id: str) -> bool:
        with self.db.transaction() as conn:
            row = conn.execute("SELECT name, is_favorite FROM contacts WHERE id = ?", (str(contact_id),)).fetchone()
            if not row:
                raise ValueError("Contact not found")
            value = not bool(row["is_favorite"])
            conn.execute("UPDATE contacts SET is_favorite = ?, updated_at = ? WHERE id = ?", (int(value), now_ms(), str(contact_id)))
            self._record_event_locked(conn, str(contact_id), row["name"], "FAVORITE", "Favorite status changed.")
            return value

    def record_viewed(self, contact_id: str) -> None:
        with self.db.transaction() as conn:
            row = conn.execute("SELECT name FROM contacts WHERE id = ?", (str(contact_id),)).fetchone()
            if not row:
                return
            timestamp = now_ms()
            conn.execute(
                "INSERT INTO recent_contacts(contact_id, viewed_at) VALUES (?, ?) "
                "ON CONFLICT(contact_id) DO UPDATE SET viewed_at = excluded.viewed_at",
                (str(contact_id), timestamp),
            )
            self._record_event_locked(conn, str(contact_id), row["name"], "OPENED", "Contact viewed.")

    def record_call(self, contact_id: str) -> None:
        with self.db.transaction() as conn:
            row = conn.execute("SELECT name FROM contacts WHERE id = ?", (str(contact_id),)).fetchone()
            if not row:
                return
            timestamp = now_ms()
            conn.execute(
                "UPDATE contacts SET times_contacted = times_contacted + 1, updated_at = ? WHERE id = ?",
                (timestamp, str(contact_id)),
            )
            conn.execute(
                "INSERT INTO recent_contacts(contact_id, viewed_at) VALUES (?, ?) "
                "ON CONFLICT(contact_id) DO UPDATE SET viewed_at = excluded.viewed_at",
                (str(contact_id), timestamp),
            )
            self._record_event_locked(conn, str(contact_id), row["name"], "CALLED", "Call action started.")

    def record_share(self, contact_ids: Iterable[str]) -> None:
        with self.db.transaction() as conn:
            for contact_id in contact_ids:
                row = conn.execute("SELECT name FROM contacts WHERE id = ?", (str(contact_id),)).fetchone()
                if row:
                    self._record_event_locked(conn, str(contact_id), row["name"], "SHARED", "Contact shared.")

    # ── Groups and tags ─────────────────────────────────────────────────

    def list_groups(self) -> list[Folder]:
        with self.db.lock:
            rows = self.db.connection.execute(
                "SELECT f.id, f.name, f.parent_folder_id, f.created_at, "
                "COUNT(cg.contact_id) AS contact_count "
                "FROM folders f LEFT JOIN contact_groups cg ON cg.group_id = f.id "
                "GROUP BY f.id ORDER BY f.parent_folder_id IS NOT NULL, f.name COLLATE NOCASE"
            ).fetchall()
            return [
                Folder(
                    id=row["id"],
                    name=row["name"],
                    parent_folder_id=row["parent_folder_id"],
                    created_at=row["created_at"],
                    contact_count=row["contact_count"],
                )
                for row in rows
            ]

    def get_group(self, group_id: str) -> Folder | None:
        return next((group for group in self.list_groups() if group.id == str(group_id)), None)

    def create_group(self, name: str, parent_folder_id: str | None = None) -> Folder:
        clean = name.strip()
        if not clean:
            raise ValueError("Group name is required")
        with self.db.transaction() as conn:
            if parent_folder_id and not conn.execute("SELECT 1 FROM folders WHERE id = ?", (parent_folder_id,)).fetchone():
                parent_folder_id = None
            existing = conn.execute("SELECT id FROM folders WHERE name = ? COLLATE NOCASE", (clean,)).fetchone()
            if existing:
                raise ValueError("A group with this name already exists")
            group_id = new_id("group-")
            timestamp = now_ms()
            conn.execute(
                "INSERT INTO folders(id, name, parent_folder_id, created_at) VALUES (?, ?, ?, ?)",
                (group_id, clean, parent_folder_id, timestamp),
            )
            self._record_event_locked(conn, None, clean, "GROUP_CREATED", "Contact group created.")
            return Folder(group_id, clean, parent_folder_id, timestamp, 0)

    def rename_group(self, group_id: str, name: str) -> Folder:
        clean = name.strip()
        if not clean:
            raise ValueError("Group name is required")
        with self.db.transaction() as conn:
            current = conn.execute("SELECT * FROM folders WHERE id = ?", (str(group_id),)).fetchone()
            if not current:
                raise ValueError("Group not found")
            duplicate = conn.execute(
                "SELECT id FROM folders WHERE name = ? COLLATE NOCASE AND id != ?",
                (clean, str(group_id)),
            ).fetchone()
            if duplicate:
                raise ValueError("A group with this name already exists")
            conn.execute("UPDATE folders SET name = ? WHERE id = ?", (clean, str(group_id)))
            self._record_event_locked(conn, None, clean, "GROUP_RENAMED", "Contact group renamed.")
            row = conn.execute(
                "SELECT f.id, f.name, f.parent_folder_id, f.created_at, "
                "COUNT(cg.contact_id) AS contact_count FROM folders f "
                "LEFT JOIN contact_groups cg ON cg.group_id = f.id WHERE f.id = ? GROUP BY f.id",
                (str(group_id),),
            ).fetchone()
            return Folder(row["id"], row["name"], row["parent_folder_id"], row["created_at"], row["contact_count"])

    def delete_group(self, group_id: str) -> bool:
        with self.db.transaction() as conn:
            row = conn.execute("SELECT name FROM folders WHERE id = ?", (str(group_id),)).fetchone()
            if not row:
                return False
            conn.execute("UPDATE folders SET parent_folder_id = NULL WHERE parent_folder_id = ?", (str(group_id),))
            conn.execute("DELETE FROM folders WHERE id = ?", (str(group_id),))
            self._record_event_locked(conn, None, row["name"], "GROUP_DELETED", "Contact group deleted.")
            return True

    def merge_groups(self, target_group_id: str, source_group_ids: Iterable[str]) -> int:
        sources = [str(item) for item in source_group_ids if str(item) != str(target_group_id)]
        with self.db.transaction() as conn:
            target = conn.execute("SELECT name FROM folders WHERE id = ?", (str(target_group_id),)).fetchone()
            if not target:
                raise ValueError("Target group not found")
            moved = 0
            for source_id in sources:
                rows = conn.execute("SELECT contact_id FROM contact_groups WHERE group_id = ?", (source_id,)).fetchall()
                for row in rows:
                    conn.execute(
                        "INSERT OR IGNORE INTO contact_groups(contact_id, group_id) VALUES (?, ?)",
                        (row["contact_id"], str(target_group_id)),
                    )
                    moved += 1
                conn.execute("DELETE FROM folders WHERE id = ?", (source_id,))
            if sources:
                self._record_event_locked(conn, None, target["name"], "MERGED_GROUPS", f"Merged {len(sources)} group(s).")
            return moved

    def contacts_in_group(self, group_id: str) -> list[Contact]:
        with self.db.lock:
            rows = self.db.connection.execute(
                "SELECT c.* FROM contacts c JOIN contact_groups cg ON cg.contact_id = c.id "
                "WHERE cg.group_id = ? ORDER BY c.name COLLATE NOCASE",
                (str(group_id),),
            ).fetchall()
            return [self._row_to_contact(self.db.connection, row) for row in rows]

    def ungrouped_contacts(self) -> list[Contact]:
        with self.db.lock:
            rows = self.db.connection.execute(
                "SELECT c.* FROM contacts c LEFT JOIN contact_groups cg ON cg.contact_id = c.id "
                "WHERE cg.contact_id IS NULL ORDER BY c.name COLLATE NOCASE"
            ).fetchall()
            return [self._row_to_contact(self.db.connection, row) for row in rows]

    def assign_groups(self, contact_ids: Iterable[str], group_ids: Iterable[str], replace: bool = True) -> None:
        contact_ids = [str(item) for item in dict.fromkeys(contact_ids)]
        group_ids = [str(item) for item in dict.fromkeys(group_ids)]
        with self.db.transaction() as conn:
            valid_groups = {
                row["id"]
                for row in conn.execute(
                    f"SELECT id FROM folders WHERE id IN ({','.join('?' for _ in group_ids)})", group_ids
                )
            } if group_ids else set()
            for contact_id in contact_ids:
                if replace:
                    conn.execute("DELETE FROM contact_groups WHERE contact_id = ?", (contact_id,))
                for group_id in valid_groups:
                    conn.execute("INSERT OR IGNORE INTO contact_groups(contact_id, group_id) VALUES (?, ?)", (contact_id, group_id))
            if contact_ids:
                self._record_event_locked(conn, None, "Contacts", "GROUPED", f"Updated groups for {len(contact_ids)} contact(s).")

    def list_tags(self) -> list[Tag]:
        with self.db.lock:
            rows = self.db.connection.execute(
                "SELECT t.id, t.name, COUNT(ct.contact_id) AS contact_count "
                "FROM tags t LEFT JOIN contact_tags ct ON ct.tag_id = t.id "
                "GROUP BY t.id ORDER BY t.name COLLATE NOCASE"
            ).fetchall()
            return [Tag(row["id"], row["name"], row["contact_count"]) for row in rows]

    def create_tag(self, name: str) -> Tag:
        clean = name.strip()
        if not clean:
            raise ValueError("Tag name is required")
        with self.db.transaction() as conn:
            existing = conn.execute("SELECT id, name FROM tags WHERE name = ? COLLATE NOCASE", (clean,)).fetchone()
            if existing:
                return Tag(existing["id"], existing["name"], 0)
            tag_id = new_id("tag-")
            conn.execute("INSERT INTO tags(id, name) VALUES (?, ?)", (tag_id, clean))
            self._record_event_locked(conn, None, clean, "TAG_CREATED", "Contact tag created.")
            return Tag(tag_id, clean, 0)

    def delete_tag(self, tag_id: str) -> bool:
        with self.db.transaction() as conn:
            row = conn.execute("SELECT name FROM tags WHERE id = ?", (str(tag_id),)).fetchone()
            if not row:
                return False
            conn.execute("DELETE FROM tags WHERE id = ?", (str(tag_id),))
            self._record_event_locked(conn, None, row["name"], "TAG_DELETED", "Contact tag deleted.")
            return True

    def assign_tags(self, contact_ids: Iterable[str], tag_ids: Iterable[str], replace: bool = False) -> None:
        contact_ids = [str(item) for item in dict.fromkeys(contact_ids)]
        tag_ids = [str(item) for item in dict.fromkeys(tag_ids)]
        with self.db.transaction() as conn:
            if replace:
                for contact_id in contact_ids:
                    conn.execute("DELETE FROM contact_tags WHERE contact_id = ?", (contact_id,))
            for contact_id in contact_ids:
                for tag_id in tag_ids:
                    if conn.execute("SELECT 1 FROM tags WHERE id = ?", (tag_id,)).fetchone():
                        conn.execute("INSERT OR IGNORE INTO contact_tags(contact_id, tag_id) VALUES (?, ?)", (contact_id, tag_id))
            if contact_ids:
                self._record_event_locked(conn, None, "Contacts", "TAGGED", f"Updated tags for {len(contact_ids)} contact(s).")

    def create_tag_and_assign(self, name: str, contact_ids: Iterable[str]) -> Tag:
        tag = self.create_tag(name)
        self.assign_tags(contact_ids, [tag.id])
        return tag

    def auto_tag_contacts(self) -> int:
        contacts = self.list_contacts()
        assigned = 0
        with self.db.transaction() as conn:
            for contact in contacts:
                for name in sorted(intelligence.suggested_tags(contact)):
                    tag_id = self._tag_id_locked(conn, name)
                    if tag_id:
                        before = conn.total_changes
                        conn.execute("INSERT OR IGNORE INTO contact_tags(contact_id, tag_id) VALUES (?, ?)", (contact.id, tag_id))
                        if conn.total_changes > before:
                            assigned += 1
            self._record_event_locked(conn, None, "Contacts", "AUTO_TAGGED", "Offline rules suggested tags for contacts.")
        return assigned

    # ── Recycle bin and duplicates ──────────────────────────────────────

    def purge_old_deleted(self) -> int:
        cutoff = now_ms() - TRASH_RETENTION_MS
        with self.db.transaction() as conn:
            cursor = conn.execute("DELETE FROM deleted_contacts WHERE deleted_at < ?", (cutoff,))
            return cursor.rowcount

    def list_deleted(self) -> list[DeletedContact]:
        self.purge_old_deleted()
        with self.db.lock:
            rows = self.db.connection.execute(
                "SELECT contact_id, name, deleted_at, snapshot_json FROM deleted_contacts ORDER BY deleted_at DESC"
            ).fetchall()
            result: list[DeletedContact] = []
            for row in rows:
                try:
                    snapshot = json.loads(row["snapshot_json"])
                except json.JSONDecodeError:
                    snapshot = {"name": row["name"]}
                result.append(DeletedContact(row["contact_id"], row["name"], row["deleted_at"], snapshot))
            return result

    def restore_deleted(self, contact_id: str) -> Contact:
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT contact_id, name, snapshot_json FROM deleted_contacts WHERE contact_id = ?",
                (str(contact_id),),
            ).fetchone()
            if not row:
                raise ValueError("Deleted contact not found")
            try:
                snapshot = json.loads(row["snapshot_json"])
            except json.JSONDecodeError as exc:
                raise ValueError("The saved contact copy is corrupted") from exc
            draft = self.draft_from_payload(snapshot)
            restored_id = self._save_contact_locked(conn, draft, None, record_event=False, event_action="RESTORED")
            conn.execute("DELETE FROM deleted_contacts WHERE contact_id = ?", (str(contact_id),))
            self._record_event_locked(conn, restored_id, draft.name, "RESTORED", "Restored from Recycle Bin.")
            restored = self._get_contact_locked(conn, restored_id)
            assert restored is not None
            return restored

    def permanently_delete(self, contact_id: str) -> bool:
        with self.db.transaction() as conn:
            row = conn.execute("SELECT name FROM deleted_contacts WHERE contact_id = ?", (str(contact_id),)).fetchone()
            if not row:
                return False
            conn.execute("DELETE FROM deleted_contacts WHERE contact_id = ?", (str(contact_id),))
            self._record_event_locked(conn, str(contact_id), row["name"], "PURGED", "Removed permanently from Recycle Bin.")
            return True

    def duplicate_groups(self) -> list[intelligence.DuplicateGroup]:
        return intelligence.find_duplicate_groups(self.list_contacts())

    def merge_contacts(self, target_id: str, source_ids: Iterable[str]) -> Contact:
        source_ids = [str(item) for item in dict.fromkeys(source_ids) if str(item) != str(target_id)]
        with self.db.transaction() as conn:
            target = self._get_contact_locked(conn, str(target_id))
            sources = [self._get_contact_locked(conn, item) for item in source_ids]
            sources = [item for item in sources if item is not None]
            if not target or not sources:
                raise ValueError("Choose a target and at least one source contact")

            phone_values: list[PhoneNumber] = []
            phone_keys: set[str] = set()
            email_values: list[EmailAddress] = []
            email_keys: set[str] = set()
            groups: list[str] = []
            tags: list[str] = []
            for contact in [target, *sources]:
                for phone in contact.phones:
                    key = intelligence.normalize_phone(phone.number) or phone.number.casefold()
                    if key and key not in phone_keys:
                        phone_keys.add(key)
                        phone_values.append(PhoneNumber(phone.number, phone.label))
                for email in contact.emails:
                    key = email.email.casefold()
                    if key and key not in email_keys:
                        email_keys.add(key)
                        email_values.append(EmailAddress(email.email, email.label))
                for group in contact.groups:
                    if group not in groups:
                        groups.append(group)
                for tag in contact.tags:
                    if tag not in tags:
                        tags.append(tag)
            draft = ContactDraft(
                name=target.name or sources[0].name,
                phones=phone_values,
                emails=email_values,
                company=target.company or next((item.company for item in sources if item.company), ""),
                address=max((target.address, *(item.address for item in sources)), key=len),
                note="\n".join(dict.fromkeys(item.note for item in [target, *sources] if item.note)),
                groups=groups,
                tags=tags,
                is_favorite=any(item.is_favorite for item in [target, *sources]),
                photo_uri=target.photo_uri or next((item.photo_uri for item in sources if item.photo_uri), None),
            )
            self._save_contact_locked(conn, draft, target.id, record_event=False)
            for source in sources:
                conn.execute("DELETE FROM contacts WHERE id = ?", (source.id,))
            self._record_event_locked(conn, target.id, target.name, "MERGED", f"Merged {len(sources)} duplicate contact(s).")
            merged = self._get_contact_locked(conn, target.id)
            assert merged is not None
            return merged

    # ── Recent, timeline, smart groups and insights ─────────────────────

    def favorite_contacts(self) -> list[Contact]:
        with self.db.lock:
            rows = self.db.connection.execute("SELECT * FROM contacts WHERE is_favorite = 1 ORDER BY name COLLATE NOCASE").fetchall()
            return [self._row_to_contact(self.db.connection, row) for row in rows]

    def recent_contacts(self, limit: int = 100) -> list[Contact]:
        with self.db.lock:
            rows = self.db.connection.execute(
                "SELECT c.* FROM contacts c JOIN recent_contacts r ON r.contact_id = c.id "
                "ORDER BY r.viewed_at DESC LIMIT ?",
                (max(1, int(limit)),),
            ).fetchall()
            return [self._row_to_contact(self.db.connection, row) for row in rows]

    def list_events(self, limit: int = 500) -> list[Event]:
        with self.db.lock:
            rows = self.db.connection.execute(
                "SELECT id, contact_id, contact_name, action, details, occurred_at "
                "FROM contact_events ORDER BY occurred_at DESC LIMIT ?",
                (max(1, int(limit)),),
            ).fetchall()
            return [Event(row["id"], row["contact_id"], row["contact_name"], row["action"], row["details"], row["occurred_at"]) for row in rows]

    def keyword_clusters(self) -> list[intelligence.KeywordCluster]:
        return intelligence.detect_keyword_clusters(self.list_contacts())

    def list_smart_groups(self) -> list[SmartGroup]:
        with self.db.lock:
            rows = self.db.connection.execute(
                "SELECT id, name, field, value, created_at FROM smart_groups ORDER BY name COLLATE NOCASE"
            ).fetchall()
            return [SmartGroup(row["id"], row["name"], row["field"], row["value"], row["created_at"]) for row in rows]

    def create_smart_group(self, name: str, field: str, value: str) -> SmartGroup:
        if not name.strip() or not value.strip():
            raise ValueError("Smart group name and match value are required")
        with self.db.transaction() as conn:
            item = SmartGroup(new_id("smart-"), name.strip(), field.strip().casefold(), value.strip(), now_ms())
            conn.execute(
                "INSERT INTO smart_groups(id, name, field, value, created_at) VALUES (?, ?, ?, ?, ?)",
                (item.id, item.name, item.field, item.value, item.created_at),
            )
            self._record_event_locked(conn, None, item.name, "SMART_GROUP_CREATED", f"Matches {item.field}: {item.value}")
            return item

    def delete_smart_group(self, smart_group_id: str) -> bool:
        with self.db.transaction() as conn:
            cursor = conn.execute("DELETE FROM smart_groups WHERE id = ?", (str(smart_group_id),))
            return cursor.rowcount > 0

    def smart_group_contacts(self, smart_group: SmartGroup) -> list[Contact]:
        return [contact for contact in self.list_contacts() if intelligence.matches_smart_group(contact, smart_group.field, smart_group.value)]

    def relationships(self) -> list[tuple[str, list[str]]]:
        result: list[tuple[str, list[str]]] = []
        for group in self.list_groups():
            names = [contact.name for contact in self.contacts_in_group(group.id)]
            result.append((f"Group · {group.name}", names))
        for tag in self.list_tags():
            with self.db.lock:
                rows = self.db.connection.execute(
                    "SELECT c.name FROM contacts c JOIN contact_tags ct ON ct.contact_id = c.id WHERE ct.tag_id = ? ORDER BY c.name COLLATE NOCASE",
                    (tag.id,),
                ).fetchall()
            names = [row["name"] for row in rows]
            if len(names) > 1:
                result.append((f"Tag · {tag.name}", names))
        return result

    def stats(self) -> dict[str, int]:
        with self.db.lock:
            conn = self.db.connection
            return {
                "contacts": conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0],
                "groups": conn.execute("SELECT COUNT(*) FROM folders").fetchone()[0],
                "tags": conn.execute("SELECT COUNT(*) FROM tags").fetchone()[0],
                "favorites": conn.execute("SELECT COUNT(*) FROM contacts WHERE is_favorite = 1").fetchone()[0],
                "trash": conn.execute("SELECT COUNT(*) FROM deleted_contacts").fetchone()[0],
            }

    # ── Backup, restore and portable formats ────────────────────────────

    def export_backup(self) -> dict[str, Any]:
        contacts = self.list_contacts()
        with self.db.lock:
            conn = self.db.connection
            folders = [
                dict(row)
                for row in conn.execute(
                    "SELECT id, name, parent_folder_id, created_at FROM folders ORDER BY name COLLATE NOCASE"
                )
            ]
            tags = [dict(row) for row in conn.execute("SELECT id, name FROM tags ORDER BY name COLLATE NOCASE")]
            smart_groups = [dict(row) for row in conn.execute("SELECT id, name, field, value, created_at FROM smart_groups")]
            memberships = [
                dict(row)
                for row in conn.execute("SELECT contact_id, group_id AS folder_id FROM contact_groups")
            ]
            tag_assignments = [
                dict(row)
                for row in conn.execute("SELECT contact_id, tag_id FROM contact_tags")
            ]
            recent = [dict(row) for row in conn.execute("SELECT contact_id, viewed_at FROM recent_contacts")]

        phones: list[dict[str, Any]] = []
        emails: list[dict[str, Any]] = []
        contact_data: list[dict[str, Any]] = []
        for contact in contacts:
            item = self._contact_to_dict(contact)
            item["folder_ids"] = [row["folder_id"] for row in memberships if row["contact_id"] == contact.id]
            item["tag_ids"] = [row["tag_id"] for row in tag_assignments if row["contact_id"] == contact.id]
            contact_data.append(item)
            for phone in contact.phones:
                phones.append({
                    "id": phone.id,
                    "contact_id": contact.id,
                    "label": phone.label,
                    "number": phone.number,
                    "normalised_number": intelligence.normalize_phone(phone.number),
                })
            for email in contact.emails:
                emails.append({"id": email.id, "contact_id": contact.id, "label": email.label, "email": email.email})

        return {
            "format_version": 2,
            "version": 1,
            "app": "Contact Explorer Python",
            "exported_at": now_ms(),
            "folders": folders,
            "groups": folders,
            "contacts": contact_data,
            "phones": phones,
            "emails": emails,
            "memberships": memberships,
            "tags": tags,
            "tag_assignments": tag_assignments,
            "smart_groups": smart_groups,
            "recent": recent,
        }

    def _clear_active_data_locked(self, conn: sqlite3.Connection) -> None:
        conn.execute("DELETE FROM contact_groups")
        conn.execute("DELETE FROM contact_tags")
        conn.execute("DELETE FROM recent_contacts")
        conn.execute("DELETE FROM contact_phones")
        conn.execute("DELETE FROM contact_emails")
        conn.execute("DELETE FROM contacts")
        conn.execute("DELETE FROM tags")
        conn.execute("DELETE FROM folders")
        conn.execute("DELETE FROM smart_groups")
        conn.execute("DELETE FROM deleted_contacts")
        conn.execute("DELETE FROM contact_events")

    def import_backup(self, data: dict[str, Any], replace: bool = True) -> int:
        if not isinstance(data, dict) or not isinstance(data.get("contacts", []), list):
            raise ValueError("Invalid Contact Explorer backup")
        folders_data = data.get("folders") or data.get("groups") or []
        tags_data = data.get("tags") or []
        phones_by_contact: dict[str, list[dict[str, Any]]] = {}
        for item in data.get("phones", []) or []:
            if isinstance(item, dict):
                phones_by_contact.setdefault(str(item.get("contact_id", "")), []).append(item)
        emails_by_contact: dict[str, list[dict[str, Any]]] = {}
        for item in data.get("emails", []) or []:
            if isinstance(item, dict):
                emails_by_contact.setdefault(str(item.get("contact_id", "")), []).append(item)
        memberships_by_contact: dict[str, list[str]] = {}
        for item in data.get("memberships", []) or []:
            if isinstance(item, dict):
                memberships_by_contact.setdefault(str(item.get("contact_id", "")), []).append(str(item.get("folder_id", "")))
        tag_ids_by_contact: dict[str, list[str]] = {}
        for item in data.get("tag_assignments", []) or []:
            if isinstance(item, dict):
                tag_ids_by_contact.setdefault(str(item.get("contact_id", "")), []).append(str(item.get("tag_id", "")))

        imported = 0
        with self.db.transaction() as conn:
            if replace:
                self._clear_active_data_locked(conn)

            folder_names: dict[str, str] = {}
            for item in folders_data:
                if not isinstance(item, dict):
                    continue
                folder_id = str(item.get("id") or new_id("group-"))
                name = str(item.get("name", "")).strip()
                if not name:
                    continue
                folder_names[folder_id] = name
            for item in folders_data:
                if not isinstance(item, dict):
                    continue
                folder_id = str(item.get("id") or "")
                name = folder_names.get(folder_id)
                if not name:
                    continue
                parent = item.get("parent_folder_id")
                parent = str(parent) if parent and str(parent) in folder_names else None
                conn.execute(
                    "INSERT OR REPLACE INTO folders(id, name, parent_folder_id, created_at) VALUES (?, ?, ?, ?)",
                    (folder_id, name, parent, int(item.get("created_at") or now_ms())),
                )
            for item in tags_data:
                if not isinstance(item, dict):
                    continue
                tag_id = str(item.get("id") or new_id("tag-"))
                name = str(item.get("name", "")).strip()
                if name:
                    conn.execute("INSERT OR IGNORE INTO tags(id, name) VALUES (?, ?)", (tag_id, name))

            imported_ids: dict[str, str] = {}
            for raw in data.get("contacts", []):
                if not isinstance(raw, dict):
                    continue
                source_id = str(raw.get("id", ""))
                payload = dict(raw)
                if not payload.get("phones") and phones_by_contact.get(source_id):
                    payload["phones"] = phones_by_contact[source_id]
                if not payload.get("emails") and emails_by_contact.get(source_id):
                    payload["emails"] = emails_by_contact[source_id]
                if not payload.get("groups"):
                    payload["groups"] = [folder_names[item] for item in memberships_by_contact.get(source_id, []) if item in folder_names]
                if not payload.get("tags"):
                    tag_names = {
                        str(item.get("id")): str(item.get("name", ""))
                        for item in tags_data
                        if isinstance(item, dict)
                    }
                    payload["tags"] = [tag_names[item] for item in tag_ids_by_contact.get(source_id, []) if tag_names.get(item)]
                draft = self.draft_from_payload(payload)
                if not draft.name:
                    continue
                desired_id = source_id or None
                saved_id = self._save_contact_locked(conn, draft, desired_id, record_event=False)
                imported_ids[source_id] = saved_id
                imported += 1

            # The old PhoneBook JSON format stores memberships separately.
            for item in data.get("memberships", []) or []:
                if not isinstance(item, dict):
                    continue
                contact_id = imported_ids.get(str(item.get("contact_id")), str(item.get("contact_id", "")))
                group_id = str(item.get("folder_id", ""))
                if contact_id and group_id and conn.execute("SELECT 1 FROM contacts WHERE id = ?", (contact_id,)).fetchone() and conn.execute("SELECT 1 FROM folders WHERE id = ?", (group_id,)).fetchone():
                    conn.execute("INSERT OR IGNORE INTO contact_groups(contact_id, group_id) VALUES (?, ?)", (contact_id, group_id))

            for item in data.get("smart_groups", []) or data.get("smart_rules", []) or []:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", "")).strip()
                field = str(item.get("field", "company")).strip()
                value = str(item.get("value", "")).strip()
                if name and value:
                    conn.execute(
                        "INSERT OR REPLACE INTO smart_groups(id, name, field, value, created_at) VALUES (?, ?, ?, ?, ?)",
                        (str(item.get("id") or new_id("smart-")), name, field, value, int(item.get("created_at") or now_ms())),
                    )
            if not conn.execute("SELECT 1 FROM folders LIMIT 1").fetchone():
                for name in DEFAULT_GROUPS:
                    conn.execute("INSERT INTO folders(id, name, parent_folder_id, created_at) VALUES (?, ?, NULL, ?)", (new_id("group-"), name, now_ms()))
            self._record_event_locked(conn, None, "Vault", "RESTORED", f"Restored {imported} contacts from backup.")
        return imported

    def export_contacts_text(self, format_name: str, contact_ids: Iterable[str] | None = None, organized: bool = True) -> str:
        contacts = self.list_contacts()
        if contact_ids is not None:
            selected = {str(item) for item in contact_ids}
            contacts = [contact for contact in contacts if contact.id in selected]
        format_name = format_name.casefold()
        if format_name == "csv":
            return transfer.to_csv(contacts, include_organization=organized)
        if format_name in {"vcf", "vcard"}:
            return transfer.to_vcf(contacts, include_organization=organized)
        raise ValueError("Export format must be csv or vcf")

    def import_contacts_text(self, source: str, format_name: str, replace: bool = False) -> int:
        format_name = format_name.casefold()
        if format_name == "csv":
            drafts = transfer.from_csv(source)
        elif format_name in {"vcf", "vcard"}:
            drafts = transfer.from_vcf(source)
        else:
            raise ValueError("Import format must be csv or vcf")
        if replace:
            with self.db.transaction() as conn:
                self._clear_active_data_locked(conn)
                for name in DEFAULT_GROUPS:
                    conn.execute("INSERT INTO folders(id, name, parent_folder_id, created_at) VALUES (?, ?, NULL, ?)", (new_id("group-"), name, now_ms()))
        count = 0
        for draft in drafts:
            self.save_contact(None, draft)
            count += 1
        return count

    def export_vault_text(self) -> str:
        return transfer.dumps_vault(self.export_backup())

    def import_vault_text(self, source: str, replace: bool = True) -> int:
        return self.import_backup(transfer.loads_vault(source), replace=replace)

    def share_text(self, contact_ids: Iterable[str]) -> str:
        selected = {str(item) for item in contact_ids}
        contacts = [contact for contact in self.list_contacts() if contact.id in selected]
        chunks: list[str] = []
        for contact in contacts:
            chunks.append(
                "\n".join(
                    item
                    for item in [
                        contact.name,
                        *(f"{phone.label}: {phone.number}" for phone in contact.phones),
                        *(f"{email.label}: {email.email}" for email in contact.emails),
                        f"Company: {contact.company}" if contact.company else "",
                        f"Address: {contact.address}" if contact.address else "",
                        f"Notes: {contact.note}" if contact.note else "",
                    ]
                    if item
                )
            )
        return "\n\n".join(chunks)
