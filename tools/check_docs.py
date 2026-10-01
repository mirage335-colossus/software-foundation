#!/usr/bin/env python3
"""Validate local Markdown destinations, required repository files and JSON."""
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE = {".git", ".agent-work", "build", ".cache", "__pycache__"}
errors = []
required = ["README.md", "AGENTS.md", "COMPILE", "RELEASE", "LICENSE",
            "docs/README.md", "third_party/README.md", "CMakePresets.json"]
for name in required:
    if not (ROOT / name).is_file():
        errors.append("missing required file: " + name)
for path in ROOT.rglob("*"):
    relative = path.relative_to(ROOT)
    if any(part in EXCLUDE for part in relative.parts) or not path.is_file():
        continue
    if path.suffix == ".json":
        try:
            json.loads(path.read_text())
        except (ValueError, UnicodeError) as error:
            errors.append(f"{relative}: {error}")
    if path.suffix != ".md":
        continue
    # Ignore code fences; template paths inside prose still need real destinations.
    content = re.sub(r"```.*?```", "", path.read_text(), flags=re.S)
    for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", content):
        target = target.strip().split(" ", 1)[0].strip("<>")
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        destination = (path.parent / unquote(parsed.path)).resolve()
        if not destination.exists():
            errors.append(f"{relative}: missing link {target}")
if errors:
    print("\n".join(errors), file=sys.stderr)
    sys.exit(1)
print("Repository documentation links and JSON are valid")
