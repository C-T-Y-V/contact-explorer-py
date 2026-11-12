"""Tkinter desktop frontend for Contact Explorer."""

from __future__ import annotations

import contextlib
import os
import tkinter as tk
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from .models import Contact, ContactDraft, EmailAddress, PhoneNumber
from .service import ContactService

COLORS = {
    "bg": "#07111f",
    "panel": "#0d1b2d",
    "panel_alt": "#10243a",
    "panel_hover": "#173451",
    "line": "#214665",
    "cyan": "#42e0b5",
    "blue": "#55b8ff",
    "purple": "#9b8cff",
    "amber": "#ffc857",
    "pink": "#ff77b9",
    "danger": "#ff718b",
    "text": "#f3f7ff",
    "muted": "#91a6bd",
    "dark_text": "#06101b",
}


def initials(name: str) -> str:
    parts = [part for part in name.split() if part]
    return "".join(part[0] for part in parts[:2]).upper() or "?"


def format_time(timestamp: int, with_time: bool = True) -> str:
    if not timestamp:
        return "—"
    value = datetime.fromtimestamp(timestamp / 1000)
    return value.strftime("%d %b %Y, %I:%M %p" if with_time else "%d %b %Y")


class ContactExplorerApp(tk.Tk):
    def __init__(self, db_path: str | Path | None = None) -> None:
        super().__init__()
        self.service = ContactService(db_path)
        self.title("Contact Explorer — Python Edition")
        self.geometry("1320x820")
        self.minsize(1000, 650)
        self.configure(bg=COLORS["bg"])
        self.protocol("WM_DELETE_WINDOW", self.close)

        self.current_page = "home"
        self.current_group_id: str | None = None
        self.selected_ids: set[str] = set()
        self.view_mode = tk.StringVar(value="list")
        self.sort_mode = tk.StringVar(value="Name A to Z")
        self.search_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready · all data stays on this device")
        self.nav_buttons: dict[str, tk.Button] = {}
        self.content: tk.Frame
        self.tree: ttk.Treeview | None = None
        self.preview: tk.Frame | None = None
        self.card_vars: dict[str, tk.BooleanVar] = {}
        self._search_after_id: str | None = None

        self._configure_styles()
        self._build_shell()
        self._bind_shortcuts()
        self.show_page("home")

    # ── Shell and styling ──────────────────────────────────────────────

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        with contextlib.suppress(tk.TclError):
            style.theme_use("clam")
        style.configure(
            "Treeview",
            background=COLORS["panel"],
            fieldbackground=COLORS["panel"],
            foreground=COLORS["text"],
            rowheight=38,
            borderwidth=0,
        )
        style.map(
            "Treeview", background=[("selected", "#1d5f86")], foreground=[("selected", "#ffffff")]
        )
        style.configure(
            "Treeview.Heading",
            background=COLORS["panel_alt"],
            foreground=COLORS["muted"],
            relief="flat",
            padding=(8, 8),
            font=("Segoe UI", 9, "bold"),
        )
        style.configure(
            "TScrollbar",
            background=COLORS["panel_alt"],
            troughcolor=COLORS["bg"],
            arrowcolor=COLORS["muted"],
        )
        style.configure(
            "TCombobox",
            fieldbackground=COLORS["panel_alt"],
            background=COLORS["panel_alt"],
            foreground=COLORS["text"],
        )
        style.configure("TCheckbutton", background=COLORS["panel"], foreground=COLORS["text"])

    def _build_shell(self) -> None:
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        header = tk.Frame(self, bg=COLORS["panel"], height=74)
        header.grid(row=0, column=0, columnspan=2, sticky="nsew")
        header.grid_propagate(False)
        header.grid_columnconfigure(1, weight=1)

        brand = tk.Frame(header, bg=COLORS["panel"])
        brand.grid(row=0, column=0, padx=(22, 18), pady=12, sticky="w")
        tk.Label(
            brand,
            text="CONTACT",
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")
        tk.Label(
            brand,
            text="EXPLORER",
            bg=COLORS["panel"],
            fg=COLORS["cyan"],
            font=("Segoe UI", 20, "bold"),
        ).pack(anchor="w")

        search_frame = tk.Frame(
            header, bg=COLORS["panel_alt"], highlightbackground=COLORS["line"], highlightthickness=1
        )
        search_frame.grid(row=0, column=1, padx=12, pady=17, sticky="ew")
        tk.Label(
            search_frame, text="⌕", bg=COLORS["panel_alt"], fg=COLORS["cyan"], font=("Segoe UI", 18)
        ).pack(side="left", padx=(12, 6))
        self.search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            bg=COLORS["panel_alt"],
            fg=COLORS["text"],
            insertbackground=COLORS["cyan"],
            relief="flat",
            font=("Segoe UI", 11),
        )
        self.search_entry.pack(side="left", fill="x", expand=True, ipady=7)
        tk.Label(
            search_frame,
            text="name · phone · email · group:family",
            bg=COLORS["panel_alt"],
            fg=COLORS["muted"],
            font=("Segoe UI", 8),
        ).pack(side="right", padx=12)
        self.search_var.trace_add("write", self._on_search_changed)

        actions = tk.Frame(header, bg=COLORS["panel"])
        actions.grid(row=0, column=2, padx=(6, 18), pady=15, sticky="e")
        self._button(actions, "＋ New", self.open_contact_form, accent=True).pack(
            side="left", padx=4
        )
        self._button(actions, "⚙", lambda: self.show_page("settings"), width=4).pack(
            side="left", padx=4
        )

        sidebar = tk.Frame(
            self,
            bg=COLORS["panel"],
            width=218,
            highlightbackground=COLORS["line"],
            highlightthickness=1,
        )
        sidebar.grid(row=1, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        tk.Label(
            sidebar,
            text="WORKSPACE",
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", padx=18, pady=(20, 8))
        navigation = [
            ("home", "⌂  Home"),
            ("all", "◉  All Contacts"),
            ("favorites", "♥  Favorites"),
            ("recent", "◷  Recent"),
            ("groups", "▣  Groups"),
            ("tags", "◇  Tags"),
            ("trash", "♻  Recycle Bin"),
        ]
        for page, label in navigation:
            self._add_nav_button(sidebar, page, label)
        tk.Label(
            sidebar,
            text="INSIGHTS",
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", padx=18, pady=(20, 8))
        for page, label in [
            ("duplicates", "⌘  Duplicates"),
            ("timeline", "◴  Timeline"),
            ("smart", "✦  Smart Groups"),
            ("relationships", "⌘  Relationships"),
        ]:
            self._add_nav_button(sidebar, page, label)
        tk.Label(
            sidebar,
            text="TOOLS",
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", padx=18, pady=(20, 8))
        for page, label in [("transfer", "⇅  Import / Export"), ("settings", "⚙  Settings")]:
            self._add_nav_button(sidebar, page, label)

        self.content = tk.Frame(self, bg=COLORS["bg"])
        self.content.grid(row=1, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)
        status = tk.Label(
            self,
            textvariable=self.status_var,
            anchor="w",
            bg="#050b14",
            fg=COLORS["muted"],
            font=("Segoe UI", 9),
            padx=14,
            pady=7,
        )
        status.grid(row=2, column=0, columnspan=2, sticky="ew")

    def _add_nav_button(self, parent: tk.Frame, page: str, label: str) -> None:
        button = tk.Button(
            parent,
            text=label,
            command=lambda: self.show_page(page),
            anchor="w",
            padx=18,
            pady=8,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            activebackground=COLORS["panel_hover"],
            activeforeground=COLORS["text"],
            relief="flat",
            bd=0,
            font=("Segoe UI", 10),
        )
        button.pack(fill="x", padx=8, pady=1)
        self.nav_buttons[page] = button

    def _button(
        self,
        parent: tk.Misc,
        text: str,
        command,
        accent: bool = False,
        danger: bool = False,
        width: int | None = None,
    ) -> tk.Button:
        if danger:
            bg, fg, active = "#4a2030", COLORS["danger"], "#683044"
        elif accent:
            bg, fg, active = "#12689a", "#ffffff", "#1988bd"
        else:
            bg, fg, active = COLORS["panel_alt"], COLORS["text"], COLORS["panel_hover"]
        options = {
            "text": text,
            "command": command,
            "bg": bg,
            "fg": fg,
            "activebackground": active,
            "activeforeground": "#ffffff",
            "relief": "flat",
            "bd": 0,
            "padx": 12,
            "pady": 7,
            "font": ("Segoe UI", 9, "bold"),
            "cursor": "hand2",
        }
        if width is not None:
            options["width"] = width
        return tk.Button(parent, **options)

    def _label(
        self, parent: tk.Misc, text: str, size: int = 10, color: str = "text", bold: bool = False
    ) -> tk.Label:
        return tk.Label(
            parent,
            text=text,
            bg=parent.cget("bg"),
            fg=COLORS[color],
            font=("Segoe UI", size, "bold" if bold else "normal"),
        )

    def _clear_content(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()
        self.tree = None
        self.preview = None
        self.card_vars.clear()
        self.selected_ids.clear()

    def _set_nav_active(self) -> None:
        for page, button in self.nav_buttons.items():
            active = page == self.current_page or (
                self.current_page == "group-detail" and page == "groups"
            )
            button.configure(
                bg=COLORS["panel_hover"] if active else COLORS["panel"],
                fg=COLORS["cyan"] if active else COLORS["muted"],
            )

    def show_page(self, page: str, group_id: str | None = None) -> None:
        self.current_page = page
        self.current_group_id = group_id
        self._set_nav_active()
        self._clear_content()
        builders = {
            "home": self.build_home,
            "all": lambda: self.build_contact_page("all", "All Contacts"),
            "favorites": lambda: self.build_contact_page("favorites", "Favorites"),
            "recent": lambda: self.build_contact_page("recent", "Recently Viewed"),
            "group-detail": lambda: self.build_contact_page(
                "group",
                self.service.get_group(group_id).name
                if group_id and self.service.get_group(group_id)
                else "Group",
                group_id,
            ),
            "ungrouped": lambda: self.build_contact_page("ungrouped", "Ungrouped Contacts"),
            "groups": self.build_groups,
            "tags": self.build_tags,
            "trash": self.build_trash,
            "duplicates": self.build_duplicates,
            "timeline": self.build_timeline,
            "smart": self.build_smart_groups,
            "relationships": self.build_relationships,
            "transfer": self.build_transfer,
            "settings": self.build_settings,
        }
        builder = builders.get(page, self.build_home)
        builder()

    def _bind_shortcuts(self) -> None:
        self.bind("<Control-f>", lambda _event: (self.search_entry.focus_set(), "break")[1])
        self.bind("<Control-n>", lambda _event: (self.open_contact_form(), "break")[1])
        self.bind("<Control-a>", self.select_all)
        self.bind("<Delete>", lambda _event: (self.delete_selected(), "break")[1])
        self.bind(
            "<Escape>",
            lambda _event: (self.selected_ids.clear(), self.refresh_current(), "break")[2],
        )

    def _on_search_changed(self, *_args) -> None:
        if self._search_after_id:
            self.after_cancel(self._search_after_id)
        self._search_after_id = self.after(180, self.refresh_current)

    def refresh_current(self) -> None:
        if self.current_page in {"all", "favorites", "recent", "group-detail", "ungrouped"}:
            page, group = self.current_page, self.current_group_id
            if page == "group-detail":
                self.show_page("group-detail", group)
            else:
                self.show_page(page)
        elif self.current_page == "groups":
            self.show_page("groups")
        elif self.current_page == "home":
            self.show_page("home")

    def set_status(self, text: str) -> None:
        self.status_var.set(text)

    # ── Home dashboard ─────────────────────────────────────────────────

    def build_home(self) -> None:
        outer = tk.Frame(self.content, bg=COLORS["bg"])
        outer.grid(row=0, column=0, sticky="nsew", padx=28, pady=24)
        outer.grid_columnconfigure(0, weight=1)
        title = tk.Frame(outer, bg=COLORS["bg"])
        title.grid(row=0, column=0, sticky="ew")
        self._label(title, "Good to see you", 11, "muted").pack(anchor="w")
        self._label(title, "Your contact workspace", 25, "text", True).pack(anchor="w", pady=(2, 0))
        self._label(
            title, "Offline-first · private · organized like a file explorer", 10, "cyan"
        ).pack(anchor="w", pady=(5, 0))

        stats = self.service.stats()
        stat_frame = tk.Frame(outer, bg=COLORS["bg"])
        stat_frame.grid(row=1, column=0, sticky="ew", pady=(24, 20))
        for index, (label, key, color) in enumerate(
            (
                ("Contacts", "contacts", "blue"),
                ("Favorites", "favorites", "pink"),
                ("Groups", "groups", "purple"),
                ("In Recycle Bin", "trash", "amber"),
            )
        ):
            stat_frame.grid_columnconfigure(index, weight=1)
            card = tk.Frame(
                stat_frame,
                bg=COLORS["panel"],
                highlightbackground=COLORS["line"],
                highlightthickness=1,
            )
            card.grid(
                row=0,
                column=index,
                sticky="ew",
                padx=(0 if index == 0 else 7, 7 if index < 3 else 0),
            )
            tk.Label(
                card,
                text=label.upper(),
                bg=COLORS["panel"],
                fg=COLORS["muted"],
                font=("Segoe UI", 8, "bold"),
            ).pack(anchor="w", padx=14, pady=(12, 3))
            tk.Label(
                card,
                text=str(stats[key]),
                bg=COLORS["panel"],
                fg=COLORS[color],
                font=("Segoe UI", 23, "bold"),
            ).pack(anchor="w", padx=14, pady=(0, 12))

        section = tk.Frame(outer, bg=COLORS["bg"])
        section.grid(row=2, column=0, sticky="nsew")
        section.grid_columnconfigure(0, weight=3)
        section.grid_columnconfigure(1, weight=2)
        groups_panel = tk.Frame(section, bg=COLORS["bg"])
        groups_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        self._section_heading(
            groups_panel, "Groups", "Browse your contact folders", lambda: self.show_page("groups")
        )
        group_grid = tk.Frame(groups_panel, bg=COLORS["bg"])
        group_grid.pack(fill="x", pady=(10, 0))
        for index, group in enumerate(self.service.list_groups()[:8]):
            group_grid.grid_columnconfigure(index % 2, weight=1)
            card = tk.Frame(
                group_grid,
                bg=COLORS["panel"],
                highlightbackground=COLORS["line"],
                highlightthickness=1,
                cursor="hand2",
            )
            card.grid(
                row=index // 2,
                column=index % 2,
                sticky="ew",
                padx=(0 if index % 2 == 0 else 6, 6 if index % 2 == 0 else 0),
                pady=5,
            )
            card.bind(
                "<Button-1>", lambda _event, gid=group.id: self.show_page("group-detail", gid)
            )
            tk.Label(
                card, text="▣", bg=COLORS["panel"], fg=COLORS["cyan"], font=("Segoe UI", 20)
            ).pack(side="left", padx=13, pady=12)
            info = tk.Frame(card, bg=COLORS["panel"])
            info.pack(side="left", fill="x", expand=True, pady=10)
            tk.Label(
                info,
                text=group.name,
                bg=COLORS["panel"],
                fg=COLORS["text"],
                font=("Segoe UI", 10, "bold"),
                anchor="w",
            ).pack(fill="x")
            tk.Label(
                info,
                text=f"{group.contact_count} contacts",
                bg=COLORS["panel"],
                fg=COLORS["muted"],
                font=("Segoe UI", 9),
                anchor="w",
            ).pack(fill="x", pady=(2, 0))
        if not self.service.list_groups():
            self._label(
                group_grid, "Create your first group to organize contacts.", 10, "muted"
            ).pack(pady=20)

        quick = tk.Frame(section, bg=COLORS["bg"])
        quick.grid(row=0, column=1, sticky="nsew")
        self._section_heading(
            quick, "Quick Access", "Recently viewed contacts", lambda: self.show_page("recent")
        )
        recent = self.service.recent_contacts(5)
        if not recent:
            self._empty(
                quick, "No recent contacts yet", "Open a contact and it will appear here."
            ).pack(fill="x", pady=12)
        else:
            for contact in recent:
                self._mini_contact(quick, contact)
        self._section_heading(
            quick,
            "Favorites",
            "Pinned for one-tap access",
            lambda: self.show_page("favorites"),
            pady=(22, 0),
        )
        favorites = self.service.favorite_contacts()[:4]
        if not favorites:
            self._label(quick, "No favorites yet.", 10, "muted").pack(anchor="w", pady=12)
        else:
            for contact in favorites:
                self._mini_contact(quick, contact)

    def _section_heading(
        self, parent: tk.Frame, title: str, subtitle: str, command, pady=(0, 0)
    ) -> None:
        row = tk.Frame(parent, bg=COLORS["bg"])
        row.pack(fill="x", pady=pady)
        info = tk.Frame(row, bg=COLORS["bg"])
        info.pack(side="left")
        tk.Label(
            info, text=title, bg=COLORS["bg"], fg=COLORS["text"], font=("Segoe UI", 15, "bold")
        ).pack(anchor="w")
        tk.Label(
            info, text=subtitle, bg=COLORS["bg"], fg=COLORS["muted"], font=("Segoe UI", 9)
        ).pack(anchor="w", pady=(2, 0))
        self._button(row, "View all →", command).pack(side="right", pady=2)

    def _mini_contact(self, parent: tk.Frame, contact: Contact) -> None:
        row = tk.Frame(
            parent,
            bg=COLORS["panel"],
            highlightbackground=COLORS["line"],
            highlightthickness=1,
            cursor="hand2",
        )
        row.pack(fill="x", pady=4)
        row.bind("<Button-1>", lambda _event, cid=contact.id: self.open_contact_preview(cid))
        tk.Label(
            row,
            text=initials(contact.name),
            width=4,
            pady=7,
            bg="#155b82",
            fg="#ffffff",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left", padx=8, pady=7)
        info = tk.Frame(row, bg=COLORS["panel"])
        info.pack(side="left", fill="x", expand=True, pady=7)
        tk.Label(
            info,
            text=contact.name,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            info,
            text=contact.primary_phone or contact.primary_email or "No phone or email",
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill="x", pady=(2, 0))
        if contact.is_favorite:
            tk.Label(
                row, text="♥", bg=COLORS["panel"], fg=COLORS["pink"], font=("Segoe UI", 12)
            ).pack(side="right", padx=10)

    def _empty(self, parent: tk.Misc, title: str, message: str) -> tk.Frame:
        frame = tk.Frame(
            parent, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1
        )
        tk.Label(
            frame, text=title, bg=COLORS["panel"], fg=COLORS["text"], font=("Segoe UI", 11, "bold")
        ).pack(pady=(22, 4), padx=18)
        tk.Label(
            frame,
            text=message,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9),
            wraplength=320,
        ).pack(pady=(0, 22), padx=18)
        return frame

    # ── Contact explorer views ──────────────────────────────────────────

    def build_contact_page(self, mode: str, title: str, group_id: str | None = None) -> None:
        outer = tk.Frame(self.content, bg=COLORS["bg"])
        outer.grid(row=0, column=0, sticky="nsew", padx=24, pady=20)
        outer.grid_rowconfigure(1, weight=1)
        outer.grid_columnconfigure(0, weight=1)

        toolbar = tk.Frame(outer, bg=COLORS["bg"])
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        toolbar.grid_columnconfigure(0, weight=1)
        heading = tk.Frame(toolbar, bg=COLORS["bg"])
        heading.grid(row=0, column=0, sticky="w")
        self._label(heading, title, 20, "text", True).pack(anchor="w")
        contacts = self._contacts_for_page(mode, group_id)
        self._label(
            heading, f"{len(contacts)} contact" + ("s" if len(contacts) != 1 else ""), 9, "muted"
        ).pack(anchor="w", pady=(3, 0))

        controls = tk.Frame(toolbar, bg=COLORS["bg"])
        controls.grid(row=0, column=1, sticky="e")
        tk.Label(
            controls, text="Sort", bg=COLORS["bg"], fg=COLORS["muted"], font=("Segoe UI", 9)
        ).pack(side="left", padx=(0, 5))
        sort_box = ttk.Combobox(
            controls,
            textvariable=self.sort_mode,
            state="readonly",
            width=18,
            values=(
                "Best match",
                "Name A to Z",
                "Name Z to A",
                "Recently modified",
                "Most contacted",
                "Least contacted",
                "Company",
            ),
        )
        sort_box.pack(side="left", padx=4)
        sort_box.bind("<<ComboboxSelected>>", lambda _event: self.refresh_current())
        self._button(
            controls,
            "☷ List",
            lambda: self._set_view("list"),
            accent=self.view_mode.get() == "list",
        ).pack(side="left", padx=3)
        self._button(
            controls,
            "▦ Cards",
            lambda: self._set_view("cards"),
            accent=self.view_mode.get() == "cards",
        ).pack(side="left", padx=3)
        self._button(controls, "＋ Add", self.open_contact_form, accent=True).pack(
            side="left", padx=(9, 0)
        )

        pane = ttk.PanedWindow(outer, orient="horizontal")
        pane.grid(row=1, column=0, sticky="nsew")
        left = tk.Frame(pane, bg=COLORS["bg"])
        right = tk.Frame(
            pane, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1
        )
        pane.add(left, weight=3)
        pane.add(right, weight=2)
        self.preview = right
        self._bulk_bar(left)

        list_area = tk.Frame(left, bg=COLORS["bg"])
        list_area.pack(fill="both", expand=True, pady=(10, 0))
        if not contacts:
            self._empty(
                list_area, "Nothing here yet", "Try a different search or add a new contact."
            ).pack(fill="x", pady=20)
        elif self.view_mode.get() == "cards":
            self._build_card_view(list_area, contacts)
        else:
            self._build_tree_view(list_area, contacts)
        self._show_preview(None)

    def _set_view(self, mode: str) -> None:
        self.view_mode.set(mode)
        self.refresh_current()

    def _contacts_for_page(self, mode: str, group_id: str | None = None) -> list[Contact]:
        if mode == "favorites":
            contacts = self.service.favorite_contacts()
        elif mode == "recent":
            contacts = self.service.recent_contacts()
        elif mode == "group":
            contacts = self.service.contacts_in_group(group_id or "") if group_id else []
        elif mode == "ungrouped":
            contacts = self.service.ungrouped_contacts()
        else:
            contacts = self.service.list_contacts()
        query = self.search_var.get().strip()
        if query:
            contacts = self.service.search_contacts(query, contacts)
        sort_mode = self.sort_mode.get()
        if sort_mode == "Name A to Z":
            contacts.sort(key=lambda item: item.name.casefold())
        elif sort_mode == "Name Z to A":
            contacts.sort(key=lambda item: item.name.casefold(), reverse=True)
        elif sort_mode == "Recently modified":
            contacts.sort(key=lambda item: item.updated_at, reverse=True)
        elif sort_mode == "Most contacted":
            contacts.sort(key=lambda item: item.times_contacted, reverse=True)
        elif sort_mode == "Least contacted":
            contacts.sort(key=lambda item: item.times_contacted)
        elif sort_mode == "Company":
            contacts.sort(key=lambda item: (item.company.casefold(), item.name.casefold()))
        return contacts

    def _build_tree_view(self, parent: tk.Frame, contacts: list[Contact]) -> None:
        frame = tk.Frame(
            parent, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1
        )
        frame.pack(fill="both", expand=True)
        columns = ("name", "phone", "email", "company", "groups", "tags")
        tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="extended")
        headings = {
            "name": "Name",
            "phone": "Phone",
            "email": "Email",
            "company": "Company",
            "groups": "Groups",
            "tags": "Tags",
        }
        widths = {
            "name": 165,
            "phone": 145,
            "email": 190,
            "company": 130,
            "groups": 145,
            "tags": 125,
        }
        for column in columns:
            tree.heading(column, text=headings[column])
            tree.column(column, width=widths[column], minwidth=70, anchor="w")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        for contact in contacts:
            tree.insert(
                "",
                "end",
                iid=contact.id,
                values=(
                    contact.name,
                    contact.primary_phone,
                    contact.primary_email,
                    contact.company or "—",
                    ", ".join(contact.groups) or "—",
                    ", ".join(contact.tags) or "—",
                ),
            )
        self.tree = tree
        tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        tree.bind("<Double-1>", lambda _event: self._edit_first_selected())
        tree.bind("<Button-3>", self._context_menu)

    def _build_card_view(self, parent: tk.Frame, contacts: list[Contact]) -> None:
        canvas = tk.Canvas(parent, bg=COLORS["bg"], highlightthickness=0)
        scroll = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=COLORS["bg"])
        inner.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        for index, contact in enumerate(contacts):
            inner.grid_columnconfigure(index % 2, weight=1)
            card = tk.Frame(
                inner, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1
            )
            card.grid(
                row=index // 2,
                column=index % 2,
                sticky="nsew",
                padx=(0 if index % 2 == 0 else 6, 6 if index % 2 == 0 else 0),
                pady=6,
            )
            selected = tk.BooleanVar(value=contact.id in self.selected_ids)
            self.card_vars[contact.id] = selected
            top = tk.Frame(card, bg=COLORS["panel"])
            top.pack(fill="x", padx=12, pady=(10, 5))
            tk.Label(
                top,
                text=initials(contact.name),
                width=4,
                pady=8,
                bg="#155b82",
                fg="#ffffff",
                font=("Segoe UI", 12, "bold"),
            ).pack(side="left")
            info = tk.Frame(top, bg=COLORS["panel"])
            info.pack(side="left", fill="x", expand=True, padx=10)
            tk.Label(
                info,
                text=contact.name,
                bg=COLORS["panel"],
                fg=COLORS["text"],
                font=("Segoe UI", 11, "bold"),
                anchor="w",
            ).pack(fill="x")
            tk.Label(
                info,
                text=contact.company or "No company",
                bg=COLORS["panel"],
                fg=COLORS["muted"],
                font=("Segoe UI", 9),
                anchor="w",
            ).pack(fill="x", pady=(3, 0))
            tk.Checkbutton(
                top,
                variable=selected,
                command=self._on_card_selection,
                bg=COLORS["panel"],
                activebackground=COLORS["panel"],
                fg=COLORS["cyan"],
                selectcolor=COLORS["panel_alt"],
            ).pack(side="right")
            details = tk.Frame(card, bg=COLORS["panel"])
            details.pack(fill="x", padx=12, pady=(3, 9))
            tk.Label(
                details,
                text=contact.primary_phone or "No phone",
                bg=COLORS["panel"],
                fg=COLORS["text"],
                font=("Segoe UI", 9),
                anchor="w",
            ).pack(fill="x")
            tk.Label(
                details,
                text=contact.primary_email or "No email",
                bg=COLORS["panel"],
                fg=COLORS["muted"],
                font=("Segoe UI", 9),
                anchor="w",
            ).pack(fill="x", pady=(2, 0))
            actions = tk.Frame(card, bg=COLORS["panel_alt"])
            actions.pack(fill="x")
            self._button(
                actions, "Open", lambda cid=contact.id: self.open_contact_preview(cid)
            ).pack(side="left", padx=7, pady=6)
            self._button(
                actions,
                "♥" if contact.is_favorite else "♡",
                lambda cid=contact.id: self.toggle_favorite(cid),
                danger=contact.is_favorite,
            ).pack(side="right", padx=7, pady=6)

    def _bulk_bar(self, parent: tk.Frame) -> None:
        bar = tk.Frame(
            parent, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1
        )
        bar.pack(fill="x")
        self.bulk_count = tk.StringVar(value="0 selected")
        tk.Label(
            bar,
            textvariable=self.bulk_count,
            bg=COLORS["panel"],
            fg=COLORS["cyan"],
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=11, pady=8)
        for text, command in (
            ("Group", self.bulk_group),
            ("Tag", self.bulk_tag),
            ("Share", self.share_selected),
            ("Delete", self.delete_selected),
        ):
            self._button(bar, text, command, danger=text == "Delete").pack(
                side="right", padx=3, pady=4
            )
        self._button(bar, "Select all", self.select_all).pack(side="right", padx=3, pady=4)

    def _on_tree_select(self, _event=None) -> None:
        if self.tree is None:
            return
        self.selected_ids = set(self.tree.selection())
        self._update_selection_label()
        if len(self.selected_ids) == 1:
            self._show_preview(self.service.get_contact(next(iter(self.selected_ids))))
        elif len(self.selected_ids) == 0:
            self._show_preview(None)
        else:
            self._show_preview(None, f"{len(self.selected_ids)} contacts selected")

    def _on_card_selection(self) -> None:
        self.selected_ids = {
            contact_id for contact_id, variable in self.card_vars.items() if variable.get()
        }
        self._update_selection_label()
        if len(self.selected_ids) == 1:
            self._show_preview(self.service.get_contact(next(iter(self.selected_ids))))

    def _update_selection_label(self) -> None:
        if hasattr(self, "bulk_count"):
            count = len(self.selected_ids)
            self.bulk_count.set(f"{count} selected" if count else "Select contacts")

    def select_all(self, _event=None):
        if self.tree is not None:
            self.tree.selection_set(self.tree.get_children())
            self._on_tree_select()
        elif self.card_vars:
            for variable in self.card_vars.values():
                variable.set(True)
            self._on_card_selection()
        return "break"

    def clear_selection(self) -> None:
        self.selected_ids.clear()
        if self.tree is not None:
            self.tree.selection_remove(self.tree.selection())
        for variable in self.card_vars.values():
            variable.set(False)
        self._update_selection_label()

    def _show_preview(self, contact: Contact | None, message: str | None = None) -> None:
        if self.preview is None:
            return
        for child in self.preview.winfo_children():
            child.destroy()
        if message:
            self._label(self.preview, message, 15, "cyan", True).pack(
                anchor="w", padx=22, pady=(28, 4)
            )
            self._label(
                self.preview, "Use the toolbar below the list for bulk operations.", 10, "muted"
            ).pack(anchor="w", padx=22)
            return
        if contact is None:
            self._label(self.preview, "Contact Preview", 16, "text", True).pack(
                anchor="w", padx=22, pady=(28, 5)
            )
            self._label(
                self.preview,
                "Select a contact to inspect details, call, message, share or edit it.",
                10,
                "muted",
            ).pack(anchor="w", padx=22, pady=(0, 20))
            return
        self.service.record_viewed(contact.id)
        header = tk.Frame(self.preview, bg=COLORS["panel"])
        header.pack(fill="x", padx=22, pady=(25, 12))
        tk.Label(
            header,
            text=initials(contact.name),
            width=5,
            pady=14,
            bg="#155b82",
            fg="#ffffff",
            font=("Segoe UI", 18, "bold"),
        ).pack(side="left")
        info = tk.Frame(header, bg=COLORS["panel"])
        info.pack(side="left", fill="x", expand=True, padx=12)
        tk.Label(
            info,
            text=contact.name,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=("Segoe UI", 16, "bold"),
            anchor="w",
            wraplength=250,
        ).pack(fill="x")
        tk.Label(
            info,
            text="♥ Favorite" if contact.is_favorite else "Contact details",
            bg=COLORS["panel"],
            fg=COLORS["pink"] if contact.is_favorite else COLORS["muted"],
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill="x", pady=(3, 0))
        actions = tk.Frame(self.preview, bg=COLORS["panel"])
        actions.pack(fill="x", padx=22, pady=(0, 16))
        self._button(actions, "Edit", lambda: self.open_contact_form(contact), accent=True).pack(
            side="left", padx=(0, 5)
        )
        self._button(actions, "Favorite", lambda: self.toggle_favorite(contact.id)).pack(
            side="left", padx=5
        )
        self._button(actions, "Share", lambda: self.share_contacts([contact.id])).pack(
            side="left", padx=5
        )
        self._button(
            actions, "Delete", lambda: self.delete_contacts([contact.id]), danger=True
        ).pack(side="left", padx=5)
        self._detail_section(
            contact,
            "PHONE NUMBERS",
            [(phone.number, phone.label, phone.number) for phone in contact.phones],
            phone_actions=True,
        )
        self._detail_section(
            contact,
            "EMAIL ADDRESSES",
            [(email.email, email.label, None) for email in contact.emails],
        )
        for label, value in (
            ("COMPANY", contact.company),
            ("ADDRESS", contact.address),
            ("NOTES", contact.note),
            ("GROUPS", ", ".join(contact.groups)),
            ("TAGS", ", ".join(contact.tags)),
        ):
            if value:
                self._detail_section(contact, label, [(value, "", None)])

    def _detail_section(
        self,
        contact: Contact,
        title: str,
        rows: list[tuple[str, str, str | None]],
        phone_actions: bool = False,
    ) -> None:
        if self.preview is None or not rows:
            return
        frame = tk.Frame(self.preview, bg=COLORS["panel"])
        frame.pack(fill="x", padx=22, pady=(0, 13))
        tk.Label(
            frame, text=title, bg=COLORS["panel"], fg=COLORS["muted"], font=("Segoe UI", 8, "bold")
        ).pack(anchor="w", pady=(0, 5))
        for value, label, number in rows:
            row = tk.Frame(frame, bg=COLORS["panel_alt"])
            row.pack(fill="x", pady=2)
            text = f"{value}  ·  {label}" if label else value
            tk.Label(
                row,
                text=text,
                bg=COLORS["panel_alt"],
                fg=COLORS["text"],
                font=("Segoe UI", 9),
                anchor="w",
                wraplength=240,
            ).pack(side="left", fill="x", expand=True, padx=9, pady=7)
            if phone_actions and number:
                self._button(
                    row, "Call", lambda value=number, cid=contact.id: self.call_number(value, cid)
                ).pack(side="right", padx=3, pady=3)
                self._button(row, "SMS", lambda value=number: self.message_number(value)).pack(
                    side="right", padx=3, pady=3
                )

    def open_contact_preview(self, contact_id: str) -> None:
        if self.preview is None:
            self.show_page("all")
            self.after(50, lambda: self._show_preview(self.service.get_contact(contact_id)))
        else:
            self._show_preview(self.service.get_contact(contact_id))

    def _edit_first_selected(self) -> None:
        if len(self.selected_ids) == 1:
            self.open_contact_form(self.service.get_contact(next(iter(self.selected_ids))))

    # ── Contact actions and forms ───────────────────────────────────────

    def call_number(self, number: str, contact_id: str | None = None) -> None:
        clean = number.strip()
        if not clean:
            return
        if contact_id:
            self.service.record_call(contact_id)
        webbrowser.open(f"tel:{clean.replace(' ', '')}")
        self.set_status(f"Call action opened for {clean}")

    def message_number(self, number: str) -> None:
        clean = number.strip()
        if clean:
            webbrowser.open(f"sms:{clean.replace(' ', '')}")
            self.set_status(f"Message action opened for {clean}")

    def toggle_favorite(self, contact_id: str) -> None:
        try:
            favorite = self.service.toggle_favorite(contact_id)
            self.set_status("Added to Favorites" if favorite else "Removed from Favorites")
            self.refresh_current()
        except ValueError as exc:
            messagebox.showerror("Favorite", str(exc), parent=self)

    def share_contacts(self, contact_ids: list[str]) -> None:
        text = self.service.share_text(contact_ids)
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.service.record_share(contact_ids)
        self.set_status("Contact details copied to clipboard")

    def share_selected(self) -> None:
        self.share_contacts(list(self.selected_ids))

    def delete_contacts(self, contact_ids: list[str]) -> None:
        ids = [str(item) for item in contact_ids if item]
        if not ids:
            return
        if not messagebox.askyesno(
            "Move to Recycle Bin",
            f"Move {len(ids)} contact(s) to the Recycle Bin?\nThey can be restored for 30 days.",
            parent=self,
        ):
            return
        count = self.service.delete_contacts(ids)
        self.set_status(f"Moved {count} contact(s) to Recycle Bin")
        self.refresh_current()

    def delete_selected(self) -> None:
        self.delete_contacts(list(self.selected_ids))

    def open_contact_form(
        self, contact: Contact | None = None, preselected_group: str | None = None
    ) -> None:
        if preselected_group is None and self.current_page == "group-detail":
            preselected_group = self.current_group_id
        dialog = tk.Toplevel(self)
        dialog.title("Edit Contact" if contact else "New Contact")
        dialog.geometry("690x760")
        dialog.minsize(580, 620)
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self)
        dialog.grab_set()

        canvas = tk.Canvas(dialog, bg=COLORS["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        body = tk.Frame(canvas, bg=COLORS["bg"])
        body.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=body, anchor="nw", width=650)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(20, 0), pady=16)
        scrollbar.pack(side="right", fill="y", padx=(0, 10), pady=16)

        tk.Label(
            body,
            text="Edit Contact" if contact else "New Contact",
            bg=COLORS["bg"],
            fg=COLORS["text"],
            font=("Segoe UI", 20, "bold"),
        ).pack(anchor="w", pady=(0, 4))
        tk.Label(
            body,
            text="Keep the details useful; every field remains on this device.",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(0, 18))

        variables: dict[str, tk.StringVar] = {
            key: tk.StringVar(value=value)
            for key, value in {
                "name": contact.name if contact else "",
                "company": contact.company if contact else "",
                "address": contact.address if contact else "",
                "note": contact.note if contact else "",
                "tags": ", ".join(contact.tags) if contact else "",
            }.items()
        }
        self._form_field(body, "Full name *", variables["name"], "e.g. Rahul Sharma")
        self._form_field(body, "Company / College", variables["company"], "Optional")
        self._form_field(body, "Address / City", variables["address"], "Optional")

        tk.Label(
            body,
            text="PHONE NUMBERS",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", pady=(16, 6))
        phone_frame = tk.Frame(body, bg=COLORS["bg"])
        phone_frame.pack(fill="x")
        phone_rows: list[tuple[tk.Frame, tk.StringVar, tk.StringVar]] = []

        def add_phone(number: str = "", label: str = "Mobile") -> None:
            row = tk.Frame(phone_frame, bg=COLORS["bg"])
            row.pack(fill="x", pady=3)
            label_var, number_var = tk.StringVar(value=label), tk.StringVar(value=number)
            tk.Entry(
                row,
                textvariable=label_var,
                width=13,
                bg=COLORS["panel"],
                fg=COLORS["text"],
                insertbackground=COLORS["cyan"],
                relief="flat",
            ).pack(side="left", ipady=7, padx=(0, 7))
            tk.Entry(
                row,
                textvariable=number_var,
                bg=COLORS["panel"],
                fg=COLORS["text"],
                insertbackground=COLORS["cyan"],
                relief="flat",
            ).pack(side="left", fill="x", expand=True, ipady=7)
            remove = self._button(
                row, "×", lambda current=row: remove_phone(current), danger=True, width=3
            )
            remove.pack(side="right", padx=(7, 0))
            phone_rows.append((row, label_var, number_var))

        def remove_phone(row: tk.Frame) -> None:
            if len(phone_rows) <= 1:
                return
            row.destroy()
            phone_rows[:] = [item for item in phone_rows if item[0] is not row]

        if contact and contact.phones:
            for item in contact.phones:
                add_phone(item.number, item.label)
        else:
            add_phone()
        self._button(body, "＋ Add phone number", add_phone).pack(anchor="w", pady=(4, 10))

        tk.Label(
            body,
            text="EMAIL ADDRESSES",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", pady=(8, 6))
        email_frame = tk.Frame(body, bg=COLORS["bg"])
        email_frame.pack(fill="x")
        email_rows: list[tuple[tk.Frame, tk.StringVar, tk.StringVar]] = []

        def add_email(address: str = "", label: str = "Home") -> None:
            row = tk.Frame(email_frame, bg=COLORS["bg"])
            row.pack(fill="x", pady=3)
            label_var, email_var = tk.StringVar(value=label), tk.StringVar(value=address)
            tk.Entry(
                row,
                textvariable=label_var,
                width=13,
                bg=COLORS["panel"],
                fg=COLORS["text"],
                insertbackground=COLORS["cyan"],
                relief="flat",
            ).pack(side="left", ipady=7, padx=(0, 7))
            tk.Entry(
                row,
                textvariable=email_var,
                bg=COLORS["panel"],
                fg=COLORS["text"],
                insertbackground=COLORS["cyan"],
                relief="flat",
            ).pack(side="left", fill="x", expand=True, ipady=7)
            self._button(
                row, "×", lambda current=row: remove_email(current), danger=True, width=3
            ).pack(side="right", padx=(7, 0))
            email_rows.append((row, label_var, email_var))

        def remove_email(row: tk.Frame) -> None:
            if len(email_rows) <= 1:
                return
            row.destroy()
            email_rows[:] = [item for item in email_rows if item[0] is not row]

        if contact and contact.emails:
            for item in contact.emails:
                add_email(item.email, item.label)
        else:
            add_email()
        self._button(body, "＋ Add email address", add_email).pack(anchor="w", pady=(4, 10))

        self._form_field(body, "Notes", variables["note"], "Optional")
        self._form_field(body, "Tags", variables["tags"], "Comma separated, e.g. urgent, client")

        tk.Label(
            body, text="GROUPS", bg=COLORS["bg"], fg=COLORS["muted"], font=("Segoe UI", 9, "bold")
        ).pack(anchor="w", pady=(16, 6))
        group_frame = tk.Frame(body, bg=COLORS["panel"])
        group_frame.pack(fill="x")
        group_vars: dict[str, tk.BooleanVar] = {}
        for group in self.service.list_groups():
            variable = tk.BooleanVar(
                value=(
                    group.name in (contact.groups if contact else [])
                    or group.id == preselected_group
                )
            )
            group_vars[group.id] = variable
            tk.Checkbutton(
                group_frame,
                text=group.name,
                variable=variable,
                bg=COLORS["panel"],
                activebackground=COLORS["panel"],
                fg=COLORS["text"],
                selectcolor=COLORS["panel_alt"],
                anchor="w",
            ).pack(side="left", padx=10, pady=8)
        if not group_vars:
            tk.Label(
                group_frame,
                text="No groups yet — create one from the Groups page.",
                bg=COLORS["panel"],
                fg=COLORS["muted"],
                font=("Segoe UI", 9),
            ).pack(anchor="w", padx=10, pady=10)

        favorite_var = tk.BooleanVar(value=contact.is_favorite if contact else False)
        tk.Checkbutton(
            body,
            text="♥ Add to Favorites",
            variable=favorite_var,
            bg=COLORS["bg"],
            activebackground=COLORS["bg"],
            fg=COLORS["pink"],
            selectcolor=COLORS["panel_alt"],
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=(15, 7))
        error_var = tk.StringVar()
        tk.Label(
            body,
            textvariable=error_var,
            bg=COLORS["bg"],
            fg=COLORS["danger"],
            font=("Segoe UI", 9),
            wraplength=600,
        ).pack(anchor="w")

        buttons = tk.Frame(body, bg=COLORS["bg"])
        buttons.pack(fill="x", pady=(18, 20))
        self._button(buttons, "Cancel", dialog.destroy).pack(side="right", padx=5)

        def save() -> None:
            name = variables["name"].get().strip()
            if not name:
                error_var.set("Name is required.")
                return
            phones = [
                PhoneNumber(number_var.get().strip(), label_var.get().strip() or "Mobile")
                for _, label_var, number_var in phone_rows
                if number_var.get().strip()
            ]
            emails = [
                EmailAddress(email_var.get().strip(), label_var.get().strip() or "Home")
                for _, label_var, email_var in email_rows
                if email_var.get().strip()
            ]
            groups = [
                group.name
                for group in self.service.list_groups()
                if group_vars.get(group.id) and group_vars[group.id].get()
            ]
            tags = [item.strip() for item in variables["tags"].get().split(",") if item.strip()]
            draft = ContactDraft(
                name=name,
                phones=phones,
                emails=emails,
                company=variables["company"].get(),
                address=variables["address"].get(),
                note=variables["note"].get(),
                groups=groups,
                tags=tags,
                is_favorite=favorite_var.get(),
            )
            try:
                self.service.save_contact(contact.id if contact else None, draft)
                dialog.destroy()
                self.set_status("Contact updated" if contact else "Contact created")
                self.refresh_current()
            except Exception as exc:
                error_var.set(str(exc))

        self._button(buttons, "Save Contact", save, accent=True).pack(side="right", padx=5)
        dialog.bind("<Control-Return>", lambda _event: save())

    def _form_field(
        self, parent: tk.Frame, label: str, variable: tk.StringVar, placeholder: str
    ) -> None:
        tk.Label(
            parent, text=label, bg=COLORS["bg"], fg=COLORS["muted"], font=("Segoe UI", 9, "bold")
        ).pack(anchor="w", pady=(8, 5))
        entry = tk.Entry(
            parent,
            textvariable=variable,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            insertbackground=COLORS["cyan"],
            relief="flat",
            font=("Segoe UI", 10),
        )
        entry.pack(fill="x", ipady=8)

    def _context_menu(self, event) -> None:
        if self.tree is None:
            return
        item = self.tree.identify_row(event.y)
        if item and item not in self.selected_ids:
            self.tree.selection_set(item)
            self._on_tree_select()
        if not item:
            return
        menu = tk.Menu(
            self,
            tearoff=0,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            activebackground=COLORS["panel_hover"],
            activeforeground=COLORS["text"],
        )
        ids = list(self.selected_ids)
        contact = self.service.get_contact(item)
        menu.add_command(label="Open contact", command=lambda: self.open_contact_preview(item))
        if contact and contact.primary_phone:
            menu.add_command(
                label="Call", command=lambda: self.call_number(contact.primary_phone, contact.id)
            )
            menu.add_command(
                label="Message", command=lambda: self.message_number(contact.primary_phone)
            )
        menu.add_separator()
        menu.add_command(label="Add / remove Favorite", command=lambda: self.toggle_favorite(item))
        menu.add_command(label="Move to Group…", command=self.bulk_group)
        menu.add_command(label="Add Tag…", command=self.bulk_tag)
        menu.add_command(label="Copy Share Text", command=self.share_selected)
        menu.add_command(label="Edit", command=lambda: self.open_contact_form(contact))
        menu.add_command(
            label="Delete", command=lambda: self.delete_contacts(ids), foreground=COLORS["danger"]
        )
        menu.tk_popup(event.x_root, event.y_root)

    def bulk_group(self) -> None:
        if not self.selected_ids:
            messagebox.showinfo("Move to Group", "Select one or more contacts first.", parent=self)
            return
        dialog = tk.Toplevel(self)
        dialog.title("Move Contacts to Group")
        dialog.geometry("420x430")
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self)
        dialog.grab_set()
        tk.Label(
            dialog,
            text=f"Move {len(self.selected_ids)} contact(s)",
            bg=COLORS["bg"],
            fg=COLORS["text"],
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w", padx=20, pady=(20, 4))
        tk.Label(
            dialog,
            text="Choose a group. Existing memberships will be replaced.",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=20, pady=(0, 13))
        choice = tk.StringVar()
        for group in self.service.list_groups():
            tk.Radiobutton(
                dialog,
                text=f"{group.name}  ({group.contact_count})",
                variable=choice,
                value=group.id,
                bg=COLORS["panel"],
                activebackground=COLORS["panel"],
                fg=COLORS["text"],
                selectcolor=COLORS["panel_alt"],
                anchor="w",
                padx=12,
                pady=7,
            ).pack(fill="x", padx=20, pady=2)
        tk.Label(
            dialog,
            text="Tip: use the New Group button to create folders for richer organization.",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=("Segoe UI", 8),
            wraplength=370,
        ).pack(anchor="w", padx=20, pady=12)
        buttons = tk.Frame(dialog, bg=COLORS["bg"])
        buttons.pack(side="bottom", fill="x", padx=20, pady=18)
        self._button(
            buttons, "Remove from groups", lambda: self._apply_bulk_group(dialog, None)
        ).pack(side="left")
        self._button(buttons, "Cancel", dialog.destroy).pack(side="right", padx=5)
        self._button(
            buttons, "Move", lambda: self._apply_bulk_group(dialog, choice.get()), accent=True
        ).pack(side="right", padx=5)

    def _apply_bulk_group(self, dialog: tk.Toplevel, group_id: str | None) -> None:
        if group_id:
            self.service.assign_groups(self.selected_ids, [group_id], replace=True)
        else:
            self.service.assign_groups(self.selected_ids, [], replace=True)
        dialog.destroy()
        self.set_status("Group memberships updated")
        self.refresh_current()

    def bulk_tag(self) -> None:
        if not self.selected_ids:
            messagebox.showinfo("Add Tag", "Select one or more contacts first.", parent=self)
            return
        dialog = tk.Toplevel(self)
        dialog.title("Add Tags")
        dialog.geometry("440x470")
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self)
        dialog.grab_set()
        tk.Label(
            dialog,
            text=f"Tag {len(self.selected_ids)} contact(s)",
            bg=COLORS["bg"],
            fg=COLORS["text"],
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w", padx=20, pady=(20, 4))
        tk.Label(
            dialog,
            text="Select existing tags or type a new one below.",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=20, pady=(0, 10))
        tag_vars: dict[str, tk.BooleanVar] = {}
        for tag in self.service.list_tags():
            variable = tk.BooleanVar()
            tag_vars[tag.id] = variable
            tk.Checkbutton(
                dialog,
                text=f"{tag.name}  ({tag.contact_count})",
                variable=variable,
                bg=COLORS["panel"],
                activebackground=COLORS["panel"],
                fg=COLORS["text"],
                selectcolor=COLORS["panel_alt"],
                anchor="w",
                padx=12,
                pady=6,
            ).pack(fill="x", padx=20, pady=2)
        new_tag = tk.StringVar()
        tk.Label(
            dialog,
            text="New tag",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", padx=20, pady=(13, 4))
        tk.Entry(
            dialog,
            textvariable=new_tag,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            insertbackground=COLORS["cyan"],
            relief="flat",
        ).pack(fill="x", padx=20, ipady=7)
        buttons = tk.Frame(dialog, bg=COLORS["bg"])
        buttons.pack(side="bottom", fill="x", padx=20, pady=18)
        self._button(buttons, "Cancel", dialog.destroy).pack(side="right", padx=5)

        def apply() -> None:
            ids = [tag_id for tag_id, variable in tag_vars.items() if variable.get()]
            if new_tag.get().strip():
                ids.append(self.service.create_tag(new_tag.get()).id)
            if ids:
                self.service.assign_tags(self.selected_ids, ids)
            dialog.destroy()
            self.set_status("Tags updated")
            self.refresh_current()

        self._button(buttons, "Apply Tags", apply, accent=True).pack(side="right", padx=5)

    # ── Groups, tags and recycle bin screens ────────────────────────────

    def build_groups(self) -> None:
        outer = tk.Frame(self.content, bg=COLORS["bg"])
        outer.grid(row=0, column=0, sticky="nsew", padx=28, pady=22)
        outer.grid_rowconfigure(1, weight=1)
        outer.grid_columnconfigure(0, weight=1)
        header = tk.Frame(outer, bg=COLORS["bg"])
        header.grid(row=0, column=0, sticky="ew", pady=(0, 17))
        self._label(header, "Groups", 21, "text", True).pack(side="left")
        self._button(header, "＋ New Group", self.open_group_form, accent=True).pack(
            side="right", padx=4
        )
        self._button(header, "⇄ Merge", self.merge_groups_dialog).pack(side="right", padx=4)
        self._button(header, "✦ Auto Group", self.auto_group).pack(side="right", padx=4)
        groups = self.service.list_groups()
        grid = tk.Frame(outer, bg=COLORS["bg"])
        grid.grid(row=1, column=0, sticky="nsew")
        for index, group in enumerate(groups):
            grid.grid_columnconfigure(index % 3, weight=1)
            card = tk.Frame(
                grid, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1
            )
            card.grid(
                row=index // 3,
                column=index % 3,
                sticky="nsew",
                padx=(0 if index % 3 == 0 else 6, 6 if index % 3 < 2 else 0),
                pady=6,
            )
            top = tk.Frame(card, bg=COLORS["panel"])
            top.pack(fill="x", padx=14, pady=(13, 4))
            tk.Label(
                top, text="▣", bg=COLORS["panel"], fg=COLORS["cyan"], font=("Segoe UI", 22)
            ).pack(side="left")
            tk.Label(
                top,
                text=group.name,
                bg=COLORS["panel"],
                fg=COLORS["text"],
                font=("Segoe UI", 12, "bold"),
                anchor="w",
                wraplength=180,
            ).pack(side="left", padx=10, fill="x", expand=True)
            body = tk.Frame(card, bg=COLORS["panel"])
            body.pack(fill="x", padx=14, pady=(2, 12))
            tk.Label(
                body,
                text=f"{group.contact_count} contact(s)",
                bg=COLORS["panel"],
                fg=COLORS["muted"],
                font=("Segoe UI", 9),
            ).pack(anchor="w")
            if group.parent_folder_id:
                parent = self.service.get_group(group.parent_folder_id)
                tk.Label(
                    body,
                    text=f"inside {parent.name}" if parent else "nested group",
                    bg=COLORS["panel"],
                    fg=COLORS["purple"],
                    font=("Segoe UI", 8),
                ).pack(anchor="w", pady=(3, 0))
            actions = tk.Frame(card, bg=COLORS["panel_alt"])
            actions.pack(fill="x")
            self._button(
                actions, "Open", lambda gid=group.id: self.show_page("group-detail", gid)
            ).pack(side="left", padx=7, pady=6)
            self._button(actions, "Rename", lambda item=group: self.open_group_form(item)).pack(
                side="left", padx=2, pady=6
            )
            self._button(
                actions, "Delete", lambda gid=group.id: self.delete_group(gid), danger=True
            ).pack(side="right", padx=7, pady=6)
        ungrouped = self.service.ungrouped_contacts()
        index = len(groups)
        grid.grid_columnconfigure(index % 3, weight=1)
        card = tk.Frame(
            grid, bg="#112338", highlightbackground=COLORS["purple"], highlightthickness=1
        )
        card.grid(
            row=index // 3,
            column=index % 3,
            sticky="nsew",
            padx=(0 if index % 3 == 0 else 6, 6 if index % 3 < 2 else 0),
            pady=6,
        )
        tk.Label(
            card,
            text="∅  Ungrouped Contacts",
            bg="#112338",
            fg=COLORS["purple"],
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w", padx=14, pady=(16, 4))
        tk.Label(
            card,
            text=f"{len(ungrouped)} contact(s) need a group",
            bg="#112338",
            fg=COLORS["muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=14, pady=(0, 12))
        self._button(card, "Review", lambda: self.show_page("ungrouped")).pack(
            anchor="w", padx=7, pady=(0, 8)
        )

    def delete_group(self, group_id: str) -> None:
        group = self.service.get_group(group_id)
        if group and messagebox.askyesno(
            "Delete Group",
            f"Delete '{group.name}'? Contacts will stay safe and become ungrouped.",
            parent=self,
        ):
            self.service.delete_group(group_id)
            self.set_status("Group deleted")
            self.show_page("groups")

    def open_group_form(self, group=None) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Rename Group" if group else "New Group")
        dialog.geometry("430x350" if not group else "430x260")
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self)
        dialog.grab_set()
        tk.Label(
            dialog,
            text="Rename Group" if group else "New Group",
            bg=COLORS["bg"],
            fg=COLORS["text"],
            font=("Segoe UI", 17, "bold"),
        ).pack(anchor="w", padx=22, pady=(22, 4))
        tk.Label(
            dialog,
            text="Groups work like folders; a contact can belong to more than one.",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9),
            wraplength=380,
        ).pack(anchor="w", padx=22, pady=(0, 13))
        name = tk.StringVar(value=group.name if group else "")
        tk.Entry(
            dialog,
            textvariable=name,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            insertbackground=COLORS["cyan"],
            relief="flat",
            font=("Segoe UI", 10),
        ).pack(fill="x", padx=22, ipady=8)
        parent_var = tk.StringVar(value="None (root)")
        parent_lookup: dict[str, str | None] = {"None (root)": None}
        if not group:
            tk.Label(
                dialog,
                text="Parent group (optional)",
                bg=COLORS["bg"],
                fg=COLORS["muted"],
                font=("Segoe UI", 9, "bold"),
            ).pack(anchor="w", padx=22, pady=(12, 5))
            values = ["None (root)"]
            for candidate in self.service.list_groups():
                values.append(candidate.name)
                parent_lookup[candidate.name] = candidate.id
            ttk.Combobox(
                dialog, textvariable=parent_var, values=values, state="readonly", width=30
            ).pack(anchor="w", padx=22)
        error = tk.StringVar()
        tk.Label(
            dialog, textvariable=error, bg=COLORS["bg"], fg=COLORS["danger"], font=("Segoe UI", 9)
        ).pack(anchor="w", padx=22, pady=5)
        buttons = tk.Frame(dialog, bg=COLORS["bg"])
        buttons.pack(side="bottom", fill="x", padx=22, pady=18)
        self._button(buttons, "Cancel", dialog.destroy).pack(side="right", padx=4)

        def save() -> None:
            try:
                if group:
                    self.service.rename_group(group.id, name.get())
                else:
                    self.service.create_group(name.get(), parent_lookup.get(parent_var.get()))
                dialog.destroy()
                self.set_status("Group saved")
                self.show_page("groups")
            except Exception as exc:
                error.set(str(exc))

        self._button(buttons, "Save Group", save, accent=True).pack(side="right", padx=4)

    def merge_groups_dialog(self) -> None:
        groups = self.service.list_groups()
        if len(groups) < 2:
            messagebox.showinfo(
                "Merge Groups", "Create at least two groups before merging.", parent=self
            )
            return
        dialog = tk.Toplevel(self)
        dialog.title("Merge Groups")
        dialog.geometry("460x520")
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self)
        dialog.grab_set()
        tk.Label(
            dialog,
            text="Merge Groups",
            bg=COLORS["bg"],
            fg=COLORS["text"],
            font=("Segoe UI", 17, "bold"),
        ).pack(anchor="w", padx=22, pady=(22, 4))
        tk.Label(
            dialog,
            text="Choose the destination group and one or more groups to absorb.",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9),
            wraplength=400,
        ).pack(anchor="w", padx=22, pady=(0, 13))
        target_var = tk.StringVar(value=groups[0].id)
        tk.Label(
            dialog,
            text="Destination",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", padx=22, pady=(0, 5))
        target_menu = ttk.Combobox(
            dialog, values=[group.name for group in groups], state="readonly", width=29
        )
        target_menu.current(0)
        target_menu.pack(anchor="w", padx=22)
        target_menu.bind(
            "<<ComboboxSelected>>", lambda _event: target_var.set(groups[target_menu.current()].id)
        )
        source_vars: dict[str, tk.BooleanVar] = {}
        for group in groups:
            variable = tk.BooleanVar(value=False)
            source_vars[group.id] = variable
            tk.Checkbutton(
                dialog,
                text=f"{group.name}  ({group.contact_count})",
                variable=variable,
                bg=COLORS["panel"],
                activebackground=COLORS["panel"],
                fg=COLORS["text"],
                selectcolor=COLORS["panel_alt"],
                anchor="w",
                padx=10,
                pady=5,
            ).pack(fill="x", padx=22, pady=2)
        buttons = tk.Frame(dialog, bg=COLORS["bg"])
        buttons.pack(side="bottom", fill="x", padx=22, pady=18)
        self._button(buttons, "Cancel", dialog.destroy).pack(side="right", padx=4)

        def merge() -> None:
            target = target_var.get()
            sources = [
                group_id
                for group_id, variable in source_vars.items()
                if variable.get() and group_id != target
            ]
            if not sources:
                messagebox.showinfo(
                    "Merge Groups", "Select at least one source group.", parent=dialog
                )
                return
            self.service.merge_groups(target, sources)
            dialog.destroy()
            self.set_status("Groups merged")
            self.show_page("groups")

        self._button(buttons, "Merge Groups", merge, accent=True).pack(side="right", padx=4)

    def build_tags(self) -> None:
        outer = tk.Frame(self.content, bg=COLORS["bg"])
        outer.grid(row=0, column=0, sticky="nsew", padx=28, pady=22)
        outer.grid_columnconfigure(0, weight=1)
        self._label(outer, "Tags", 21, "text", True).pack(anchor="w")
        self._label(
            outer, "Use labels to create flexible cross-group collections.", 10, "muted"
        ).pack(anchor="w", pady=(3, 15))
        actions = tk.Frame(outer, bg=COLORS["bg"])
        actions.pack(fill="x", pady=(0, 15))
        self._button(actions, "＋ New Tag", self.open_tag_form, accent=True).pack(side="left")
        self._button(actions, "✦ Suggest Tags on Device", self.auto_tag).pack(side="left", padx=7)
        tags = self.service.list_tags()
        if not tags:
            self._empty(
                outer,
                "No tags yet",
                "Create a tag or let the offline rules suggest tags from contact fields.",
            ).pack(fill="x", pady=10)
        for tag in tags:
            row = tk.Frame(
                outer, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1
            )
            row.pack(fill="x", pady=4)
            tk.Label(
                row, text="◇", bg=COLORS["panel"], fg=COLORS["purple"], font=("Segoe UI", 19)
            ).pack(side="left", padx=13, pady=8)
            info = tk.Frame(row, bg=COLORS["panel"])
            info.pack(side="left", fill="x", expand=True, pady=9)
            tk.Label(
                info,
                text=tag.name,
                bg=COLORS["panel"],
                fg=COLORS["text"],
                font=("Segoe UI", 11, "bold"),
                anchor="w",
            ).pack(fill="x")
            tk.Label(
                info,
                text=f"{tag.contact_count} contact(s)",
                bg=COLORS["panel"],
                fg=COLORS["muted"],
                font=("Segoe UI", 9),
                anchor="w",
            ).pack(fill="x", pady=(2, 0))
            self._button(row, "Delete", lambda tid=tag.id: self.delete_tag(tid), danger=True).pack(
                side="right", padx=10, pady=10
            )

    def open_tag_form(self) -> None:
        value = simpledialog.askstring("New Tag", "Tag name:", parent=self)
        if value and value.strip():
            try:
                self.service.create_tag(value)
                self.set_status("Tag created")
                self.show_page("tags")
            except Exception as exc:
                messagebox.showerror("Tag", str(exc), parent=self)

    def delete_tag(self, tag_id: str) -> None:
        tag = next((item for item in self.service.list_tags() if item.id == tag_id), None)
        if tag and messagebox.askyesno("Delete Tag", f"Delete tag '{tag.name}'?", parent=self):
            self.service.delete_tag(tag_id)
            self.show_page("tags")

    def auto_tag(self) -> None:
        count = self.service.auto_tag_contacts()
        self.set_status(f"Offline rules assigned {count} tag(s)")
        self.show_page("tags")

    def build_trash(self) -> None:
        outer = tk.Frame(self.content, bg=COLORS["bg"])
        outer.grid(row=0, column=0, sticky="nsew", padx=28, pady=22)
        outer.grid_rowconfigure(2, weight=1)
        outer.grid_columnconfigure(0, weight=1)
        self._label(outer, "Recycle Bin", 21, "text", True).pack(anchor="w")
        self._label(
            outer,
            "Deleted contacts are retained for 30 days before automatic cleanup.",
            10,
            "muted",
        ).pack(anchor="w", pady=(3, 15))
        items = self.service.list_deleted()
        toolbar = tk.Frame(outer, bg=COLORS["bg"])
        toolbar.pack(fill="x", pady=(0, 10))
        self._button(toolbar, "Restore selected", lambda: self.restore_deleted(tree)).pack(
            side="left", padx=(0, 6)
        )
        self._button(
            toolbar, "Delete permanently", lambda: self.purge_deleted(tree), danger=True
        ).pack(side="left")
        frame = tk.Frame(
            outer, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1
        )
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(
            frame, columns=("name", "phone", "deleted"), show="headings", selectmode="extended"
        )
        for column, text, width in (
            ("name", "Name", 250),
            ("phone", "Phone", 220),
            ("deleted", "Deleted", 220),
        ):
            tree.heading(column, text=text)
            tree.column(column, width=width, anchor="w")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        for item in items:
            phone = "; ".join(
                value.get("number", "")
                for value in item.snapshot.get("phones", [])
                if isinstance(value, dict)
            )
            tree.insert(
                "",
                "end",
                iid=item.contact_id,
                values=(item.name, phone, format_time(item.deleted_at)),
            )

    def restore_deleted(self, tree: ttk.Treeview) -> None:
        ids = tree.selection()
        if not ids:
            return
        for item in ids:
            self.service.restore_deleted(item)
        self.set_status(f"Restored {len(ids)} contact(s)")
        self.show_page("trash")

    def purge_deleted(self, tree: ttk.Treeview) -> None:
        ids = tree.selection()
        if not ids or not messagebox.askyesno(
            "Delete Permanently", "This cannot be undone. Continue?", parent=self
        ):
            return
        for item in ids:
            self.service.permanently_delete(item)
        self.set_status("Removed saved contact copies")
        self.show_page("trash")

    # ── Insights screens ────────────────────────────────────────────────

    def build_duplicates(self) -> None:
        outer = tk.Frame(self.content, bg=COLORS["bg"])
        outer.grid(row=0, column=0, sticky="nsew", padx=28, pady=22)
        outer.grid_columnconfigure(0, weight=1)
        self._label(outer, "Possible Duplicates", 21, "text", True).pack(anchor="w")
        self._label(
            outer,
            "Matches are detected locally from phone numbers, email addresses and names.",
            10,
            "muted",
        ).pack(anchor="w", pady=(3, 15))
        groups = self.service.duplicate_groups()
        if not groups:
            self._empty(
                outer, "No possible duplicates", "Your contact list looks clean right now."
            ).pack(fill="x", pady=12)
            return
        for group in groups:
            card = tk.Frame(
                outer, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1
            )
            card.pack(fill="x", pady=6)
            top = tk.Frame(card, bg=COLORS["panel"])
            top.pack(fill="x", padx=15, pady=(12, 5))
            info = tk.Frame(top, bg=COLORS["panel"])
            info.pack(side="left", fill="x", expand=True)
            tk.Label(
                info,
                text=group.reason,
                bg=COLORS["panel"],
                fg=COLORS["cyan"],
                font=("Segoe UI", 11, "bold"),
                anchor="w",
            ).pack(fill="x")
            tk.Label(
                info,
                text=f"Confidence {group.confidence}% · {len(group.contacts)} contacts",
                bg=COLORS["panel"],
                fg=COLORS["muted"],
                font=("Segoe UI", 9),
                anchor="w",
            ).pack(fill="x", pady=(3, 0))
            self._button(
                top, "Merge", lambda item=group: self.merge_duplicate(item), accent=True
            ).pack(side="right")
            for contact in group.contacts:
                line = " · ".join(
                    value
                    for value in (contact.primary_phone, contact.primary_email, contact.company)
                    if value
                )
                tk.Label(
                    card,
                    text=f"{contact.name}  {('— ' + line) if line else ''}",
                    bg=COLORS["panel"],
                    fg=COLORS["text"],
                    font=("Segoe UI", 9),
                    anchor="w",
                ).pack(fill="x", padx=15, pady=2)
            tk.Frame(card, bg=COLORS["panel"], height=8).pack()

    def merge_duplicate(self, group) -> None:
        if len(group.contacts) < 2:
            return
        names = ", ".join(item.name for item in group.contacts)
        if not messagebox.askyesno(
            "Merge Contacts",
            f"Keep '{group.contacts[0].name}' and merge these contacts?\n\n{names}",
            parent=self,
        ):
            return
        self.service.merge_contacts(group.contacts[0].id, [item.id for item in group.contacts[1:]])
        self.set_status("Duplicate contacts merged")
        self.show_page("duplicates")

    def build_timeline(self) -> None:
        outer = tk.Frame(self.content, bg=COLORS["bg"])
        outer.grid(row=0, column=0, sticky="nsew", padx=28, pady=22)
        outer.grid_rowconfigure(1, weight=1)
        outer.grid_columnconfigure(0, weight=1)
        self._label(outer, "Contact Timeline", 21, "text", True).pack(anchor="w")
        self._label(
            outer,
            "Views, edits, calls, shares and organization actions recorded locally.",
            10,
            "muted",
        ).pack(anchor="w", pady=(3, 15))
        frame = tk.Frame(
            outer, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1
        )
        frame.pack(fill="both", expand=True)
        canvas = tk.Canvas(frame, bg=COLORS["panel"], highlightthickness=0)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=COLORS["panel"])
        inner.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw", width=760)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        events = self.service.list_events()
        if not events:
            tk.Label(
                inner,
                text="Timeline is empty.",
                bg=COLORS["panel"],
                fg=COLORS["muted"],
                font=("Segoe UI", 10),
            ).pack(anchor="w", padx=20, pady=24)
        for event in events:
            row = tk.Frame(
                inner,
                bg=COLORS["panel_alt"],
                highlightbackground=COLORS["line"],
                highlightthickness=1,
            )
            row.pack(fill="x", padx=12, pady=4)
            tk.Label(
                row, text="◷", bg=COLORS["panel_alt"], fg=COLORS["cyan"], font=("Segoe UI", 15)
            ).pack(side="left", padx=12, pady=10)
            info = tk.Frame(row, bg=COLORS["panel_alt"])
            info.pack(side="left", fill="x", expand=True, pady=9)
            tk.Label(
                info,
                text=f"{event.contact_name} · {event.action.replace('_', ' ').title()}",
                bg=COLORS["panel_alt"],
                fg=COLORS["text"],
                font=("Segoe UI", 10, "bold"),
                anchor="w",
            ).pack(fill="x")
            tk.Label(
                info,
                text=event.details,
                bg=COLORS["panel_alt"],
                fg=COLORS["muted"],
                font=("Segoe UI", 9),
                anchor="w",
            ).pack(fill="x", pady=(2, 0))
            tk.Label(
                row,
                text=format_time(event.occurred_at),
                bg=COLORS["panel_alt"],
                fg=COLORS["muted"],
                font=("Segoe UI", 8),
            ).pack(side="right", padx=12)

    def build_smart_groups(self) -> None:
        outer = tk.Frame(self.content, bg=COLORS["bg"])
        outer.grid(row=0, column=0, sticky="nsew", padx=28, pady=22)
        outer.grid_columnconfigure(0, weight=1)
        self._label(outer, "Smart Groups", 21, "text", True).pack(anchor="w")
        self._label(
            outer, "Saved local rules update automatically as contact fields change.", 10, "muted"
        ).pack(anchor="w", pady=(3, 14))
        self._button(outer, "＋ Create Smart Group", self.open_smart_group_form, accent=True).pack(
            anchor="w", pady=(0, 14)
        )
        groups = self.service.list_smart_groups()
        if not groups:
            self._empty(
                outer,
                "No smart groups",
                "Create a rule such as company contains Acme or city contains Jaipur.",
            ).pack(fill="x", pady=10)
        for group in groups:
            matches = self.service.smart_group_contacts(group)
            row = tk.Frame(
                outer, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1
            )
            row.pack(fill="x", pady=4)
            info = tk.Frame(row, bg=COLORS["panel"])
            info.pack(side="left", fill="x", expand=True, padx=15, pady=11)
            tk.Label(
                info,
                text=group.name,
                bg=COLORS["panel"],
                fg=COLORS["text"],
                font=("Segoe UI", 11, "bold"),
                anchor="w",
            ).pack(fill="x")
            tk.Label(
                info,
                text=f"{group.field}: {group.value} · {len(matches)} contact(s)",
                bg=COLORS["panel"],
                fg=COLORS["muted"],
                font=("Segoe UI", 9),
                anchor="w",
            ).pack(fill="x", pady=(3, 0))
            self._button(row, "Open", lambda items=matches: self.show_smart_matches(items)).pack(
                side="right", padx=4, pady=10
            )
            self._button(
                row, "Delete", lambda gid=group.id: self.delete_smart_group(gid), danger=True
            ).pack(side="right", padx=(4, 12), pady=10)

    def open_smart_group_form(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Create Smart Group")
        dialog.geometry("470x360")
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self)
        dialog.grab_set()
        tk.Label(
            dialog,
            text="Create Smart Group",
            bg=COLORS["bg"],
            fg=COLORS["text"],
            font=("Segoe UI", 17, "bold"),
        ).pack(anchor="w", padx=22, pady=(22, 4))
        tk.Label(
            dialog,
            text="A local rule that finds matching contacts automatically.",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=22, pady=(0, 14))
        fields: dict[str, tk.StringVar] = {key: tk.StringVar() for key in ("name", "value")}
        self._form_field(dialog, "Smart group name", fields["name"], "e.g. Work contacts")
        field_var = tk.StringVar(value="company")
        tk.Label(
            dialog,
            text="Match field",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", padx=22, pady=(12, 5))
        ttk.Combobox(
            dialog,
            textvariable=field_var,
            state="readonly",
            values=("name", "company", "email", "phone", "city", "notes", "group", "tag"),
            width=25,
        ).pack(anchor="w", padx=22)
        self._form_field(dialog, "Contains", fields["value"], "e.g. Acme")
        error = tk.StringVar()
        tk.Label(
            dialog, textvariable=error, bg=COLORS["bg"], fg=COLORS["danger"], font=("Segoe UI", 9)
        ).pack(anchor="w", padx=22, pady=4)
        buttons = tk.Frame(dialog, bg=COLORS["bg"])
        buttons.pack(side="bottom", fill="x", padx=22, pady=18)
        self._button(buttons, "Cancel", dialog.destroy).pack(side="right", padx=4)

        def save() -> None:
            try:
                self.service.create_smart_group(
                    fields["name"].get(), field_var.get(), fields["value"].get()
                )
                dialog.destroy()
                self.show_page("smart")
            except Exception as exc:
                error.set(str(exc))

        self._button(buttons, "Create", save, accent=True).pack(side="right", padx=4)

    def delete_smart_group(self, group_id: str) -> None:
        if messagebox.askyesno("Delete Smart Group", "Delete this saved rule?", parent=self):
            self.service.delete_smart_group(group_id)
            self.show_page("smart")

    def show_smart_matches(self, contacts: list[Contact]) -> None:
        # Keep the main navigation model simple while still making rule results usable.
        self.current_page = "all"
        self._clear_content()
        self.build_custom_contact_page("Smart Group Results", contacts)

    def build_custom_contact_page(self, title: str, contacts: list[Contact]) -> None:
        outer = tk.Frame(self.content, bg=COLORS["bg"])
        outer.grid(row=0, column=0, sticky="nsew", padx=24, pady=20)
        outer.grid_rowconfigure(1, weight=1)
        outer.grid_columnconfigure(0, weight=1)
        self._label(outer, title, 20, "text", True).pack(anchor="w")
        self._label(outer, f"{len(contacts)} matching contact(s)", 9, "muted").pack(
            anchor="w", pady=(3, 12)
        )
        frame = tk.Frame(
            outer, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1
        )
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(
            frame,
            columns=("name", "phone", "email", "company"),
            show="headings",
            selectmode="browse",
        )
        for column, width in (("name", 230), ("phone", 190), ("email", 250), ("company", 180)):
            tree.heading(column, text=column.title())
            tree.column(column, width=width, anchor="w")
        tree.pack(fill="both", expand=True)
        for contact in contacts:
            tree.insert(
                "",
                "end",
                iid=contact.id,
                values=(
                    contact.name,
                    contact.primary_phone,
                    contact.primary_email,
                    contact.company,
                ),
            )
        tree.bind("<Double-1>", lambda _event: self.open_contact_preview(tree.focus()))

    def auto_group(self) -> None:
        clusters = self.service.keyword_clusters()
        if not clusters:
            messagebox.showinfo(
                "Auto Group", "No high-confidence local clusters were found yet.", parent=self
            )
            return
        preview = "\n".join(
            f"• {item.suggested_category}: {len(item.contacts)} contacts" for item in clusters[:8]
        )
        if not messagebox.askyesno(
            "Auto Group (Offline)", f"Create or update these groups?\n\n{preview}", parent=self
        ):
            return
        applied = 0
        for cluster in clusters:
            try:
                existing = next(
                    (
                        group
                        for group in self.service.list_groups()
                        if group.name.casefold() == cluster.suggested_category.casefold()
                    ),
                    None,
                )
                group = existing or self.service.create_group(cluster.suggested_category)
                self.service.assign_groups(
                    [item.id for item in cluster.contacts], [group.id], replace=False
                )
                applied += len(cluster.contacts)
            except ValueError:
                continue
        self.set_status(f"Auto Group organized {applied} contact assignment(s)")
        self.show_page("groups")

    def build_relationships(self) -> None:
        outer = tk.Frame(self.content, bg=COLORS["bg"])
        outer.grid(row=0, column=0, sticky="nsew", padx=28, pady=22)
        outer.grid_columnconfigure(0, weight=1)
        self._label(outer, "Relationship Map", 21, "text", True).pack(anchor="w")
        self._label(
            outer,
            "Contacts are linked when they share a group or tag. This map stays on your device.",
            10,
            "muted",
        ).pack(anchor="w", pady=(3, 15))
        relations = self.service.relationships()
        if not relations:
            self._empty(
                outer,
                "No relationships yet",
                "Assign contacts to shared groups or tags to see connections.",
            ).pack(fill="x", pady=10)
        for title, names in relations:
            card = tk.Frame(
                outer, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1
            )
            card.pack(fill="x", pady=5)
            tk.Label(
                card,
                text=title,
                bg=COLORS["panel"],
                fg=COLORS["cyan"],
                font=("Segoe UI", 11, "bold"),
                anchor="w",
            ).pack(fill="x", padx=15, pady=(12, 4))
            tk.Label(
                card,
                text="  ↔  ".join(names) if names else "No contacts",
                bg=COLORS["panel"],
                fg=COLORS["text"],
                font=("Segoe UI", 9),
                anchor="w",
                wraplength=900,
                justify="left",
            ).pack(fill="x", padx=15, pady=(0, 12))

    # ── Import/export and settings ──────────────────────────────────────

    def build_transfer(self) -> None:
        outer = tk.Frame(self.content, bg=COLORS["bg"])
        outer.grid(row=0, column=0, sticky="nsew", padx=28, pady=22)
        outer.grid_columnconfigure(0, weight=1)
        self._label(outer, "Import / Export", 21, "text", True).pack(anchor="w")
        self._label(
            outer,
            "Portable formats preserve the information you choose, without cloud upload.",
            10,
            "muted",
        ).pack(anchor="w", pady=(3, 18))
        export_card = tk.Frame(
            outer, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1
        )
        export_card.pack(fill="x", pady=6)
        tk.Label(
            export_card,
            text="Export",
            bg=COLORS["panel"],
            fg=COLORS["cyan"],
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w", padx=18, pady=(16, 3))
        tk.Label(
            export_card,
            text="CSV and vCard are compatible with other address books. A JSON vault preserves groups, tags and smart rules.",
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9),
            wraplength=820,
            justify="left",
        ).pack(anchor="w", padx=18, pady=(0, 12))
        buttons = tk.Frame(export_card, bg=COLORS["panel"])
        buttons.pack(anchor="w", padx=12, pady=(0, 15))
        self._button(buttons, "Export CSV", lambda: self.export_file("csv"), accent=True).pack(
            side="left", padx=5
        )
        self._button(buttons, "Export vCard", lambda: self.export_file("vcf")).pack(
            side="left", padx=5
        )
        self._button(buttons, "Export JSON Vault", lambda: self.export_file("vault")).pack(
            side="left", padx=5
        )

        import_card = tk.Frame(
            outer, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1
        )
        import_card.pack(fill="x", pady=6)
        tk.Label(
            import_card,
            text="Import / Restore",
            bg=COLORS["panel"],
            fg=COLORS["purple"],
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w", padx=18, pady=(16, 3))
        tk.Label(
            import_card,
            text="Imported contacts are added to the local database. JSON vault restore replaces current active data after confirmation.",
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9),
            wraplength=820,
            justify="left",
        ).pack(anchor="w", padx=18, pady=(0, 12))
        buttons = tk.Frame(import_card, bg=COLORS["panel"])
        buttons.pack(anchor="w", padx=12, pady=(0, 15))
        self._button(buttons, "Import CSV", lambda: self.import_file("csv"), accent=True).pack(
            side="left", padx=5
        )
        self._button(buttons, "Import vCard", lambda: self.import_file("vcf")).pack(
            side="left", padx=5
        )
        self._button(buttons, "Restore JSON Vault", lambda: self.import_file("vault")).pack(
            side="left", padx=5
        )
        stats = self.service.stats()
        self._label(
            outer,
            f"Current local database: {stats['contacts']} contacts · {stats['groups']} groups · {stats['tags']} tags",
            10,
            "muted",
        ).pack(anchor="w", pady=(14, 0))

    def _export_contacts(self) -> list[Contact]:
        if self.selected_ids:
            selected = set(self.selected_ids)
            return [contact for contact in self.service.list_contacts() if contact.id in selected]
        return self.service.list_contacts()

    def export_file(self, format_name: str) -> None:
        if format_name == "csv":
            path = filedialog.asksaveasfilename(
                parent=self,
                title="Export CSV",
                defaultextension=".csv",
                filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),
            )
            if not path:
                return
            text = self.service.export_contacts_text(
                "csv", [item.id for item in self._export_contacts()]
            )
        elif format_name == "vcf":
            path = filedialog.asksaveasfilename(
                parent=self,
                title="Export vCard",
                defaultextension=".vcf",
                filetypes=(("vCard files", "*.vcf"), ("All files", "*.*")),
            )
            if not path:
                return
            text = self.service.export_contacts_text(
                "vcf", [item.id for item in self._export_contacts()]
            )
        else:
            path = filedialog.asksaveasfilename(
                parent=self,
                title="Export JSON Vault",
                defaultextension=".cebak.json",
                filetypes=(
                    ("Contact Explorer vault", "*.cebak.json"),
                    ("JSON files", "*.json"),
                    ("All files", "*.*"),
                ),
            )
            if not path:
                return
            import json

            text = json.dumps(self.service.export_backup(), indent=2, ensure_ascii=False)
        try:
            Path(path).write_text(text, encoding="utf-8", newline="")
            self.set_status(f"Exported {Path(path).name}")
        except OSError as exc:
            messagebox.showerror("Export", str(exc), parent=self)

    def import_file(self, format_name: str) -> None:
        if format_name == "csv":
            path = filedialog.askopenfilename(
                parent=self,
                title="Import CSV",
                filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),
            )
        elif format_name == "vcf":
            path = filedialog.askopenfilename(
                parent=self,
                title="Import vCard",
                filetypes=(("vCard files", "*.vcf"), ("All files", "*.*")),
            )
        else:
            path = filedialog.askopenfilename(
                parent=self,
                title="Restore JSON Vault",
                filetypes=(
                    ("JSON files", "*.json"),
                    ("Vault files", "*.cebak"),
                    ("All files", "*.*"),
                ),
            )
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8-sig")
            if format_name == "vault":
                if not messagebox.askyesno(
                    "Restore Vault",
                    "Replace current active contacts, groups and tags with this vault?",
                    parent=self,
                ):
                    return
                count = self.service.import_vault_text(text, replace=True)
            else:
                count = self.service.import_contacts_text(text, format_name, replace=False)
            self.set_status(f"Imported {count} contact(s)")
            self.show_page("home")
        except Exception as exc:
            messagebox.showerror("Import", str(exc), parent=self)

    def build_settings(self) -> None:
        outer = tk.Frame(self.content, bg=COLORS["bg"])
        outer.grid(row=0, column=0, sticky="nsew", padx=28, pady=22)
        outer.grid_columnconfigure(0, weight=1)
        self._label(outer, "Settings", 21, "text", True).pack(anchor="w")
        self._label(outer, "Local storage and privacy controls", 10, "muted").pack(
            anchor="w", pady=(3, 18)
        )
        card = tk.Frame(
            outer, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1
        )
        card.pack(fill="x", pady=6)
        self._setting_row(card, "Storage", "SQLite database · offline local", COLORS["cyan"])
        self._setting_row(card, "Database file", str(self.service.db_path), COLORS["text"])
        self._setting_row(card, "Network", "No network required", COLORS["cyan"])
        stats = self.service.stats()
        self._setting_row(
            card,
            "Data summary",
            f"{stats['contacts']} contacts · {stats['groups']} groups · {stats['tags']} tags",
            COLORS["text"],
        )
        buttons = tk.Frame(outer, bg=COLORS["bg"])
        buttons.pack(fill="x", pady=15)
        self._button(buttons, "Open Data Folder", self.open_data_folder).pack(side="left")
        self._button(
            buttons, "Create Full Backup", lambda: self.export_file("vault"), accent=True
        ).pack(side="left", padx=7)
        self._button(buttons, "Import / Export", lambda: self.show_page("transfer")).pack(
            side="left"
        )
        info = self._empty(
            outer,
            "Privacy first",
            "Contact Explorer never uploads your contacts. The optional HTTP backend listens only on localhost by default.",
        )
        info.pack(fill="x", pady=8)

    def _setting_row(self, parent: tk.Frame, label: str, value: str, color: str) -> None:
        row = tk.Frame(parent, bg=COLORS["panel"])
        row.pack(fill="x", padx=16, pady=10)
        tk.Label(
            row,
            text=label,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9, "bold"),
            width=18,
            anchor="w",
        ).pack(side="left")
        tk.Label(
            row,
            text=value,
            bg=COLORS["panel"],
            fg=color,
            font=("Segoe UI", 9),
            anchor="w",
            wraplength=650,
        ).pack(side="left", fill="x", expand=True)

    def open_data_folder(self) -> None:
        try:
            os.startfile(self.service.db_path.parent)  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            webbrowser.open(self.service.db_path.parent.as_uri())

    def close(self) -> None:
        self.service.close()
        self.destroy()


def launch(db_path: str | Path | None = None) -> None:
    app = ContactExplorerApp(db_path)
    app.mainloop()
