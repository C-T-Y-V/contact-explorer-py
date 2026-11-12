"""Unit tests for ContactService business logic layer."""

from __future__ import annotations

from contact_explorer.models import ContactDraft, EmailAddress, PhoneNumber
from contact_explorer.service import ContactService


def test_service_crud_lifecycle(service: ContactService, sample_draft: ContactDraft) -> None:
    # 1. Create Contact
    contact = service.save_contact(None, sample_draft)
    assert contact.id is not None
    assert contact.name == sample_draft.name
    assert len(contact.phones) == 2
    assert len(contact.emails) == 2
    assert contact.is_favorite is True

    # 2. Read Contact
    retrieved = service.get_contact(contact.id)
    assert retrieved is not None
    assert retrieved.name == sample_draft.name
    assert retrieved.company == "Enterprise Corp"

    # 3. Update Contact
    updated_draft = ContactDraft(
        name="Aditi Rao Kapoor",
        phones=[PhoneNumber("+91 98765 00001", "Mobile")],
        emails=[EmailAddress("aditi.kapoor@enterprisecorp.com", "Work")],
        company="Enterprise Corp Inc",
        is_favorite=False,
    )
    updated = service.save_contact(contact.id, updated_draft)
    assert updated.name == "Aditi Rao Kapoor"
    assert updated.company == "Enterprise Corp Inc"
    assert updated.is_favorite is False

    # 4. Favorites & Recents
    service.record_viewed(contact.id)
    recents = service.recent_contacts()
    assert any(c.id == contact.id for c in recents)


def test_service_soft_delete_and_restore(service: ContactService) -> None:
    draft = ContactDraft("Delete Candidate", [PhoneNumber("9998887776")])
    contact = service.save_contact(None, draft)

    # Soft delete
    deleted_count = service.delete_contacts([contact.id])
    assert deleted_count == 1
    assert service.get_contact(contact.id) is None

    # Check Trash
    trash = service.list_deleted()
    assert len(trash) == 1
    assert trash[0].contact_id == contact.id
    assert trash[0].name == "Delete Candidate"

    # Restore from Trash
    restored = service.restore_deleted(contact.id)
    assert restored is not None
    assert restored.name == "Delete Candidate"
    assert len(service.list_deleted()) == 0
    assert service.get_contact(restored.id) is not None


def test_service_merge_contacts(service: ContactService) -> None:
    primary = service.save_contact(
        None,
        ContactDraft(
            "Primary User", [PhoneNumber("1111111111")], [EmailAddress("primary@test.com")]
        ),
    )
    secondary = service.save_contact(
        None,
        ContactDraft(
            "Secondary User", [PhoneNumber("2222222222")], [EmailAddress("secondary@test.com")]
        ),
    )

    merged = service.merge_contacts(primary.id, [secondary.id])
    assert merged is not None
    assert len(merged.phones) == 2
    assert len(merged.emails) == 2
    assert service.get_contact(secondary.id) is None


def test_service_groups_and_tags(service: ContactService) -> None:
    draft1 = ContactDraft("User A", [PhoneNumber("111")], groups=["Developers"], tags=["python"])
    draft2 = ContactDraft("User B", [PhoneNumber("222")], groups=["Developers"], tags=["rust"])
    service.save_contact(None, draft1)
    service.save_contact(None, draft2)

    groups = service.list_groups()
    dev_group = next((g for g in groups if g.name == "Developers"), None)
    assert dev_group is not None
    assert dev_group.contact_count == 2

    tags = service.list_tags()
    tag_names = {t.name for t in tags}
    assert "python" in tag_names
    assert "rust" in tag_names
