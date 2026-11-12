"""Local-only search, duplicate detection and categorisation helpers."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from .models import Contact


def normalize_phone(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    return digits[-10:] if len(digits) >= 10 else digits


def tokens(value: str) -> list[str]:
    return [part for part in re.split(r"[^\w@.+-]+", value.casefold()) if part]


def edit_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    if abs(len(left) - len(right)) > 3:
        return 99
    previous = list(range(len(right) + 1))
    for index, left_char in enumerate(left, 1):
        current = [index]
        for right_index, right_char in enumerate(right, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1]


@dataclass
class DuplicateGroup:
    contacts: list[Contact]
    reason: str
    confidence: int

    def to_dict(self) -> dict:
        return {
            "contacts": [contact.to_dict() for contact in self.contacts],
            "reason": self.reason,
            "confidence": self.confidence,
        }


@dataclass
class KeywordCluster:
    keyword: str
    suggested_category: str
    contacts: list[Contact]

    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "suggested_category": self.suggested_category,
            "contacts": [contact.to_dict() for contact in self.contacts],
        }


def _phones(contact: Contact) -> list[str]:
    return [phone.number for phone in contact.phones if phone.number.strip()]


def _emails(contact: Contact) -> list[str]:
    return [email.email.casefold() for email in contact.emails if email.email.strip()]


def _field_values(contact: Contact) -> dict[str, list[str]]:
    return {
        "name": [contact.name.casefold()],
        "phone": [value.casefold() for value in _phones(contact)],
        "email": _emails(contact),
        "company": [contact.company.casefold()],
        "address": [contact.address.casefold()],
        "city": [contact.address.casefold().split(",", 1)[0].strip()],
        "note": [contact.note.casefold()],
        "group": [value.casefold() for value in contact.groups],
        "tag": [value.casefold() for value in contact.tags],
        "favorite": [
            "true" if contact.is_favorite else "false",
            "yes" if contact.is_favorite else "no",
        ],
        "is": ["favorite" if contact.is_favorite else "", "starred" if contact.is_favorite else ""],
    }


def _relevance(query: str, value: str) -> int:
    query = query.casefold()
    value = value.casefold()
    if not query or not value:
        return 0
    if value == query:
        return 120
    if value.startswith(query):
        return 100
    if query in value:
        return 80
    if len(query) < 4:
        return 0
    best = 0
    for candidate in tokens(value):
        distance = edit_distance(query, candidate)
        if distance <= max(1, len(query) // 4):
            best = max(best, 55 - distance * 10)
    return best


def _matches_filter(contact: Contact, field: str, value: str) -> bool:
    aliases = {
        "work": "company",
        "office": "company",
        "college": "group",
        "school": "group",
        "family": "group",
        "friend": "group",
        "mobile": "phone",
        "cell": "phone",
        "mail": "email",
        "notes": "note",
        "fav": "favorite",
        "starred": "favorite",
    }
    key = aliases.get(field.casefold(), field.casefold())
    fields = _field_values(contact)
    values = fields.get(key)
    if values is None:
        values = [
            contact.name.casefold(),
            contact.company.casefold(),
            contact.address.casefold(),
            contact.note.casefold(),
            *fields["phone"],
            *fields["email"],
            *fields["group"],
            *fields["tag"],
        ]
    value = value.casefold()
    if key == "phone":
        digits = normalize_phone(value)
        return any(
            value in phone or (digits and digits in normalize_phone(phone)) for phone in values
        )
    return any(value in item for item in values)


def search_contacts(contacts: Iterable[Contact], query: str) -> list[Contact]:
    """Search all contact fields and return relevance-ranked contacts."""

    contacts = list(contacts)
    raw_tokens = [part for part in query.strip().split() if part]
    if not raw_tokens:
        return contacts

    filters: list[tuple[str, str]] = []
    free_terms: list[str] = []
    for item in raw_tokens:
        if ":" in item:
            field, value = item.split(":", 1)
            if field and value:
                filters.append((field, value))
        else:
            free_terms.append(item.casefold())

    ranked: list[tuple[int, Contact]] = []
    for contact in contacts:
        if filters and not all(_matches_filter(contact, key, value) for key, value in filters):
            continue
        fields = _field_values(contact)
        searchable = [value for values in fields.values() for value in values if value]
        score = 0
        for term in free_terms:
            term_digits = normalize_phone(term)
            best = 0
            for value in searchable:
                best = max(best, _relevance(term, value))
            if term_digits and len(term_digits) >= 3:
                best = max(
                    best,
                    110 if any(term_digits in normalize_phone(p) for p in _phones(contact)) else 0,
                )
            if not best:
                break
            score += best
        else:
            # Favorites, recent access and call frequency provide a small,
            # deterministic tie-breaker like the Android search plugin.
            score += 20 if contact.is_favorite else 0
            score += min(contact.times_contacted, 50)
            ranked.append((score, contact))

    ranked.sort(key=lambda item: (-item[0], item[1].name.casefold()))
    return [contact for _, contact in ranked]


def find_duplicate_groups(contacts: Iterable[Contact]) -> list[DuplicateGroup]:
    contacts = list(contacts)
    by_id = {contact.id: contact for contact in contacts}
    pair_scores: dict[tuple[str, str], tuple[int, str]] = {}

    def record(left: Contact, right: Contact, score: int, reason: str) -> None:
        s = sorted((left.id, right.id))
        pair: tuple[str, str] = (s[0], s[1])
        if pair not in pair_scores or score > pair_scores[pair][0]:
            pair_scores[pair] = score, reason

    def compare_bucket(buckets: dict[str, list[Contact]], score: int, reason: str) -> None:
        for bucket in buckets.values():
            unique = list({contact.id: contact for contact in bucket}.values())
            for index, left in enumerate(unique):
                for right in unique[index + 1 :]:
                    record(left, right, score, reason)

    phone_buckets: dict[str, list[Contact]] = {}
    email_buckets: dict[str, list[Contact]] = {}
    name_buckets: dict[str, list[Contact]] = {}
    for contact in contacts:
        for phone in {normalize_phone(value) for value in _phones(contact)}:
            if len(phone) >= 7:
                phone_buckets.setdefault(phone, []).append(contact)
        for email in set(_emails(contact)):
            if email:
                email_buckets.setdefault(email, []).append(contact)
        name = re.sub(r"\s+", " ", contact.name.casefold()).strip()
        if len(name) >= 2 and name != "unnamed contact":
            name_buckets.setdefault(name, []).append(contact)

    compare_bucket(phone_buckets, 95, "Identical phone number")
    compare_bucket(email_buckets, 90, "Identical email address")
    for bucket in name_buckets.values():
        unique = list({contact.id: contact for contact in bucket}.values())
        for index, left in enumerate(unique):
            for right in unique[index + 1 :]:
                same_company = bool(
                    left.company and left.company.casefold() == right.company.casefold()
                )
                record(
                    left,
                    right,
                    85 if same_company else 75,
                    "Same name and company" if same_company else "Identical name",
                )

    adjacency: dict[str, set[str]] = {}
    reasons: dict[str, str] = {}
    confidence: dict[str, int] = {}
    for (lid, rid), (score, reason) in pair_scores.items():
        if score < 60:
            continue
        adjacency.setdefault(lid, set()).add(rid)
        adjacency.setdefault(rid, set()).add(lid)
        reasons[lid] = reason
        reasons[rid] = reason
        confidence[lid] = max(confidence.get(lid, 0), score)
        confidence[rid] = max(confidence.get(rid, 0), score)

    result: list[DuplicateGroup] = []
    visited: set[str] = set()
    for start in adjacency:
        if start in visited:
            continue
        queue = [start]
        visited.add(start)
        member_ids: list[str] = []
        while queue:
            current = queue.pop(0)
            member_ids.append(current)
            for neighbor in adjacency.get(current, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        members = [by_id[item] for item in member_ids if item in by_id]
        if len(members) > 1:
            result.append(
                DuplicateGroup(
                    contacts=members,
                    reason=reasons.get(start, "Potential duplicate"),
                    confidence=max(confidence.get(item, 70) for item in member_ids),
                )
            )
    return sorted(result, key=lambda group: -group.confidence)


def suggested_tags(contact: Contact) -> set[str]:
    phones = " ".join(_phones(contact))
    emails = " ".join(_emails(contact))
    text = " ".join(
        (contact.name, contact.company, emails, contact.address, contact.note, phones)
    ).casefold()
    rules = {
        "developer": ("developer", "engineer", "software", "programmer"),
        "college": ("college", "university", "student", "campus"),
        "work": ("work", "office", "manager", "project"),
        "family": ("mom", "dad", "sister", "brother", "family", "mother", "father"),
        "emergency": ("emergency", "doctor", "hospital", "police"),
    }
    found = {tag for tag, words in rules.items() if any(word in text for word in words)}
    for email in emails.split():
        if "@" in email:
            domain = email.split("@", 1)[1].strip(".,")
            if domain:
                found.add(f"domain:{domain}")
    if contact.company.strip():
        found.add(f"company:{contact.company.strip().casefold()}")
    return found


def detect_keyword_clusters(contacts: Iterable[Contact]) -> list[KeywordCluster]:
    contacts = list(contacts)
    rules = [
        ("Legal & Advocates", ("adv", "advocate", "lawyer", "legal", "vakil")),
        (
            "Class & College",
            (
                "class",
                "classmate",
                "college",
                "school",
                "batch",
                "batchmate",
                "tuition",
                "coaching",
                "academy",
            ),
        ),
        ("Medical & Doctors", ("dr", "doctor", "doc", "clinic", "dentist", "pharma", "hospital")),
        (
            "Services & Home",
            (
                "plumber",
                "electrician",
                "carpenter",
                "driver",
                "mechanic",
                "maid",
                "cook",
                "painter",
            ),
        ),
        (
            "Real Estate",
            ("flat", "broker", "dealer", "agent", "realtor", "property", "builder", "rent"),
        ),
        ("Gym & Fitness", ("gym", "fitness", "trainer", "coach", "workout", "yoga")),
        (
            "Corporate & Work",
            (
                "office",
                "work",
                "corp",
                "manager",
                "boss",
                "client",
                "vendor",
                "tcs",
                "wipro",
                "infosys",
                "accenture",
            ),
        ),
        (
            "Family",
            (
                "mom",
                "dad",
                "mother",
                "father",
                "bhai",
                "sister",
                "brother",
                "chacha",
                "mama",
                "uncle",
                "aunty",
            ),
        ),
    ]
    clusters: list[KeywordCluster] = []
    for category, keywords in rules:
        matching = [
            contact
            for contact in contacts
            if any(
                keyword in tokens(f"{contact.name} {contact.company} {contact.note}")
                for keyword in keywords
            )
        ]
        if len(matching) >= 2:
            clusters.append(KeywordCluster(keywords[0], category, matching))

    stop_words = {
        "the",
        "and",
        "mr",
        "mrs",
        "shri",
        "kumar",
        "singh",
        "sharma",
        "patel",
        "gupta",
        "verma",
        "reddy",
        "rao",
        "contact",
        "new",
        "home",
        "cell",
        "work",
        "call",
        "test",
        "sim",
        "airtel",
        "jio",
        "phone",
    }
    token_map: dict[str, list[Contact]] = {}
    for contact in contacts:
        for token in set(tokens(contact.name)):
            if len(token) >= 3 and token not in stop_words:
                token_map.setdefault(token, []).append(contact)
    for keyword, members in token_map.items():
        member_ids = {item.id for item in members}
        if len(members) < 2 or any(
            member_ids.issubset({item.id for item in cluster.contacts}) for cluster in clusters
        ):
            continue
        pretty = keyword[:1].upper() + keyword[1:]
        if not any(
            cluster.suggested_category.casefold() == pretty.casefold() for cluster in clusters
        ):
            clusters.append(KeywordCluster(keyword, pretty, members))
    return sorted(clusters, key=lambda cluster: -len(cluster.contacts))


def matches_smart_group(contact: Contact, field: str, value: str) -> bool:
    value = value.casefold().strip()
    if field == "company":
        return value in contact.company.casefold()
    if field == "email":
        return any(value in email.email.casefold() for email in contact.emails)
    if field == "city":
        return value in contact.address.casefold().split(",", 1)[0]
    if field in {"note", "notes"}:
        return value in contact.note.casefold()
    if field == "name":
        return value in contact.name.casefold()
    if field == "phone":
        return any(value in phone.number.casefold() for phone in contact.phones)
    if field == "group":
        return any(value in group.casefold() for group in contact.groups)
    if field == "tag":
        return any(value in tag.casefold() for tag in contact.tags)
    return value in " ".join(_field_values(contact)["name"] + _field_values(contact)["company"])
