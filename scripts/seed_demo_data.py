"""Seed realistic demo contacts, groups, tags, and duplicates into Contact Explorer."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from contact_explorer.models import ContactDraft, EmailAddress, PhoneNumber
from contact_explorer.service import ContactService

DEMO_CONTACTS = [
    ContactDraft(
        name="Aarav Patel",
        phones=[PhoneNumber("+91 98201 11223", "Mobile"), PhoneNumber("+91 22 2400 1100", "Work")],
        emails=[EmailAddress("aarav.patel@techcorp.in", "Work")],
        company="TechCorp Innovations",
        address="Bandra Kurla Complex, Mumbai, Maharashtra",
        note="VP of Engineering. Lead on distributed cloud architecture.",
        groups=["Work", "Engineering"],
        tags=["leadership", "key-account"],
        is_favorite=True,
    ),
    ContactDraft(
        name="Diya Sengupta",
        phones=[PhoneNumber("+91 98300 44556", "Mobile")],
        emails=[
            EmailAddress("diya.s@designstudio.org", "Work"),
            EmailAddress("diya@gmail.com", "Personal"),
        ],
        company="Studio Pixel Works",
        address="Park Street, Kolkata, West Bengal",
        note="Principal Product Designer. Specializes in dark-mode UI systems.",
        groups=["Work", "Design"],
        tags=["contractor", "vip"],
        is_favorite=True,
    ),
    ContactDraft(
        name="Vikramaditya Rao",
        phones=[PhoneNumber("+91 94480 77889", "Mobile")],
        emails=[EmailAddress("vikram.rao@fintech.co", "Work")],
        company="Apex FinTech",
        address="MG Road, Bengaluru, Karnataka",
        note="Chief Risk Officer. Met at Global AI Summit 2026.",
        groups=["Work", "Finance"],
        tags=["partner", "finance"],
        is_favorite=False,
    ),
    ContactDraft(
        name="Ananya Sharma",
        phones=[PhoneNumber("+91 98110 33445", "Mobile")],
        emails=[EmailAddress("ananya.sharma@family.net", "Personal")],
        company="Freelance Consultant",
        address="Civil Lines, Jaipur, Rajasthan",
        note="Cousin. Remind about family reunion in December.",
        groups=["Family"],
        tags=["family", "personal"],
        is_favorite=True,
    ),
    ContactDraft(
        name="Rohan Verma",
        phones=[PhoneNumber("+91 98990 66778", "Mobile")],
        emails=[EmailAddress("rohan.verma@collegerockers.com", "Personal")],
        company="Cyberdyne Systems",
        address="Connaught Place, New Delhi",
        note="College classmate. DevOps specialist.",
        groups=["Friends", "Tech"],
        tags=["college", "devops"],
        is_favorite=False,
    ),
    ContactDraft(
        name="Aarav Patel",  # Intentional duplicate for deduplication testing
        phones=[PhoneNumber("+91 98201 11223", "Mobile")],
        emails=[EmailAddress("aarav.p@personal.org", "Personal")],
        company="TechCorp",
        address="Mumbai",
        note="Old business card.",
        groups=["Work"],
        tags=["lead"],
        is_favorite=False,
    ),
]


def seed(db_path: Path | None = None) -> None:
    service = ContactService(db_path)
    print(f"[*] Initialized database connection: {service.db.path}")

    for created, draft in enumerate(DEMO_CONTACTS, 1):
        contact = service.save_contact(None, draft)
        print(
            f"  [+] Created contact #{created}: {contact.name} ({contact.primary_phone or contact.primary_email})"
        )

    stats = service.stats()
    dup_clusters = len(service.duplicate_groups())
    print("\n[✓] Database seeding complete!")
    print(f"    Total Contacts : {stats['contacts']}")
    print(f"    Favorites      : {stats['favorites']}")
    print(f"    Groups         : {stats['groups']}")
    print(f"    Tags           : {stats['tags']}")
    print(f"    Trash          : {stats['trash']}")
    print(f"    Dup Clusters   : {dup_clusters}")
    service.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo data into Contact Explorer")
    parser.add_argument("--db", type=Path, default=None, help="Custom database path")
    args = parser.parse_args()
    seed(args.db)


if __name__ == "__main__":
    main()
