"""CSV, vCard and JSON vault portability helpers."""

from __future__ import annotations

import csv
import io
import json
import quopri
import re
from typing import Any, Iterable

from .models import Contact, ContactDraft, EmailAddress, PhoneNumber


def _escape_vcf(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")


def _unescape_vcf(value: str) -> str:
    return value.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def to_csv(contacts: Iterable[Contact], include_organization: bool = True) -> str:
    columns = ["name", "phone", "email", "company", "address", "notes"]
    if include_organization:
        columns += ["groups", "tags", "favorite"]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    for contact in contacts:
        row: dict[str, Any] = {
            "name": contact.name,
            "phone": ";".join(phone.number for phone in contact.phones),
            "email": ";".join(email.email for email in contact.emails),
            "company": contact.company,
            "address": contact.address,
            "notes": contact.note,
        }
        if include_organization:
            row.update(
                groups=";".join(contact.groups),
                tags=";".join(contact.tags),
                favorite="true" if contact.is_favorite else "false",
            )
        writer.writerow(row)
    return output.getvalue()


def _split_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(";") if item.strip()]


def from_csv(source: str) -> list[ContactDraft]:
    rows = list(csv.DictReader(io.StringIO(source)))
    if not rows:
        # Also accept a headerless six-column export.
        raw = list(csv.reader(io.StringIO(source)))
        rows = [
            dict(zip(("name", "phone", "email", "company", "address", "notes"), row))
            for row in raw
            if any(cell.strip() for cell in row)
        ]
    drafts: list[ContactDraft] = []
    for row in rows:
        normalized = {str(key).strip().casefold(): (value or "").strip() for key, value in row.items()}
        name = normalized.get("name", "").strip()
        if not name:
            continue
        phone_values = _split_values(normalized.get("phone", ""))
        email_values = _split_values(normalized.get("email", ""))
        drafts.append(
            ContactDraft(
                name=name,
                phones=[PhoneNumber(number) for number in phone_values],
                emails=[EmailAddress(email) for email in email_values],
                company=normalized.get("company", ""),
                address=normalized.get("address", ""),
                note=normalized.get("notes", normalized.get("note", "")),
                groups=_split_values(normalized.get("groups", "")),
                tags=_split_values(normalized.get("tags", "")),
                is_favorite=normalized.get("favorite", "").casefold() in {"1", "true", "yes", "y"},
            )
        )
    return drafts


def to_vcf(contacts: Iterable[Contact], include_organization: bool = True) -> str:
    lines: list[str] = []
    for contact in contacts:
        lines.extend(("BEGIN:VCARD", "VERSION:3.0", f"FN:{_escape_vcf(contact.name)}", f"N:{_escape_vcf(contact.name)};;;;"))
        for phone in contact.phones:
            label = phone.label.upper() or "CELL"
            lines.append(f"TEL;TYPE={label}:{_escape_vcf(phone.number)}")
        for email in contact.emails:
            label = email.label.upper() or "INTERNET"
            lines.append(f"EMAIL;TYPE={label}:{_escape_vcf(email.email)}")
        if contact.company:
            lines.append(f"ORG:{_escape_vcf(contact.company)}")
        if contact.address:
            lines.append(f"ADR;TYPE=HOME:;;{_escape_vcf(contact.address)};;;;")
        if contact.note:
            lines.append(f"NOTE:{_escape_vcf(contact.note)}")
        if include_organization:
            if contact.groups:
                lines.append("CATEGORIES:" + ",".join(_escape_vcf(item) for item in contact.groups))
            if contact.tags:
                lines.append("X-TAGS:" + ",".join(_escape_vcf(item) for item in contact.tags))
            if contact.is_favorite:
                lines.append("X-FAVORITE:TRUE")
        lines.append("END:VCARD")
    return "\r\n".join(lines) + ("\r\n" if lines else "")


def _decode_vcf_value(value: str, encoded: bool) -> str:
    if not encoded:
        return value
    try:
        return quopri.decodestring(value).decode("utf-8", errors="replace")
    except Exception:
        return value


def from_vcf(source: str) -> list[ContactDraft]:
    unfolded: list[str] = []
    for line in source.replace("\r\n", "\n").split("\n"):
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)

    drafts: list[ContactDraft] = []
    card: dict[str, Any] | None = None
    for line in unfolded:
        upper = line.upper()
        if upper == "BEGIN:VCARD":
            card = {"phones": [], "emails": [], "groups": [], "tags": [], "favorite": False}
            continue
        if upper == "END:VCARD":
            if card is None:
                continue
            if card.get("name") or card["phones"] or card["emails"]:
                drafts.append(
                    ContactDraft(
                        name=card.get("name") or "Unnamed contact",
                        phones=card["phones"],
                        emails=card["emails"],
                        company=card.get("company", ""),
                        address=card.get("address", ""),
                        note=card.get("note", ""),
                        groups=list(dict.fromkeys(card["groups"])),
                        tags=list(dict.fromkeys(card["tags"])),
                        is_favorite=bool(card["favorite"]),
                    )
                )
            card = None
            continue
        if card is None or ":" not in line:
            continue
        key_part, raw_value = line.split(":", 1)
        key = key_part.split(";", 1)[0].upper()
        params = key_part.upper()
        value = _unescape_vcf(_decode_vcf_value(raw_value, "ENCODING=QUOTED-PRINTABLE" in params))
        if key == "FN" and not card.get("name"):
            card["name"] = value
        elif key == "N" and not card.get("name"):
            card["name"] = value.split(";", 1)[0].replace(";", " ").strip()
        elif key == "TEL":
            label = "Home" if "HOME" in params else "Work" if "WORK" in params else "Mobile"
            if value.strip() and value.strip() not in {phone.number for phone in card["phones"]}:
                card["phones"].append(PhoneNumber(value.strip(), label))
        elif key == "EMAIL":
            label = "Work" if "WORK" in params else "Home"
            if value.strip() and value.strip().casefold() not in {email.email.casefold() for email in card["emails"]}:
                card["emails"].append(EmailAddress(value.strip(), label))
        elif key == "ORG" and not card.get("company"):
            card["company"] = value
        elif key == "ADR" and not card.get("address"):
            card["address"] = value.strip(";").replace(";;", "").replace(";", ", ")
        elif key == "NOTE" and not card.get("note"):
            card["note"] = value
        elif key in {"CATEGORIES", "CATEGORY"}:
            card["groups"].extend(item.strip() for item in value.split(",") if item.strip())
        elif key in {"X-TAGS", "X-TAG"}:
            card["tags"].extend(item.strip() for item in value.split(",") if item.strip())
        elif key == "X-FAVORITE":
            card["favorite"] = value.strip().casefold() in {"1", "true", "yes"}
    return drafts


def dumps_vault(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def loads_vault(source: str) -> dict[str, Any]:
    data = json.loads(source)
    if not isinstance(data, dict):
        raise ValueError("Vault must contain a JSON object")
    if "contacts" not in data:
        raise ValueError("This file does not contain Contact Explorer contacts")
    return data
