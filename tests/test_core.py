from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from contact_explorer.intelligence import find_duplicate_groups, search_contacts
from contact_explorer.models import ContactDraft, EmailAddress, PhoneNumber
from contact_explorer.service import ContactService
from contact_explorer.transfer import from_csv, from_vcf, to_csv, to_vcf


class ContactExplorerCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.close()
        self.path = Path(handle.name)
        self.service = ContactService(self.path)

    def tearDown(self) -> None:
        self.service.close()
        for suffix in ("", "-wal", "-shm"):
            self.path.with_name(self.path.name + suffix).unlink(missing_ok=True)

    def test_contact_crud_search_groups_and_tags(self) -> None:
        contact = self.service.save_contact(
            None,
            ContactDraft(
                "Rahul Sharma",
                [PhoneNumber("+91 98765 43210")],
                [EmailAddress("rahul@example.com")],
                company="Acme Labs",
                address="Jaipur, Rajasthan",
                note="developer",
                groups=["Family"],
                tags=["priority"],
                is_favorite=True,
            ),
        )
        self.assertEqual(self.service.search_contacts("company:acme")[0].id, contact.id)
        self.assertEqual(self.service.search_contacts("tag:priority")[0].id, contact.id)
        self.assertEqual(self.service.favorite_contacts()[0].id, contact.id)
        self.assertEqual(
            self.service.get_group(
                next(group.id for group in self.service.list_groups() if group.name == "Family")
            ).contact_count,
            1,
        )

    def test_recycle_bin_restore(self) -> None:
        contact = self.service.save_contact(
            None, ContactDraft("Recycle Me", [PhoneNumber("1234567890")])
        )
        self.assertEqual(self.service.delete_contacts([contact.id]), 1)
        self.assertEqual(self.service.stats()["trash"], 1)
        restored = self.service.restore_deleted(contact.id)
        self.assertEqual(restored.name, "Recycle Me")
        self.assertEqual(self.service.stats()["trash"], 0)

    def test_duplicate_detection_and_merge(self) -> None:
        first = self.service.save_contact(
            None,
            ContactDraft(
                "Same Person",
                [PhoneNumber("+91 9999999999")],
                [EmailAddress("same@example.com")],
                company="Acme",
            ),
        )
        second = self.service.save_contact(
            None,
            ContactDraft(
                "Same Person", [PhoneNumber("9999999999")], [EmailAddress("same@example.com")]
            ),
        )
        groups = self.service.duplicate_groups()
        self.assertTrue(groups)
        self.service.merge_contacts(first.id, [second.id])
        self.assertEqual(len(self.service.list_contacts()), 1)
        self.assertEqual(len(self.service.get_contact(first.id).phones), 1)

    def test_csv_vcard_and_vault_round_trip(self) -> None:
        contact = self.service.save_contact(
            None,
            ContactDraft(
                "Neha, Test",
                [PhoneNumber("+91 123")],
                [EmailAddress("neha@example.com")],
                note="hello, world",
                groups=["Friends"],
                tags=["vip"],
                is_favorite=True,
            ),
        )
        csv_text = to_csv([contact])
        csv_draft = from_csv(csv_text)[0]
        self.assertEqual(csv_draft.name, contact.name)
        vcf_draft = from_vcf(to_vcf([contact]))[0]
        self.assertEqual(vcf_draft.email, contact.primary_email)
        vault = json.loads(self.service.export_vault_text())
        other_path = self.path.with_name(self.path.stem + "-other.db")
        other = ContactService(other_path)
        try:
            self.assertEqual(other.import_backup(vault), 1)
            self.assertEqual(other.list_contacts()[0].tags, ["vip"])
        finally:
            other.close()
            for suffix in ("", "-wal", "-shm"):
                other_path.with_name(other_path.name + suffix).unlink(missing_ok=True)

    def test_local_search_and_duplicate_helpers_accept_contact_lists(self) -> None:
        first = self.service.save_contact(
            None, ContactDraft("Aman Gupta", [PhoneNumber("1112223333")], company="College")
        )
        second = self.service.save_contact(
            None, ContactDraft("Priya Singh", [PhoneNumber("4445556666")], company="Office")
        )
        self.assertEqual(search_contacts([first, second], "college")[0].id, first.id)
        self.assertEqual(find_duplicate_groups([first, second]), [])


if __name__ == "__main__":
    unittest.main()
