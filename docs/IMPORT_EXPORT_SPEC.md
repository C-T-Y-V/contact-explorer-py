# Contact Explorer Import & Export Specification

Contact Explorer provides lossless and interchangeable import/export across three industry-standard formats: **CSV (RFC 4180)**, **vCard (RFC 6350 / RFC 2426)**, and native **JSON Vault**.

---

## 1. Comma Separated Values (CSV)

### CSV Header Schema
Exported CSV files use standard UTF-8 encoding with CRLF row breaks and RFC 4180 compliant quotation escaping.

```csv
Name,Phone,Email,Company,Address,Notes,Groups,Tags,Favorite
"Sharma, Rahul","+91 98765 43210","rahul@example.com","Acme Labs","Jaipur, Rajasthan","Senior Engineer","Engineering;Family","vip;work",true
```

### Column Specifications
| Column | Type | Description |
| :--- | :--- | :--- |
| `Name` | String | Full display name (required). |
| `Phone` | String | Primary phone number (or semicolon-delimited numbers). |
| `Email` | String | Primary email address (or semicolon-delimited emails). |
| `Company` | String | Organization / company name. |
| `Address` | String | Street address. Escaped with quotes if containing commas. |
| `Notes` | String | Free-text notes and remarks. |
| `Groups` | String | Semicolon-delimited group memberships (e.g. `Work;Tech`). |
| `Tags` | String | Semicolon-delimited tags (e.g. `priority;leads`). |
| `Favorite` | Boolean | `true` or `false` (case-insensitive). |

---

## 2. vCard (.vcf) Specification

Contact Explorer parses and generates standard vCard format compliant with vCard 3.0 and 4.0 specifications.

### Sample Generated vCard
```vcard
BEGIN:VCARD
VERSION:3.0
FN:Priyanshu Sharma
TEL;TYPE=CELL:+91 98765 43210
TEL;TYPE=WORK:+91 11 2345 6789
EMAIL;TYPE=HOME:priyanshu@example.com
ORG:CTYV Technologies
ADR;TYPE=HOME:;;Sector 62;Noida;UP;201309;India
NOTE:Lead Developer & Architect
CATEGORIES:Engineering,Core Team
X-CONTACT-EXPLORER-FAVORITE:TRUE
END:VCARD
```

---

## 3. JSON Vault Specification

The JSON Vault format captures the entire relational snapshot of the database, preserving internal primary keys, multi-phone labels, folder hierarchies, and audit events.

### Vault Schema Structure
```json
{
  "version": "1.0",
  "exported_at": 1715000000000,
  "contacts": [
    {
      "id": "c7a1c320-b384-48f8-b397-bb19cbdf5208",
      "name": "Priyanshu Sharma",
      "company": "CTYV Technologies",
      "address": "Sector 62, Noida, India",
      "note": "Lead Architect",
      "is_favorite": true,
      "phones": [
        { "id": 1, "label": "Mobile", "number": "+91 98765 43210" }
      ],
      "emails": [
        { "id": 1, "label": "Work", "email": "priyanshu@example.com" }
      ],
      "groups": ["Engineering"],
      "tags": ["core", "lead"],
      "created_at": 1715000000000,
      "updated_at": 1715000000000,
      "times_contacted": 12
    }
  ],
  "groups": [
    {
      "id": "grp-eng",
      "name": "Engineering",
      "parent_folder_id": null,
      "created_at": 1715000000000
    }
  ],
  "tags": [
    { "id": "tag-core", "name": "core" }
  ],
  "smart_groups": [],
  "events": []
}
```
