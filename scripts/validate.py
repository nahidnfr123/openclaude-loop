"""Validate plugin metadata, skill structure and intra-repository references."""
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = "openclaude-loop"
SKILLS = ("openclaude-loop", "opencode-review", "opencode-build")
RUNNER = "skills/openclaude-loop/scripts/runner.py"


def validate(root=ROOT):
    errors = []

    found = sorted(p.parent.name for p in (root / "skills").glob("*/SKILL.md"))
    if found != sorted(SKILLS):
        errors.append(f"skills/: expected {sorted(SKILLS)}, found {found}")

    for path in sorted((root / "skills").glob("*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        try:
            if not text.startswith("---\n"):
                raise ValueError("missing YAML frontmatter (or a UTF-8 BOM is present)")
            front = yaml.safe_load(text.split("---", 2)[1])
            if front.get("name") != path.parent.name:
                raise ValueError("frontmatter name must match the skill folder")
            description = front.get("description")
            if not isinstance(description, str) or not description.strip():
                raise ValueError("description must be a non-empty string")
            if len(description) > 1024:
                raise ValueError(f"description is {len(description)} characters; the limit is 1024")
        except (ValueError, IndexError, AttributeError, yaml.YAMLError) as exc:
            errors.append(f"{path.relative_to(root)}: {exc}")

    # Relative links in shipped instructions and the README must resolve.
    for path in [root / "README.md", root / "ACKNOWLEDGMENTS.md", root / "VALIDATION.md",
                 *(root / "skills").rglob("*.md")]:
        if not path.is_file():
            errors.append(f"missing {path.relative_to(root)}")
            continue
        text = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
        for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
            if re.match(r"[a-z]+://|#|mailto:", link):
                continue
            target = link.split("#", 1)[0]
            if target and not (path.parent / target).exists():
                errors.append(f"{path.relative_to(root)}: missing reference {link}")

    try:
        manifest = json.loads((root / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        if manifest.get("name") != PLUGIN:
            errors.append(f".claude-plugin/plugin.json: name must be {PLUGIN}")
        if not re.match(r"^\d+\.\d+\.\d+", str(manifest.get("version", ""))):
            errors.append(".claude-plugin/plugin.json: version must be semantic")
    except (OSError, ValueError) as exc:
        errors.append(f".claude-plugin/plugin.json: {exc}")

    try:
        market = json.loads((root / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
        if market["plugins"][0]["name"] != PLUGIN:
            errors.append(".claude-plugin/marketplace.json: plugin name mismatch")
    except (OSError, ValueError, KeyError, IndexError) as exc:
        errors.append(f".claude-plugin/marketplace.json: {exc}")

    if (root / ".codex-plugin").exists():
        errors.append(".codex-plugin must not exist; this is a Claude Code plugin only")
    if not (root / RUNNER).is_file():
        errors.append(f"missing {RUNNER}")
    if not (root / "LICENSE").is_file():
        errors.append("missing LICENSE")

    return errors


if __name__ == "__main__":
    failures = validate()
    print("\n".join(failures) if failures
          else "Plugin metadata, skill structure and references passed.")
    sys.exit(bool(failures))
