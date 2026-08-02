"""Tkinter GUI: manage quickphrases, categories, dark mode, on/off toggle."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .engine import ExpansionEngine
from .listener import ExpanderService
from .store import DEFAULT_CATEGORY, PhraseStore

PREFIX = ";"
ALL = "All categories"

THEMES = {
    "light": {
        "bg": "#f4f4f7", "panel": "#f4f4f7", "fg": "#1b1b22",
        "muted": "#666677", "entry_bg": "#ffffff", "entry_fg": "#1b1b22",
        "tree_bg": "#ffffff", "tree_fg": "#1b1b22", "tree_head": "#e6e6ec",
        "select_bg": "#6366f1", "select_fg": "#ffffff",
        "ok": "#0a7d33", "bad": "#b3261e",
    },
    "dark": {
        "bg": "#1e1e2e", "panel": "#1e1e2e", "fg": "#e4e4ef",
        "muted": "#9a9ab0", "entry_bg": "#2a2a3c", "entry_fg": "#e4e4ef",
        "tree_bg": "#252536", "tree_fg": "#e4e4ef", "tree_head": "#33334a",
        "select_bg": "#6366f1", "select_fg": "#ffffff",
        "ok": "#4ade80", "bad": "#f87171",
    },
}


class QuickPhraseApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.store = PhraseStore()
        self.phrases, self.settings = self.store.load()
        self.engine = ExpansionEngine(self._trigger_map(), prefix=PREFIX)
        self.service = ExpanderService(self.engine, on_expansion=self._on_expansion)
        self._expansion_count = 0
        self._filter = ALL

        root.title("QuickPhrase")
        root.geometry("720x540")
        root.minsize(560, 420)
        self.style = ttk.Style(root)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self._build_ui()
        self._apply_theme()
        self._refresh_categories()
        self._refresh_list()
        self.service.start()
        self._set_status_running(True)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # -- UI construction ----------------------------------------------------

    def _build_ui(self) -> None:
        top = ttk.Frame(self.root, padding=(10, 8))
        top.pack(fill="x")
        self.toggle_btn = ttk.Button(top, text="Pause", command=self._toggle)
        self.toggle_btn.pack(side="left")
        self.status_lbl = ttk.Label(top, text="")
        self.status_lbl.pack(side="left", padx=10)
        self.dark_btn = ttk.Button(top, text="", width=12, command=self._toggle_dark)
        self.dark_btn.pack(side="right")
        self.hint_lbl = ttk.Label(top, text=f"Type  {PREFIX}trigger  anywhere to expand")
        self.hint_lbl.pack(side="right", padx=10)

        filter_row = ttk.Frame(self.root, padding=(10, 0, 10, 4))
        filter_row.pack(fill="x")
        ttk.Label(filter_row, text="Show:").pack(side="left")
        self.filter_var = tk.StringVar(value=ALL)
        self.filter_box = ttk.Combobox(filter_row, textvariable=self.filter_var,
                                       state="readonly", width=24)
        self.filter_box.pack(side="left", padx=6)
        self.filter_box.bind("<<ComboboxSelected>>", lambda e: self._on_filter())

        mid = ttk.Frame(self.root, padding=(10, 0))
        mid.pack(fill="both", expand=True)

        columns = ("trigger", "category", "replacement")
        self.tree = ttk.Treeview(mid, columns=columns, show="headings",
                                 selectmode="browse")
        self.tree.heading("trigger", text=f"Trigger ({PREFIX}…)")
        self.tree.heading("category", text="Category")
        self.tree.heading("replacement", text="Expands to")
        self.tree.column("trigger", width=120, stretch=False)
        self.tree.column("category", width=110, stretch=False)
        self.tree.column("replacement", width=380)
        scroll = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda e: self._edit_selected())

        editor = ttk.LabelFrame(self.root, text="Add / edit phrase", padding=10)
        editor.pack(fill="x", padx=10, pady=8)
        self.editor_frame = editor

        row1 = ttk.Frame(editor)
        row1.pack(fill="x")
        ttk.Label(row1, text=f"Trigger:  {PREFIX}").pack(side="left")
        self.trigger_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.trigger_var, width=16).pack(side="left")
        ttk.Label(row1, text="   Category:").pack(side="left")
        self.category_var = tk.StringVar(value=DEFAULT_CATEGORY)
        self.category_box = ttk.Combobox(row1, textvariable=self.category_var, width=16)
        self.category_box.pack(side="left")
        self.ph_lbl = ttk.Label(
            row1, text="{{date}} {{time}} {{cursor}} {{blank}}+Tab")
        self.ph_lbl.pack(side="right")

        ttk.Label(editor, text="Expands to:").pack(anchor="w", pady=(8, 2))
        self.replacement_text = tk.Text(editor, height=4, wrap="word", undo=True,
                                        relief="flat", borderwidth=6)
        self.replacement_text.pack(fill="x")

        row3 = ttk.Frame(editor)
        row3.pack(fill="x", pady=(8, 0))
        ttk.Button(row3, text="Save phrase", command=self._save_phrase).pack(side="left")
        ttk.Button(row3, text="Delete", command=self._delete_selected).pack(side="left", padx=6)
        ttk.Button(row3, text="Clear form", command=self._clear_form).pack(side="left")

    # -- theming ------------------------------------------------------------

    def _apply_theme(self) -> None:
        dark = bool(self.settings.get("dark"))
        c = THEMES["dark" if dark else "light"]
        self.root.configure(bg=c["bg"])
        s = self.style
        s.configure(".", background=c["bg"], foreground=c["fg"],
                    fieldbackground=c["entry_bg"])
        s.configure("TFrame", background=c["bg"])
        s.configure("TLabel", background=c["bg"], foreground=c["fg"])
        s.configure("Muted.TLabel", background=c["bg"], foreground=c["muted"])
        s.configure("TLabelframe", background=c["bg"], foreground=c["fg"])
        s.configure("TLabelframe.Label", background=c["bg"], foreground=c["muted"])
        s.configure("TButton", background=c["tree_head"], foreground=c["fg"],
                    borderwidth=0, focusthickness=0, padding=(10, 4))
        s.map("TButton", background=[("active", c["select_bg"])],
              foreground=[("active", c["select_fg"])])
        s.configure("Treeview", background=c["tree_bg"], foreground=c["tree_fg"],
                    fieldbackground=c["tree_bg"], borderwidth=0, rowheight=24)
        s.configure("Treeview.Heading", background=c["tree_head"],
                    foreground=c["fg"], borderwidth=0)
        s.map("Treeview", background=[("selected", c["select_bg"])],
              foreground=[("selected", c["select_fg"])])
        s.configure("TCombobox", fieldbackground=c["entry_bg"],
                    background=c["tree_head"], foreground=c["entry_fg"],
                    arrowcolor=c["fg"])
        s.map("TCombobox", fieldbackground=[("readonly", c["entry_bg"])],
              foreground=[("readonly", c["entry_fg"])])
        s.configure("TEntry", fieldbackground=c["entry_bg"],
                    foreground=c["entry_fg"], insertcolor=c["entry_fg"])
        s.configure("Vertical.TScrollbar", background=c["tree_head"],
                    troughcolor=c["bg"], borderwidth=0, arrowcolor=c["fg"])
        self.replacement_text.configure(
            bg=c["entry_bg"], fg=c["entry_fg"], insertbackground=c["entry_fg"],
            selectbackground=c["select_bg"], selectforeground=c["select_fg"])
        self.hint_lbl.configure(style="Muted.TLabel")
        self.ph_lbl.configure(style="Muted.TLabel")
        self.dark_btn.configure(text="☀ Light mode" if dark else "🌙 Dark mode")
        self._set_status_running(self.service.running if hasattr(self, "service") else True)

    def _toggle_dark(self) -> None:
        self.settings["dark"] = not bool(self.settings.get("dark"))
        self.store.save(self.phrases, self.settings)
        self._apply_theme()

    # -- actions ------------------------------------------------------------

    def _toggle(self) -> None:
        if self.service.running:
            self.service.stop()
            self._set_status_running(False)
        else:
            self.service.start()
            self._set_status_running(True)

    def _set_status_running(self, running: bool) -> None:
        c = THEMES["dark" if self.settings.get("dark") else "light"]
        if running:
            self.toggle_btn.configure(text="Pause")
            suffix = (f" — {self._expansion_count} expansions"
                      if self._expansion_count else "")
            self.status_lbl.configure(text="● Expanding" + suffix, foreground=c["ok"])
        else:
            self.toggle_btn.configure(text="Resume")
            self.status_lbl.configure(text="● Paused", foreground=c["bad"])

    def _save_phrase(self) -> None:
        trigger = self.trigger_var.get().strip().lstrip(PREFIX)
        replacement = self.replacement_text.get("1.0", "end-1c")
        category = self.category_var.get().strip() or DEFAULT_CATEGORY
        if not trigger:
            messagebox.showwarning("QuickPhrase", "Trigger can't be empty.")
            return
        if any(ch.isspace() for ch in trigger):
            messagebox.showwarning("QuickPhrase", "Triggers can't contain spaces.")
            return
        if not replacement:
            messagebox.showwarning("QuickPhrase", "The expansion text is empty.")
            return
        conflict = next(
            (t for t in self.phrases
             if t != trigger and (t.startswith(trigger) or trigger.startswith(t))),
            None,
        )
        if conflict and not messagebox.askyesno(
            "QuickPhrase",
            f"'{PREFIX}{trigger}' overlaps with existing '{PREFIX}{conflict}'.\n"
            "The shorter one will wait briefly for the longer one while typing.\n\n"
            "Save anyway?",
        ):
            return
        self.phrases[trigger] = {"text": replacement, "category": category}
        self._persist()
        self._refresh_categories()
        self._refresh_list(select=trigger)

    def _delete_selected(self) -> None:
        trigger = self._selected_trigger() or self.trigger_var.get().strip().lstrip(PREFIX)
        if not trigger or trigger not in self.phrases:
            return
        if messagebox.askyesno("QuickPhrase", f"Delete '{PREFIX}{trigger}'?"):
            del self.phrases[trigger]
            self._persist()
            self._refresh_categories()
            self._refresh_list()
            self._clear_form()

    def _edit_selected(self) -> None:
        trigger = self._selected_trigger()
        if trigger is None:
            return
        entry = self.phrases[trigger]
        self.trigger_var.set(trigger)
        self.category_var.set(entry.get("category", DEFAULT_CATEGORY))
        self.replacement_text.delete("1.0", "end")
        self.replacement_text.insert("1.0", entry["text"])

    def _clear_form(self) -> None:
        self.trigger_var.set("")
        self.category_var.set(DEFAULT_CATEGORY)
        self.replacement_text.delete("1.0", "end")

    def _on_filter(self) -> None:
        self._filter = self.filter_var.get()
        self._refresh_list()

    # -- helpers ------------------------------------------------------------

    def _trigger_map(self):
        return {t: e["text"] for t, e in self.phrases.items()}

    def _categories(self):
        return sorted({e.get("category", DEFAULT_CATEGORY)
                       for e in self.phrases.values()})

    def _selected_trigger(self) -> str | None:
        selection = self.tree.selection()
        return selection[0] if selection else None

    def _persist(self) -> None:
        self.store.save(self.phrases, self.settings)
        self.engine.set_phrases(self._trigger_map())

    def _refresh_categories(self) -> None:
        cats = self._categories()
        self.filter_box["values"] = [ALL] + cats
        if self._filter not in ([ALL] + cats):
            self._filter = ALL
            self.filter_var.set(ALL)
        self.category_box["values"] = cats

    def _refresh_list(self, select: str | None = None) -> None:
        self.tree.delete(*self.tree.get_children())
        for trigger in sorted(self.phrases):
            entry = self.phrases[trigger]
            category = entry.get("category", DEFAULT_CATEGORY)
            if self._filter != ALL and category != self._filter:
                continue
            preview = entry["text"].replace("\n", " ⏎ ")
            self.tree.insert("", "end", iid=trigger,
                             values=(PREFIX + trigger, category, preview))
        if select and self.tree.exists(select):
            self.tree.selection_set(select)

    def _on_expansion(self, expansion) -> None:
        self._expansion_count += 1
        self.root.after(0, lambda: self._set_status_running(self.service.running))

    def _on_close(self) -> None:
        self.service.stop()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    QuickPhraseApp(root)
    root.mainloop()
