#!/usr/bin/env python3
"""Fix script for House Voice code issues."""

import re

# FIX 1: analytics.py - Fix critical issue (line 126) + VERSION + remove duplicate
print("Fixing analytics.py...")
with open("analytics.py", "r") as f:
    content = f.read()

# Remove duplicate VERSION on line 9
content = content.replace(
    '# VERSION 3.8.0\n"""House Voice Analytics Engine',
    '# VERSION 3.12.0\n"""House Voice Analytics Engine'
)

# Remove the duplicate VERSION 3.8.0 that was on line 9
lines = content.split('\n')
new_lines = []
skip_next_version = False
for i, line in enumerate(lines):
    if i == 8 and line.strip() == "# VERSION 3.8.0":  # Line 9 (0-indexed as 8)
        skip_next_version = True
        continue
    new_lines.append(line)
content = '\n'.join(new_lines)

# Add DOMAIN import
if "from .const import DOMAIN" not in content:
    content = content.replace(
        "import statistics",
        "import statistics\nfrom .const import DOMAIN"
    )

# Fix the critical bug on line 126
content = content.replace(
    'chains = self.execution_history.hass.data[self.execution_history.domain]["chains"]',
    'chains = self.execution_history.hass.data.get(DOMAIN, {}).get("chains", {})'
)

with open("analytics.py", "w") as f:
    f.write(content)
print("✓ analytics.py fixed")

# FIX 2: __init__.py - Update VERSION
print("Fixing __init__.py...")
with open("__init__.py", "r") as f:
    content = f.read()
content = content.replace('# VERSION = "3.9.0"', '# VERSION = "3.12.0"')
with open("__init__.py", "w") as f:
    f.write(content)
print("✓ __init__.py fixed")

# FIX 3: storage.py - Update VERSION + implement chain_name lookup
print("Fixing storage.py...")
with open("storage.py", "r") as f:
    content = f.read()

content = content.replace('# VERSION = "3.6.0"', '# VERSION = "3.12.0"')

# Fix chain_name lookup
old_exec = '''        execution = {
            "id": execution_id,
            "chain_id": chain_id,
            "chain_name": chain_id,  # TODO: lookup from chains storage if available'''

new_exec = '''        # Get chain name from chains storage if available
        chain_name = chain_id
        try:
            if self.hass and DOMAIN in self.hass.data:
                chains_storage = self.hass.data[DOMAIN].get("chains", {})
                if chain_id in chains_storage:
                    chain_name = chains_storage[chain_id].get("name", chain_id)
        except Exception:
            pass  # Fallback to chain_id if lookup fails

        execution = {
            "id": execution_id,
            "chain_id": chain_id,
            "chain_name": chain_name,  # ← Now resolves from chains storage'''

content = content.replace(old_exec, new_exec)

with open("storage.py", "w") as f:
    f.write(content)
print("✓ storage.py fixed")

# FIX 4: Update VERSION in all other files
files_to_update = [
    ("voice_engine.py", "3.5.0", "3.12.0"),
    ("websocket.py", "3.11.0", "3.12.0"),
    ("const.py", "3.12.0", "3.12.0"),  # Already correct
    ("config_flow.py", "3.3.1", "3.12.0"),
    ("panel.py", "3.3.1", "3.12.0"),
    ("groups.py", "3.3.1", "3.12.0"),
    ("sensor.py", "3.3.1", "3.12.0"),
    ("system_health.py", "3.3.1", "3.12.0"),
    ("diagnostics.py", "3.3.1", "3.12.0"),
    ("repairs.py", "3.2.0", "3.12.0"),
    ("ultra_tts.py", "3.3.1", "3.12.0"),
    ("dag_executor.py", "3.5.0", "3.12.0"),
    ("chain_validator.py", "3.8.0", "3.12.0"),
]

for filename, old_version, new_version in files_to_update:
    try:
        with open(filename, "r") as f:
            content = f.read()
        
        # Update VERSION header
        content = re.sub(
            f'# VERSION = "{old_version}"',
            f'# VERSION = "{new_version}"',
            content
        )
        # Also handle VERSION without quotes
        content = re.sub(
            f'# VERSION {old_version}',
            f'# VERSION {new_version}',
            content
        )
        
        with open(filename, "w") as f:
            f.write(content)
        print(f"✓ {filename} updated to 3.12.0")
    except FileNotFoundError:
        print(f"⚠ {filename} not found (skipped)")

print("\n✅ All fixes applied successfully!")
print("\nSummary of fixes:")
print("1. analytics.py: Fixed critical AttributeError (line 126)")
print("2. analytics.py: Removed duplicate VERSION comment")
print("3. analytics.py: Updated VERSION to 3.12.0")
print("4. storage.py: Implemented chain_name lookup from chains storage")
print("5. __init__.py: Updated VERSION to 3.12.0")
print("6. All other files: Updated VERSION to 3.12.0")

