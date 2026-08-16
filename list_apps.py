"""
list_apps.py - find the exact name/command for any app open_app can't launch.

Usage:
    python list_apps.py              # lists ALL installed .desktop entries
    python list_apps.py spotify        # filters to names containing "spotify"
"""

import glob
import os
import sys

SEARCH_DIRS = [
    "/usr/share/applications",
    "/usr/local/share/applications",
    os.path.expanduser("~/.local/share/applications"),
]


def list_apps(filter_term: str = "") -> None:
    filter_term = filter_term.lower()
    found = []
    for d in SEARCH_DIRS:
        for path in glob.glob(os.path.join(d, "*.desktop")):
            desktop_id = os.path.basename(path)
            name = None
            exec_cmd = None
            try:
                with open(path, "r", errors="ignore") as f:
                    for line in f:
                        if line.startswith("Name=") and name is None:
                            name = line.strip().split("=", 1)[1]
                        elif line.startswith("Exec=") and exec_cmd is None:
                            exec_cmd = line.strip().split("=", 1)[1]
                        if name and exec_cmd:
                            break
            except OSError:
                continue
            if not name:
                continue
            if filter_term and filter_term not in name.lower():
                continue
            found.append((name, desktop_id, exec_cmd or "?"))

    if not found:
        print(f"No installed apps found matching '{filter_term}'." if filter_term else "No apps found.")
        return

    found.sort(key=lambda x: x[0].lower())
    for name, desktop_id, exec_cmd in found:
        print(f"{name}\n  desktop id: {desktop_id}\n  exec:       {exec_cmd}\n")


if __name__ == "__main__":
    term = sys.argv[1] if len(sys.argv) > 1 else ""
    list_apps(term)
