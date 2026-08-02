# QuickPhrase

A system-wide text expander. Type `;` followed by a short trigger in **any** app — browser, editor, chat — and it instantly becomes your full phrase.

Type `;omw` → `on my way!` &nbsp;•&nbsp; Type `;sig` → your email signature.

## How it works

A global keyboard listener (via [pynput](https://pynput.readthedocs.io/)) watches what you type. When it sees `;trigger`, it sends backspaces to erase what you typed and types the replacement in its place. A tkinter GUI manages your phrase list, which is stored as JSON in your user config directory.

```
quickphrase/
├── engine.py        # pure state machine: keystrokes in, "expand now" out (unit-tested)
├── placeholders.py  # pure placeholder parsing: {{date}}, {{cursor}}, {{blank}} tab stops
├── listener.py      # global keyboard/mouse hooks + injection worker + fill-in sessions
├── injector.py      # backspaces + typing + caret movement
├── store.py         # JSON persistence (phrases, categories, settings)
├── gui.py           # tkinter management window (categories, dark mode)
└── __main__.py      # python -m quickphrase
```

## Install & run

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m quickphrase
```

The window opens with a few starter phrases and expansion active. Close the window to stop everything; use **Pause** to keep it open but inactive.

## Placeholders

Use these inside a phrase's expansion text:

| Placeholder  | Result |
|--------------|--------|
| `{{date}}`   | Today's date, e.g. `2026-08-02` |
| `{{time}}`   | Current time, e.g. `14:07` |
| `{{cursor}}` | Where the caret lands after expansion (e.g. `Hi {{cursor}}, thanks!`) |
| `{{blank}}`  | Fill-in stop — see below |

Multi-line expansions work — press Enter normally in the "Expands to" box.

### Fill-in blanks

Put `{{blank}}` wherever you'll want to type something different each time:

```
Hi {{blank}},

Thanks for reaching out about {{blank}}. I'll get back to you by {{blank}}.
```

After expansion the caret lands on the first blank. Type your text, press **Tab**, and the caret jumps to the next blank; the final Tab lands at the end of the snippet. Moving the caret yourself (arrows, clicking, Esc) ends the fill-in session. Try the built-in `;intro` phrase.

## Categories & dark mode

Every phrase has a category (type a new name in the Category box to create one) and the list can be filtered with the "Show" dropdown. The 🌙/☀ button toggles dark mode; the preference is saved.

## Per-OS notes

**Windows** — works out of the box. If another app runs elevated (as admin), expansion won't work inside it unless QuickPhrase also runs elevated.

**macOS** — the first run will trigger a prompt to grant your terminal (or Python) **Accessibility** and **Input Monitoring** permissions in System Settings → Privacy & Security. Both are required for global listening and injection. Re-run after granting.

**Linux** — works on X11. On **Wayland**, global key hooks are blocked by design for security; log into an "Xorg" session, or use this app under XWayland-friendly compositors that allow it. `pynput` also needs `python3-tk` (`sudo apt install python3-tk`) if tkinter isn't bundled with your Python.

## Behavior details worth knowing

- **Expansion is instant** — no trailing space needed. `;omw` expands the moment you type the `w`.
- **Overlapping triggers** (`;b` and `;brb`): the short one waits while the long one is still possible. If you break the pattern (`;b` then space), the short one fires and your extra keystroke is preserved.
- **Moving the caret** (arrows, clicking, Esc, shortcuts) resets the in-progress trigger, so stale half-typed triggers never fire later.
- The app ignores its own injected keystrokes, so a replacement containing `;` won't recursively expand.
- **Password fields**: the listener sees all keystrokes system-wide. Phrases only expand after you type `;trigger`, and nothing is ever logged or sent anywhere, but pause the app if that concerns you in sensitive contexts.

## Where phrases are stored

| OS      | Path |
|---------|------|
| Windows | `%APPDATA%\QuickPhrase\phrases.json` |
| macOS   | `~/Library/Application Support/QuickPhrase/phrases.json` |
| Linux   | `~/.config/quickphrase/phrases.json` |

It's plain JSON (`{"version": 2, "settings": {...}, "phrases": {"trigger": {"text": ..., "category": ...}}}`), so you can edit or version-control it directly — restart the app (or re-save any phrase) to reload. Old flat-format files are migrated automatically.

## Distributing standalone apps (no Python required)

PyInstaller bundles QuickPhrase into a single executable per OS. Executables can only be built *on* their target OS — that's what the GitHub Actions workflow is for.

**Windows .exe, built locally right now:**

```powershell
powershell -ExecutionPolicy Bypass -File .\build_windows.ps1
```

Output: `dist\QuickPhrase.exe` — one file, share it with any Windows 10/11 user. Note: unsigned executables trigger a Windows SmartScreen warning on first run ("More info" → "Run anyway"). Code-signing certificates make that go away but cost money.

**All three OSes, via GitHub:**

1. Create a repository on GitHub and push this project:
   ```bash
   git init && git add . && git commit -m "QuickPhrase v0.2"
   git remote add origin https://github.com/YOURNAME/quickphrase.git
   git push -u origin main
   ```
2. Tag a release — this triggers the build workflow:
   ```bash
   git tag v0.2.0 && git push --tags
   ```
3. A few minutes later, the Releases page has `QuickPhrase-windows.exe`, `QuickPhrase-macos.zip`, and `QuickPhrase-linux` built automatically. (You can also run the workflow manually from the Actions tab.)

Per-platform notes for your users: macOS apps that are unsigned need right-click → Open the first time, then Accessibility + Input Monitoring permissions; the Linux binary needs X11 (`chmod +x QuickPhrase-linux` after download).

## Tests

```bash
python -m pytest tests/
```

The expansion engine is a pure state machine with no OS dependencies, so all matching logic (overlaps, backspaces, resets, tails) is covered headlessly.

## Ideas for v2

System tray icon (pystray) so it runs without a window; app-specific exclusions; clipboard-based injection for very long phrases (faster than typing); import/export phrase packs; named blanks with default values.
