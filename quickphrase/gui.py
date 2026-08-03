"""Tkinter GUI: EMR-style card grid for managing quickphrases.

Layout: top bar (pause / status / theme / add), search bar, category pill
tabs (All / Favorites / each category), then a scrollable 3-column grid of
phrase cards, each with trigger, category tag, preview, star, Edit, Delete.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import packs
from .engine import ExpansionEngine
from .listener import ExpanderService
from .store import DEFAULT_CATEGORY, PhraseStore

PREFIX = ";"
ALL = "All"
FAVORITES = "Favorites"
COLUMNS = 3

THEMES = {
    "light": {
        "bg": "#f4f4f7", "fg": "#1b1b22", "muted": "#666677",
        "entry_bg": "#ffffff", "entry_fg": "#1b1b22",
        "card_bg": "#ffffff", "card_border": "#dddde4",
        "trigger": "#4f46e5", "tag_bg": "#e8e8f5", "tag_fg": "#4f46e5",
        "pill_bg": "#e6e6ec", "pill_fg": "#1b1b22",
        "pill_on_bg": "#6366f1", "pill_on_fg": "#ffffff",
        "accent": "#188a4d", "accent_fg": "#ffffff",
        "danger": "#b3261e", "star_on": "#e8a512", "star_off": "#a5a5b5",
        "select_bg": "#6366f1", "select_fg": "#ffffff",
        "ok": "#0a7d33", "bad": "#b3261e", "btn_bg": "#e6e6ec",
    },
    "dark": {
        "bg": "#171722", "fg": "#e4e4ef", "muted": "#9a9ab0",
        "entry_bg": "#232334", "entry_fg": "#e4e4ef",
        "card_bg": "#1f1f30", "card_border": "#32324a",
        "trigger": "#818cf8", "tag_bg": "#2c2c44", "tag_fg": "#93c5fd",
        "pill_bg": "#2a2a3c", "pill_fg": "#e4e4ef",
        "pill_on_bg": "#6366f1", "pill_on_fg": "#ffffff",
        "accent": "#1f9d57", "accent_fg": "#ffffff",
        "danger": "#f87171", "star_on": "#fbbf24", "star_off": "#55556d",
        "select_bg": "#6366f1", "select_fg": "#ffffff",
        "ok": "#4ade80", "bad": "#f87171", "btn_bg": "#2a2a3c",
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
        self._wrap = 260

        root.title("QuickPhrase")
        root.geometry("1000x680")
        root.minsize(760, 480)
        self.style = ttk.Style(root)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self._build_static_ui()
        self._render_all()
        self.service.start()
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # -- static skeleton ----------------------------------------------------

    def _theme(self):
        return THEMES["dark" if self.settings.get("dark") else "light"]

    def _build_static_ui(self) -> None:
        c = self._theme()
        self.top = tk.Frame(self.root)
        self.top.pack(fill="x", padx=14, pady=(12, 6))

        self.toggle_btn = tk.Button(self.top, command=self._toggle, bd=0,
                                    padx=14, pady=5, cursor="hand2")
        self.toggle_btn.pack(side="left")
        self.status_lbl = tk.Label(self.top)
        self.status_lbl.pack(side="left", padx=10)

        self.add_btn = tk.Button(self.top, text="+ Add Quick Phrase", bd=0,
                                 padx=14, pady=5, cursor="hand2",
                                 command=lambda: self._open_editor(None))
        self.add_btn.pack(side="right")
        self.dark_btn = tk.Button(self.top, bd=0, padx=12, pady=5,
                                  cursor="hand2", command=self._toggle_dark)
        self.dark_btn.pack(side="right", padx=8)
        self.packs_btn = tk.Button(self.top, text="⇅ Packs", bd=0, padx=12,
                                   pady=5, cursor="hand2",
                                   command=self._show_packs_menu)
        self.packs_btn.pack(side="right")

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._render_cards())
        self.search = tk.Entry(self.root, textvariable=self.search_var,
                               bd=0, font=("Segoe UI", 11), relief="flat")
        self.search.pack(fill="x", padx=14, ipady=7)

        self.pills_frame = tk.Frame(self.root)
        self.pills_frame.pack(fill="x", padx=14, pady=(8, 2))

        holder = tk.Frame(self.root)
        holder.pack(fill="both", expand=True, padx=(14, 0), pady=(4, 10))
        self.canvas = tk.Canvas(holder, highlightthickness=0, bd=0)
        self.scroll = ttk.Scrollbar(holder, orient="vertical",
                                    command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroll.pack(side="right", fill="y")
        self.grid_frame = tk.Frame(self.canvas)
        self._canvas_win = self.canvas.create_window((0, 0), window=self.grid_frame,
                                                     anchor="nw")
        self.grid_frame.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.root.bind_all("<MouseWheel>", self._on_wheel)
        self.root.bind_all("<Button-4>", self._on_wheel)
        self.root.bind_all("<Button-5>", self._on_wheel)

        self.hint = tk.Label(self.root, anchor="w",
                             text=f"Type  {PREFIX}trigger  anywhere to expand — "
                                  "Tab jumps between {{blank}} fill-ins")
        self.hint.pack(fill="x", padx=14, pady=(0, 8))

    # -- rendering ----------------------------------------------------------

    def _render_all(self) -> None:
        c = self._theme()
        self.root.configure(bg=c["bg"])
        for w in (self.top, self.pills_frame, self.grid_frame):
            w.configure(bg=c["bg"])
        self.canvas.configure(bg=c["bg"])
        self.search.configure(bg=c["entry_bg"], fg=c["entry_fg"],
                              insertbackground=c["entry_fg"])
        self.hint.configure(bg=c["bg"], fg=c["muted"])
        self.status_lbl.configure(bg=c["bg"])
        self.toggle_btn.configure(bg=c["btn_bg"], fg=c["fg"],
                                  activebackground=c["select_bg"],
                                  activeforeground=c["select_fg"])
        self.add_btn.configure(bg=c["accent"], fg=c["accent_fg"],
                               activebackground=c["accent"],
                               activeforeground=c["accent_fg"])
        self.dark_btn.configure(bg=c["btn_bg"], fg=c["fg"],
                                activebackground=c["select_bg"],
                                activeforeground=c["select_fg"],
                                text="☀ Light" if self.settings.get("dark") else "🌙 Dark")
        self.packs_btn.configure(bg=c["btn_bg"], fg=c["fg"],
                                 activebackground=c["select_bg"],
                                 activeforeground=c["select_fg"])
        self.style.configure("Vertical.TScrollbar", background=c["btn_bg"],
                             troughcolor=c["bg"], borderwidth=0,
                             arrowcolor=c["fg"])
        self._set_status()
        self._render_pills()
        self._render_cards()

    def _render_pills(self) -> None:
        c = self._theme()
        for w in self.pills_frame.winfo_children():
            w.destroy()
        pills = [ALL, f"★ {FAVORITES}"] + self._categories()
        row = None
        used = 0
        for name in pills:
            width = len(name) + 4
            if row is None or used + width > 120:
                row = tk.Frame(self.pills_frame, bg=c["bg"])
                row.pack(fill="x", pady=1)
                used = 0
            used += width
            active = (name == self._filter)
            btn = tk.Button(
                row, text=name, bd=0, padx=10, pady=3, cursor="hand2",
                font=("Segoe UI", 9, "bold" if active else "normal"),
                bg=c["pill_on_bg"] if active else c["pill_bg"],
                fg=c["pill_on_fg"] if active else c["pill_fg"],
                activebackground=c["pill_on_bg"], activeforeground=c["pill_on_fg"],
                command=lambda n=name: self._set_filter(n))
            btn.pack(side="left", padx=2)

    def _visible_phrases(self):
        query = self.search_var.get().strip().lower()
        items = []
        for trigger in sorted(self.phrases):
            e = self.phrases[trigger]
            if self._filter == f"★ {FAVORITES}" and not e.get("favorite"):
                continue
            if self._filter not in (ALL, f"★ {FAVORITES}") and \
                    e.get("category", DEFAULT_CATEGORY) != self._filter:
                continue
            if query and query not in trigger.lower() and \
                    query not in e["text"].lower():
                continue
            items.append(trigger)
        return items

    def _render_cards(self) -> None:
        c = self._theme()
        for w in self.grid_frame.winfo_children():
            w.destroy()
        for col in range(COLUMNS):
            self.grid_frame.columnconfigure(col, weight=1, uniform="cards")

        visible = self._visible_phrases()
        if not visible:
            tk.Label(self.grid_frame, text="No phrases match.",
                     bg=c["bg"], fg=c["muted"], font=("Segoe UI", 11)
                     ).grid(row=0, column=0, columnspan=COLUMNS, pady=30)
            return

        for i, trigger in enumerate(visible):
            entry = self.phrases[trigger]
            card = tk.Frame(self.grid_frame, bg=c["card_bg"],
                            highlightbackground=c["card_border"],
                            highlightthickness=1)
            card.grid(row=i // COLUMNS, column=i % COLUMNS,
                      sticky="nsew", padx=6, pady=6)

            head = tk.Frame(card, bg=c["card_bg"])
            head.pack(fill="x", padx=10, pady=(8, 2))
            tk.Label(head, text=PREFIX + trigger, bg=c["card_bg"],
                     fg=c["trigger"], font=("Consolas", 12, "bold")
                     ).pack(side="left")
            tk.Label(head, text=entry.get("category", DEFAULT_CATEGORY),
                     bg=c["tag_bg"], fg=c["tag_fg"], padx=7, pady=1,
                     font=("Segoe UI", 8)).pack(side="right")

            preview = entry["text"].replace("\n", " ").strip()
            if len(preview) > 220:
                preview = preview[:220] + "…"
            tk.Label(card, text=preview, bg=c["card_bg"], fg=c["muted"],
                     justify="left", anchor="nw", wraplength=self._wrap,
                     font=("Segoe UI", 9)).pack(fill="both", expand=True,
                                                padx=10, pady=(0, 4))

            foot = tk.Frame(card, bg=c["card_bg"])
            foot.pack(fill="x", padx=8, pady=(0, 8))
            fav = entry.get("favorite", False)
            tk.Button(foot, text="★" if fav else "☆", bd=0, cursor="hand2",
                      bg=c["card_bg"], fg=c["star_on"] if fav else c["star_off"],
                      activebackground=c["card_bg"], font=("Segoe UI", 12),
                      command=lambda t=trigger: self._toggle_favorite(t)
                      ).pack(side="left")
            tk.Button(foot, text="Delete", bd=0, padx=10, pady=2,
                      cursor="hand2", bg=c["card_bg"], fg=c["danger"],
                      activebackground=c["danger"], activeforeground="#ffffff",
                      command=lambda t=trigger: self._delete(t)
                      ).pack(side="right")
            tk.Button(foot, text="Edit", bd=0, padx=10, pady=2,
                      cursor="hand2", bg=c["btn_bg"], fg=c["fg"],
                      activebackground=c["select_bg"], activeforeground="#ffffff",
                      command=lambda t=trigger: self._open_editor(t)
                      ).pack(side="right", padx=6)

    # -- events -------------------------------------------------------------

    def _on_canvas_resize(self, event) -> None:
        self.canvas.itemconfigure(self._canvas_win, width=event.width)
        wrap = max(170, event.width // COLUMNS - 60)
        if abs(wrap - self._wrap) > 24:
            self._wrap = wrap
            self._render_cards()

    def _on_wheel(self, event) -> None:
        if getattr(event, "num", None) == 4:
            self.canvas.yview_scroll(-3, "units")
        elif getattr(event, "num", None) == 5:
            self.canvas.yview_scroll(3, "units")
        else:
            self.canvas.yview_scroll(-3 if event.delta > 0 else 3, "units")

    def _set_filter(self, name: str) -> None:
        self._filter = name
        self._render_pills()
        self._render_cards()

    def _toggle_dark(self) -> None:
        self.settings["dark"] = not bool(self.settings.get("dark"))
        self.store.save(self.phrases, self.settings)
        self._render_all()

    def _toggle(self) -> None:
        if self.service.running:
            self.service.stop()
        else:
            self.service.start()
        self._set_status()

    def _set_status(self) -> None:
        c = self._theme()
        if self.service.running if hasattr(self, "service") else True:
            self.toggle_btn.configure(text="Pause")
            suffix = (f" — {self._expansion_count} expansions"
                      if self._expansion_count else "")
            self.status_lbl.configure(text="● Expanding" + suffix, fg=c["ok"])
        else:
            self.toggle_btn.configure(text="Resume")
            self.status_lbl.configure(text="● Paused", fg=c["bad"])

    def _toggle_favorite(self, trigger: str) -> None:
        self.phrases[trigger]["favorite"] = not self.phrases[trigger].get("favorite")
        self._persist()
        self._render_cards()

    def _delete(self, trigger: str) -> None:
        if messagebox.askyesno("QuickPhrase", f"Delete '{PREFIX}{trigger}'?"):
            del self.phrases[trigger]
            self._persist()
            self._render_cards()

    def _on_expansion(self, expansion) -> None:
        self._expansion_count += 1
        self.root.after(0, self._set_status)

    def _on_close(self) -> None:
        self.service.stop()
        self.root.destroy()

    # -- phrase packs -------------------------------------------------------

    def _show_packs_menu(self) -> None:
        c = self._theme()
        menu = tk.Menu(self.root, tearoff=0, bg=c["card_bg"], fg=c["fg"],
                       activebackground=c["select_bg"],
                       activeforeground=c["select_fg"], bd=0)
        if os.path.exists(packs.builtin_pack_path("orthopedics")):
            menu.add_command(label="Load built-in: Orthopedics Starter (130 phrases)",
                             command=self._load_builtin_ortho)
            menu.add_separator()
        menu.add_command(label="Import pack from file…", command=self._import_pack)
        menu.add_command(label="Export pack to file…", command=self._export_pack)
        menu.tk_popup(self.packs_btn.winfo_rootx(),
                      self.packs_btn.winfo_rooty() + self.packs_btn.winfo_height())

    def _load_builtin_ortho(self) -> None:
        self._apply_pack_file(packs.builtin_pack_path("orthopedics"))

    def _import_pack(self) -> None:
        path = filedialog.askopenfilename(
            title="Import QuickPhrase pack",
            filetypes=[("QuickPhrase pack", "*.json"), ("All files", "*.*")])
        if path:
            self._apply_pack_file(path)

    def _apply_pack_file(self, path: str) -> None:
        try:
            name, incoming = packs.load_pack(path)
        except packs.PackError as exc:
            messagebox.showerror("QuickPhrase", str(exc))
            return
        _, _, conflicts = packs.merge(self.phrases, incoming, overwrite=False)
        overwrite = False
        if conflicts:
            answer = messagebox.askyesnocancel(
                "QuickPhrase",
                f"'{name}' contains {conflicts} trigger(s) that differ from "
                "yours.\n\nYes = replace yours with the pack's version\n"
                "No = keep yours and import only new phrases\nCancel = abort")
            if answer is None:
                return
            overwrite = bool(answer)
        merged, applied, _ = packs.merge(self.phrases, incoming, overwrite)
        self.phrases = merged
        cats = self.settings.setdefault("categories", [])
        for entry in incoming.values():
            if entry["category"] not in cats:
                cats.append(entry["category"])
        self._persist()
        self._render_pills()
        self._render_cards()
        messagebox.showinfo("QuickPhrase",
                            f"Imported '{name}': {applied} phrase(s) added or "
                            "updated.")

    def _export_pack(self) -> None:
        c = self._theme()
        win = tk.Toplevel(self.root)
        win.title("Export pack")
        win.geometry("360x420")
        win.configure(bg=c["bg"])
        win.transient(self.root)
        win.grab_set()
        tk.Label(win, text="Choose categories to export:", bg=c["bg"],
                 fg=c["fg"], font=("Segoe UI", 10)).pack(anchor="w",
                                                         padx=14, pady=(12, 4))
        box = tk.Listbox(win, selectmode="multiple", bd=0,
                         bg=c["entry_bg"], fg=c["entry_fg"],
                         selectbackground=c["select_bg"],
                         selectforeground=c["select_fg"],
                         font=("Segoe UI", 10), activestyle="none")
        cats = self._categories()
        for cat in cats:
            box.insert("end", cat)
        box.select_set(0, "end")
        box.pack(fill="both", expand=True, padx=14)

        def do_export():
            chosen = {cats[i] for i in box.curselection()}
            subset = {t: e for t, e in self.phrases.items()
                      if e.get("category", DEFAULT_CATEGORY) in chosen}
            if not subset:
                messagebox.showwarning("QuickPhrase",
                                       "No phrases in the selected categories.",
                                       parent=win)
                return
            path = filedialog.asksaveasfilename(
                parent=win, title="Save pack as", defaultextension=".json",
                initialfile="my-quickphrase-pack.json",
                filetypes=[("QuickPhrase pack", "*.json")])
            if not path:
                return
            packs.save_pack(path, os.path.splitext(os.path.basename(path))[0],
                            subset)
            win.destroy()
            messagebox.showinfo("QuickPhrase",
                                f"Exported {len(subset)} phrase(s) to\n{path}\n\n"
                                "Share the file — friends import it via "
                                "Packs → Import.")

        tk.Button(win, text="Export…", bd=0, padx=16, pady=6, cursor="hand2",
                  bg=c["accent"], fg=c["accent_fg"],
                  activebackground=c["accent"], activeforeground=c["accent_fg"],
                  command=do_export).pack(pady=12)

    # -- add / edit dialog --------------------------------------------------

    def _open_editor(self, trigger: str | None) -> None:
        c = self._theme()
        win = tk.Toplevel(self.root)
        win.title("Edit phrase" if trigger else "Add Quick Phrase")
        win.geometry("560x420")
        win.configure(bg=c["bg"])
        win.transient(self.root)
        win.grab_set()

        entry = self.phrases.get(trigger, {}) if trigger else {}

        def label(text, pady=(10, 2)):
            tk.Label(win, text=text, bg=c["bg"], fg=c["fg"],
                     font=("Segoe UI", 10)).pack(anchor="w", padx=14, pady=pady)

        label("Trigger (typed after  %s ):" % PREFIX)
        trig_var = tk.StringVar(value=trigger or "")
        tk.Entry(win, textvariable=trig_var, bd=0, font=("Consolas", 12),
                 bg=c["entry_bg"], fg=c["entry_fg"],
                 insertbackground=c["entry_fg"]).pack(fill="x", padx=14, ipady=5)

        label("Category:")
        cat_var = tk.StringVar(value=entry.get("category", DEFAULT_CATEGORY))
        cat_box = ttk.Combobox(win, textvariable=cat_var,
                               values=self._categories())
        cat_box.pack(fill="x", padx=14)

        label("Expands to   ({{date}} {{time}} {{cursor}} {{blank}}+Tab):")
        text = tk.Text(win, height=8, wrap="word", undo=True, bd=0,
                       bg=c["entry_bg"], fg=c["entry_fg"],
                       insertbackground=c["entry_fg"], font=("Segoe UI", 10))
        text.pack(fill="both", expand=True, padx=14)
        if entry:
            text.insert("1.0", entry["text"])

        btns = tk.Frame(win, bg=c["bg"])
        btns.pack(fill="x", padx=14, pady=10)

        def save():
            new_trigger = trig_var.get().strip().lstrip(PREFIX)
            replacement = text.get("1.0", "end-1c")
            category = cat_var.get().strip() or DEFAULT_CATEGORY
            if not new_trigger:
                messagebox.showwarning("QuickPhrase", "Trigger can't be empty.",
                                       parent=win)
                return
            if any(ch.isspace() for ch in new_trigger):
                messagebox.showwarning("QuickPhrase",
                                       "Triggers can't contain spaces.", parent=win)
                return
            if not replacement:
                messagebox.showwarning("QuickPhrase",
                                       "The expansion text is empty.", parent=win)
                return
            conflict = next(
                (t for t in self.phrases
                 if t != new_trigger and t != trigger and
                 (t.startswith(new_trigger) or new_trigger.startswith(t))), None)
            if conflict and not messagebox.askyesno(
                "QuickPhrase",
                f"'{PREFIX}{new_trigger}' overlaps with '{PREFIX}{conflict}'.\n"
                "The shorter one waits briefly for the longer while typing.\n\n"
                "Save anyway?", parent=win):
                return
            if trigger and trigger != new_trigger:
                self.phrases.pop(trigger, None)
            favorite = entry.get("favorite", False)
            self.phrases[new_trigger] = {"text": replacement,
                                         "category": category,
                                         "favorite": favorite}
            cats = self.settings.setdefault("categories", [])
            if category not in cats:
                cats.append(category)
            self._persist()
            self._render_pills()
            self._render_cards()
            win.destroy()

        tk.Button(btns, text="Save phrase", bd=0, padx=16, pady=6,
                  cursor="hand2", bg=c["accent"], fg=c["accent_fg"],
                  activebackground=c["accent"], activeforeground=c["accent_fg"],
                  command=save).pack(side="right")
        tk.Button(btns, text="Cancel", bd=0, padx=16, pady=6, cursor="hand2",
                  bg=c["btn_bg"], fg=c["fg"], activebackground=c["select_bg"],
                  activeforeground=c["select_fg"],
                  command=win.destroy).pack(side="right", padx=8)

    # -- helpers ------------------------------------------------------------

    def _trigger_map(self):
        return {t: e["text"] for t, e in self.phrases.items()}

    def _categories(self):
        seeded = set(self.settings.get("categories", []))
        used = {e.get("category", DEFAULT_CATEGORY) for e in self.phrases.values()}
        return sorted(seeded | used)

    def _persist(self) -> None:
        self.store.save(self.phrases, self.settings)
        self.engine.set_phrases(self._trigger_map())


def main() -> None:
    root = tk.Tk()
    QuickPhraseApp(root)
    root.mainloop()
