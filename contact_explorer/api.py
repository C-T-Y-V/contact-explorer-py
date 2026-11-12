"""Dependency-free local HTTP API for Contact Explorer integrations."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .service import ContactService


def _contact_json(service: ContactService, contact: Any) -> dict[str, Any]:
    with service.db.lock:
        folder_ids = service._folder_ids_locked(service.db.connection, contact.id)
    return service._contact_to_dict(contact, folder_ids)


class ContactExplorerHandler(BaseHTTPRequestHandler):
    service: ContactService

    server_version = "ContactExplorerPython/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        # Keep the optional backend quiet enough for a desktop console.
        return

    def _send(self, status: int, payload: Any) -> None:
        raw = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS")
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("JSON body must be an object")
        return value

    def _parts(self) -> tuple[list[str], dict[str, list[str]]]:
        parsed = urlparse(self.path)
        parts = [item for item in parsed.path.split("/") if item]
        return parts, parse_qs(parsed.query)

    def do_OPTIONS(self) -> None:
        self._send(204, {})

    def do_GET(self) -> None:
        try:
            parts, query = self._parts()
            if parts == ["api", "health"]:
                return self._send(200, {"ok": True, "service": "Contact Explorer Python"})
            if parts == ["api", "stats"]:
                return self._send(200, self.service.stats())
            if parts == ["api", "contacts"]:
                contacts = self.service.search_contacts(query.get("search", [""])[0])
                return self._send(200, [_contact_json(self.service, contact) for contact in contacts])
            if len(parts) == 3 and parts[:2] == ["api", "contacts"]:
                contact = self.service.get_contact(parts[2])
                return self._send(200, _contact_json(self.service, contact) if contact else {"error": "Not found"}) if contact else self._send(404, {"error": "Contact not found"})
            if parts == ["api", "groups"]:
                return self._send(200, [group.to_dict() for group in self.service.list_groups()])
            if len(parts) == 4 and parts[:2] == ["api", "groups"] and parts[3] == "contacts":
                return self._send(200, [_contact_json(self.service, contact) for contact in self.service.contacts_in_group(parts[2])])
            if parts == ["api", "tags"]:
                return self._send(200, [tag.to_dict() for tag in self.service.list_tags()])
            if parts == ["api", "favorites"]:
                return self._send(200, [_contact_json(self.service, contact) for contact in self.service.favorite_contacts()])
            if parts == ["api", "recent"]:
                return self._send(200, [_contact_json(self.service, contact) for contact in self.service.recent_contacts()])
            if parts == ["api", "trash"]:
                return self._send(200, [item.to_dict() for item in self.service.list_deleted()])
            if parts == ["api", "events"]:
                return self._send(200, [item.to_dict() for item in self.service.list_events()])
            if parts == ["api", "smart-groups"]:
                result = []
                for item in self.service.list_smart_groups():
                    payload = item.to_dict()
                    payload["contact_count"] = len(self.service.smart_group_contacts(item))
                    result.append(payload)
                return self._send(200, result)
            if parts == ["api", "duplicates"]:
                return self._send(200, [group.to_dict() for group in self.service.duplicate_groups()])
            if parts == ["api", "backup"] or parts == ["api", "vault"]:
                return self._send(200, self.service.export_backup())
            return self._send(404, {"error": "Endpoint not found"})
        except (ValueError, json.JSONDecodeError) as exc:
            self._send(400, {"error": str(exc)})
        except Exception as exc:  # pragma: no cover - defensive API boundary
            self._send(500, {"error": str(exc)})

    def do_POST(self) -> None:
        try:
            parts, _ = self._parts()
            body = self._read_json()
            if parts == ["api", "contacts"]:
                contact = self.service.save_contact(None, body)
                return self._send(201, _contact_json(self.service, contact))
            if parts == ["api", "groups"]:
                group = self.service.create_group(body.get("name", ""), body.get("parent_folder_id"))
                return self._send(201, group.to_dict())
            if parts == ["api", "tags"]:
                return self._send(201, self.service.create_tag(body.get("name", "")).to_dict())
            if parts == ["api", "backup"] or parts == ["api", "vault"]:
                return self._send(200, {"imported": self.service.import_backup(body, bool(body.get("replace", True)))})
            if len(parts) == 3 and parts[:2] == ["api", "trash"] and parts[2] == "restore":
                contact = self.service.restore_deleted(body.get("contact_id", ""))
                return self._send(200, _contact_json(self.service, contact))
            return self._send(404, {"error": "Endpoint not found"})
        except (ValueError, json.JSONDecodeError) as exc:
            self._send(400, {"error": str(exc)})
        except Exception as exc:  # pragma: no cover
            self._send(500, {"error": str(exc)})

    def do_PUT(self) -> None:
        try:
            parts, _ = self._parts()
            body = self._read_json()
            if len(parts) == 3 and parts[:2] == ["api", "contacts"]:
                contact = self.service.save_contact(parts[2], body)
                return self._send(200, _contact_json(self.service, contact))
            if len(parts) == 3 and parts[:2] == ["api", "groups"]:
                return self._send(200, self.service.rename_group(parts[2], body.get("name", "")).to_dict())
            return self._send(404, {"error": "Endpoint not found"})
        except (ValueError, json.JSONDecodeError) as exc:
            self._send(400, {"error": str(exc)})
        except Exception as exc:  # pragma: no cover
            self._send(500, {"error": str(exc)})

    def do_PATCH(self) -> None:
        try:
            parts, _ = self._parts()
            if len(parts) == 4 and parts[:3] == ["api", "contacts", parts[2]] and parts[3] == "favorite":
                return self._send(200, {"is_favorite": self.service.toggle_favorite(parts[2])})
            return self._send(404, {"error": "Endpoint not found"})
        except Exception as exc:  # pragma: no cover
            self._send(400, {"error": str(exc)})

    def do_DELETE(self) -> None:
        try:
            parts, _ = self._parts()
            if len(parts) == 3 and parts[:2] == ["api", "contacts"]:
                return self._send(200, {"deleted": self.service.delete_contacts([parts[2]]) == 1})
            if len(parts) == 3 and parts[:2] == ["api", "groups"]:
                return self._send(200, {"deleted": self.service.delete_group(parts[2])})
            if len(parts) == 3 and parts[:2] == ["api", "tags"]:
                return self._send(200, {"deleted": self.service.delete_tag(parts[2])})
            if len(parts) == 3 and parts[:2] == ["api", "trash"]:
                return self._send(200, {"deleted": self.service.permanently_delete(parts[2])})
            return self._send(404, {"error": "Endpoint not found"})
        except Exception as exc:  # pragma: no cover
            self._send(400, {"error": str(exc)})


def run_server(host: str = "127.0.0.1", port: int = 8765, db_path: str | Path | None = None) -> None:
    service = ContactService(db_path)
    handler = type("ConfiguredContactExplorerHandler", (ContactExplorerHandler,), {"service": service})
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Contact Explorer backend running at http://{host}:{port}")
    print(f"SQLite database: {service.db_path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Contact Explorer backend")
    finally:
        server.server_close()
        service.close()
