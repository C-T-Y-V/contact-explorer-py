"""Unit tests for Contact Explorer transfer engine (CSV, vCard, Vault)."""

from __future__ import annotations

from contact_explorer.models import Contact, EmailAddress, PhoneNumber
from contact_explorer.transfer import from_csv, from_vcf, to_csv, to_vcf


def test_csv_export_and_import_roundtrip() -> None:
    original = Contact(
        id="c-test-csv",
        name="Rohit Sharma",
        phones=[PhoneNumber("+91 98765 00000", "Mobile")],
        emails=[EmailAddress("rohit@hitman.in", "Work")],
        company="Team India",
        address="Mumbai, Maharashtra",
        note="Captain, cricket specialist",
        groups=["Sports", "Leadership"],
        tags=["vip", "opener"],
        is_favorite=True,
    )

    csv_data = to_csv([original])
    assert "Rohit Sharma" in csv_data
    assert "+91 98765 00000" in csv_data
    assert "Team India" in csv_data

    imported_drafts = from_csv(csv_data)
    assert len(imported_drafts) == 1
    draft = imported_drafts[0]
    assert draft.name == original.name
    assert draft.phone == original.primary_phone
    assert draft.email == original.primary_email
    assert draft.company == original.company
    assert draft.is_favorite is True


def test_vcard_export_and_import_roundtrip() -> None:
    original = Contact(
        id="c-test-vcf",
        name="Virat Kohli",
        phones=[PhoneNumber("+91 98100 12345", "Mobile")],
        emails=[EmailAddress("virat@kohli.in", "Personal")],
        company="RCB Sports",
        address="Bengaluru, Karnataka",
        note="Fitness leader",
        groups=["Athletes"],
        tags=["cricket", "legend"],
        is_favorite=True,
    )

    vcf_text = to_vcf([original])
    assert "BEGIN:VCARD" in vcf_text
    assert "FN:Virat Kohli" in vcf_text
    assert "TEL" in vcf_text
    assert "EMAIL" in vcf_text
    assert "END:VCARD" in vcf_text

    imported_drafts = from_vcf(vcf_text)
    assert len(imported_drafts) == 1
    draft = imported_drafts[0]
    assert draft.name == original.name
    assert draft.email == original.primary_email
