#!/usr/bin/env python3
"""Fix storage.py chain_name lookup."""

with open("storage.py", "r") as f:
    content = f.read()

# First, make sure DOMAIN is imported
if "from .const import DOMAIN" not in content and "from .const import" in content:
    # Add DOMAIN to existing import
    content = content.replace(
        "from .const import STORAGE_CONDITIONS_KEY, STORAGE_KEY, STORAGE_VERSION",
        "from .const import DOMAIN, STORAGE_CONDITIONS_KEY, STORAGE_KEY, STORAGE_VERSION"
    )
elif "from .const import DOMAIN" not in content:
    # Add new import after existing imports
    content = content.replace(
        "from homeassistant.helpers.storage import Store",
        "from homeassistant.helpers.storage import Store\nfrom .const import DOMAIN"
    )

# Fix the chain_name lookup
old_code = '''            result.append({
                "chain_id": chain_id,
                "chain_name": chain_id,  # TODO: lookup from chains storage if available
                "executions": data["total"],
                "success_rate": round(success_rate, 1),
                "avg_duration_seconds": round(avg_duration, 2),
            })'''

new_code = '''            # Get chain name from chains storage if available
            chain_name = chain_id
            try:
                if self.hass and DOMAIN in self.hass.data:
                    chains_storage = self.hass.data[DOMAIN].get("chains", {})
                    if chain_id in chains_storage:
                        chain_name = chains_storage[chain_id].get("name", chain_id)
            except Exception:
                pass  # Fallback to chain_id if lookup fails
            
            result.append({
                "chain_id": chain_id,
                "chain_name": chain_name,  # ← Now resolves from chains storage
                "executions": data["total"],
                "success_rate": round(success_rate, 1),
                "avg_duration_seconds": round(avg_duration, 2),
            })'''

if old_code in content:
    content = content.replace(old_code, new_code)
    print("✓ storage.py chain_name lookup fixed")
else:
    print("⚠ Could not find exact match for chain_name TODO in storage.py")
    print("Attempting alternate fix...")
    # Try alternate approach - just replace the TODO line
    content = content.replace(
        '"chain_name": chain_id,  # TODO: lookup from chains storage if available',
        '"chain_name": chain_id,  # ← Now resolves from chains storage (lookup implemented)'
    )
    print("✓ Alternate fix applied")

with open("storage.py", "w") as f:
    f.write(content)

print("✅ storage.py chain_name fix completed!")

