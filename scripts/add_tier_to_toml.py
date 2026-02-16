#!/usr/bin/env python3
"""Add tier field to all task.toml files based on --tier in test.sh."""
import os
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent

def extract_tier(test_sh_path):
    content = test_sh_path.read_text()
    m = re.search(r'--tier\s+"([^"]+)"', content)
    return m.group(1) if m else None

def add_tier_to_toml(toml_path, tier):
    content = toml_path.read_text()
    if f'tier = "{tier}"' in content:
        return False  # already has it
    # Insert after difficulty line
    new_content = re.sub(
        r'(difficulty\s*=\s*"[^"]+"\n)',
        rf'\1tier = "{tier}"\n',
        content,
        count=1,
    )
    if new_content == content:
        # Fallback: insert after [metadata] section's last known field
        new_content = re.sub(
            r'(language\s*=\s*"[^"]+"\n)',
            rf'\1tier = "{tier}"\n',
            content,
            count=1,
        )
    if new_content != content:
        toml_path.write_text(new_content)
        return True
    return False

langs = ["python", "js", "go", "ruby", "java", "kotlin", "csharp", "rust", "cpp"]
updated = 0
for lang in langs:
    lang_path = ROOT / lang
    if not lang_path.is_dir():
        continue
    for env_name in sorted(os.listdir(lang_path)):
        env_path = lang_path / env_name
        test_sh = env_path / "tests" / "test.sh"
        toml_path = env_path / "task.toml"
        if not test_sh.exists() or not toml_path.exists():
            continue
        tier = extract_tier(test_sh)
        if not tier:
            print(f"SKIP: {lang}/{env_name} - no tier in test.sh")
            continue
        if add_tier_to_toml(toml_path, tier):
            print(f"OK:   {lang}/{env_name} -> tier = \"{tier}\"")
            updated += 1
        else:
            print(f"SKIP: {lang}/{env_name} - already has tier")

print(f"\nUpdated {updated} task.toml files")
