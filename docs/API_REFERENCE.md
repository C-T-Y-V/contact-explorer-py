# Contact Explorer REST API Reference

Contact Explorer provides an optional, dependency-free local HTTP REST API for scripting, system integrations, and third-party tools.

## Base Configuration

- **Default Host:** `127.0.0.1`
- **Default Port:** `8765`
- **Base URL:** `http://127.0.0.1:8765`
- **Content-Type:** `application/json; charset=utf-8`

---

## Endpoints

### 1. Health Check
Checks if the local server is alive and operational.

- **Method:** `GET`
- **Endpoint:** `/api/health`
- **Response `200 OK`:**
  ```json
  {
    "ok": true,
    "service": "Contact Explorer Python"
  }
  ```

### 2. System Statistics
Retrieves summary metrics across the contact database.

- **Method:** `GET`
- **Endpoint:** `/api/stats`
- **Response `200 OK`:**
  ```json
  {
    "contacts": 142,
    "favorites": 18,
    "groups": 6,
    "tags": 12,
    "trash": 3,
    "duplicates": 1
  }
  ```

### 3. List / Search Contacts
Lists all contacts or performs a filtered search.

- **Method:** `GET`
- **Endpoint:** `/api/contacts`
- **Query Parameters:**
  - `search` (optional): Query string supporting free text or field tokens (`group:`, `tag:`, `company:`, `city:`).
- **Example:** `GET /api/contacts?search=company:google`
- **Response `200 OK`:**
  ```json
  [
    {
      "id": "c7a1c320-b384-48f8-b397-bb19cbdf5208",
      "name": "Jane Doe",
      "phone": "+1 555 123 4567",
      "email": "jane.doe@example.com",
      "company": "Acme Corp",
      "address": "123 Market St, San Francisco, CA",
      "notes": "Lead Architect",
      "is_favorite": true,
      "phones": [
        { "id": 1, "label": "Mobile", "number": "+1 555 123 4567" }
      ],
      "emails": [
        { "id": 1, "label": "Work", "email": "jane.doe@example.com" }
      ],
      "groups": ["Work", "Engineering"],
      "tags": ["key-contact"],
      "created_at": 1715000000000,
      "updated_at": 1715000000000,
      "times_contacted": 5
    }
  ]
  ```

### 4. Get Contact by ID
- **Method:** `GET`
- **Endpoint:** `/api/contacts/{id}`
- **Response `200 OK`:** Single contact JSON object.
- **Response `404 Not Found`:** `{"error": "Contact not found"}`

### 5. Create Contact
- **Method:** `POST`
- **Endpoint:** `/api/contacts`
- **Payload:**
  ```json
  {
    "name": "Alex Mercer",
    "phones": [{ "label": "Mobile", "number": "+1 555 987 6543" }],
    "emails": [{ "label": "Personal", "email": "alex@example.com" }],
    "company": "Cyberdyne",
    "groups": ["Tech"],
    "tags": ["vip"],
    "is_favorite": false
  }
  ```
- **Response `201 Created`:** Created contact JSON object.

### 6. Delete Contacts (Soft Delete)
Moves contacts to the 30-day recycle bin.

- **Method:** `POST`
- **Endpoint:** `/api/trash`
- **Payload:**
  ```json
  {
    "contact_ids": ["c7a1c320-b384-48f8-b397-bb19cbdf5208"]
  }
  ```
- **Response `200 OK`:** `{"deleted_count": 1}`

### 7. List Deleted Contacts (Recycle Bin)
- **Method:** `GET`
- **Endpoint:** `/api/trash`
- **Response `200 OK`:** List of deleted contact snapshots.

### 8. List Duplicate Groups
Detects potential contact duplicates based on phone numbers, emails, and fuzzy names.

- **Method:** `GET`
- **Endpoint:** `/api/duplicates`
- **Response `200 OK`:**
  ```json
  [
    {
      "reason": "Matching phone number (+15551234567)",
      "contacts": [ ... ]
    }
  ]
  ```

### 9. Export Vault (Full Backup)
Exports the entire relational database into a single JSON vault document.

- **Method:** `GET`
- **Endpoint:** `/api/vault`
- **Response `200 OK`:** Lossless JSON vault object containing `contacts`, `groups`, `tags`, `events`, and `smart_groups`.
