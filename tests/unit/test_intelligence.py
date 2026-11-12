"""Unit tests for Contact Explorer search and intelligence algorithms."""

from __future__ import annotations

from contact_explorer.intelligence import find_duplicate_groups, search_contacts
from contact_explorer.models import Contact, EmailAddress, PhoneNumber


def make_contact(
    cid: str,
    name: str,
    phones: list[str],
    emails: list[str],
    company: str = "",
    groups: list[str] | None = None,
    tags: list[str] | None = None,
    is_favorite: bool = False,
) -> Contact:
    return Contact(
        id=cid,
        name=name,
        phones=[PhoneNumber(p) for p in phones],
        emails=[EmailAddress(e) for e in emails],
        company=company,
        groups=groups or [],
        tags=tags or [],
        is_favorite=is_favorite,
    )


def test_field_query_search() -> None:
    c1 = make_contact("1", "Alice Smith", ["+1 555 1111"], ["alice@acme.com"], company="Acme", tags=["lead"])
    c2 = make_contact("2", "Bob Jones", ["+1 555 2222"], ["bob@globex.com"], company="Globex", groups=["Sales"])
    c3 = make_contact("3", "Charlie Brown", ["+1 555 3333"], ["charlie@acme.com"], company="Acme", is_favorite=True)
    contacts = [c1, c2, c3]

    # Search by company
    results = search_contacts(contacts, "company:acme")
    assert len(results) == 2
    assert {r.id for r in results} == {"1", "3"}

    # Search by tag
    results = search_contacts(contacts, "tag:lead")
    assert len(results) == 1
    assert results[0].id == "1"

    # Search by group
    results = search_contacts(contacts, "group:sales")
    assert len(results) == 1
    assert results[0].id == "2"

    # Search by favorite
    results = search_contacts(contacts, "is:favorite")
    assert len(results) == 1
    assert results[0].id == "3"


def test_free_text_and_partial_search() -> None:
    c1 = make_contact("1", "Priyanshu Sharma", ["9876543210"], ["priyanshu@example.com"])
    c2 = make_contact("2", "Rahul Dravid", ["9811122233"], ["rahul@cricket.org"])
    contacts = [c1, c2]

    # Name search
    assert len(search_contacts(contacts, "Priyanshu")) == 1
    assert search_contacts(contacts, "Priyanshu")[0].id == "1"

    # Phone fragment search
    assert len(search_contacts(contacts, "43210")) == 1
    assert search_contacts(contacts, "43210")[0].id == "1"


def test_duplicate_detection_by_exact_phone() -> None:
    c1 = make_contact("1", "Kavita Rao", ["+91 99999 88888"], ["kavita1@example.com"])
    c2 = make_contact("2", "Kavita", ["99999 88888"], ["kavita2@example.com"])
    c3 = make_contact("3", "Unrelated Person", ["+91 11111 22222"], ["other@example.com"])

    clusters = find_duplicate_groups([c1, c2, c3])
    assert len(clusters) == 1
    cluster_ids = {c.id for c in clusters[0].contacts}
    assert cluster_ids == {"1", "2"}


def test_duplicate_detection_by_exact_email() -> None:
    c1 = make_contact("1", "Sunil Gavaskar", ["111"], ["legend@india.cricket"])
    c2 = make_contact("2", "S. Gavaskar", ["222"], ["legend@india.cricket"])

    clusters = find_duplicate_groups([c1, c2])
    assert len(clusters) == 1
    assert len(clusters[0].contacts) == 2
