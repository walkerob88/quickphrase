# PyInstaller spec for QuickPhrase — works on Windows, macOS, and Linux.
# Build with:  pyinstaller quickphrase.spec
import sys

APP_NAME = "QuickPhrase"

if sys.platform == "win32":
    icon = ["assets/quickphrase.ico"]
elif sys.platform == "darwin":
    icon = ["assets/quickphrase.icns"]
else:
    icon = []

a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=[],
    datas=[("quickphrase/packs", "quickphrase/packs")],
    hiddenimports=[
        # pynput loads its platform backend dynamically; be explicit so
        # PyInstaller doesn't miss it.
        "pynput.keyboard._win32", "pynput.mouse._win32",
        "pynput.keyboard._darwin", "pynput.mouse._darwin",
        "pynput.keyboard._xorg", "pynput.mouse._xorg",
    ],
    excludes=["pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    strip=False,
    upx=False,
    console=False,          # no terminal window
    icon=icon or None,
    onefile=True,
)

if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name=f"{APP_NAME}.app",
        icon="assets/quickphrase.icns",
        bundle_identifier="dev.rob.quickphrase",
        info_plist={
            "NSHighResolutionCapable": True,
            # Explain why macOS should offer the Accessibility permission.
            "NSAppleEventsUsageDescription":
                "QuickPhrase expands text snippets as you type.",
        },
    )
