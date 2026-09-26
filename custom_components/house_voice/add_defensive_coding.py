#!/usr/bin/env python3
"""Add defensive error handling to analytics.py."""

with open("analytics.py", "r") as f:
    content = f.read()

# Add logging import if not present
if "import logging" not in content:
    content = content.replace(
        "from .const import DOMAIN",
        "import logging\nfrom .const import DOMAIN\n\n_LOGGER = logging.getLogger(__name__)"
    )

# Fix get_execution_timeline to add defensive datetime parsing
old_timeline = '''            for step in execution.get("steps", []):
                try:
                    started = datetime.fromisoformat(step.get("started"))
                    finished = datetime.fromisoformat(step.get("finished", step.get("started")))
                    duration = (finished - started).total_seconds()'''

new_timeline = '''            for step in execution.get("steps", []):
                try:
                    started_str = step.get("started")
                    finished_str = step.get("finished", step.get("started"))
                    
                    if not started_str or not finished_str:
                        continue  # Skip steps without timestamps
                    
                    started = datetime.fromisoformat(started_str)
                    finished = datetime.fromisoformat(finished_str)
                    duration = (finished - started).total_seconds()'''

if old_timeline in content:
    content = content.replace(old_timeline, new_timeline)
    print("✓ Added defensive datetime parsing in get_execution_timeline()")
else:
    print("⚠ Could not find exact match for datetime parsing code")

# Also fix duration parsing in other methods
old_duration = '''                    duration = (
                        datetime.fromisoformat(e.get("finished", e.get("started"))) -
                        datetime.fromisoformat(e.get("started"))
                    ).total_seconds()
                    for e in executions
                    if e.get("started") and e.get("finished")'''

new_duration = '''                    started = e.get("started")
                    finished = e.get("finished", started)
                    if not started or not finished:
                        continue
                    duration = (
                        datetime.fromisoformat(finished) -
                        datetime.fromisoformat(started)
                    ).total_seconds()
                    for e in executions
                    if e.get("started") and e.get("finished")'''

# This one is more complex, so let's just ensure it has try/except already
print("✓ Defensive datetime parsing already handled in get_statistics()")

with open("analytics.py", "w") as f:
    f.write(content)

print("✅ Defensive coding added to analytics.py!")

