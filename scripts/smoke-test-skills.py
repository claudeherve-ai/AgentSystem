#!/usr/bin/env python3
"""
smoke-test-skills.py — Post-deploy verification that claude-skills are live.
Hits the cloud health endpoint and confirms skills are loaded.
"""
import subprocess
import json
import sys
import time

CLOUD_URL = "https://ca-agentsystem.mangoflower-d4b306b2.eastus2.azurecontainerapps.io"
API_URL = f"{CLOUD_URL}:8080"
MAX_RETRIES = 10
RETRY_DELAY = 6  # seconds

def check_skills():
    """Hit the health endpoint and verify skill count."""
    try:
        result = subprocess.run(
            ["curl", "-sf", f"{API_URL}/health"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            return None, f"curl failed (exit {result.returncode}): {result.stderr[:200]}"

        data = json.loads(result.stdout)
        skills = data.get("skills", {})
        return skills, None

    except subprocess.TimeoutExpired:
        return None, "health endpoint timed out"
    except json.JSONDecodeError as e:
        return None, f"invalid JSON: {e}"
    except Exception as e:
        return None, str(e)

def main():
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  🔍 Post-Deploy Skills Smoke Test")
    print(f"  Target: {API_URL}/health")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    for attempt in range(1, MAX_RETRIES + 1):
        skills, error = check_skills()

        if error:
            print(f"  [{attempt}/{MAX_RETRIES}] ⏳ Waiting... ({error})")
            time.sleep(RETRY_DELAY)
            continue

        # Got a response — validate
        status = skills.get("status", "unknown")
        count = skills.get("count", 0)
        domains = skills.get("domains", 0)
        path = skills.get("path", "?")
        exists = skills.get("exists", False)

        print(f"\n  Skills path:  {path}")
        print(f"  Path exists:  {exists}")
        print(f"  Skill count:  {count}")
        print(f"  Domains:      {domains}")
        print(f"  Status:       {status}")

        if count >= 100:
            print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print(f"  ✅ PASS — {count} skills across {domains} domains")
            print("  Agents are NOT dumb.")
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            sys.exit(0)
        elif count > 0:
            print(f"\n  ⚠️  DEGRADED — only {count} skills loaded (expected 300+)")
            sys.exit(2)
        else:
            print(f"\n  ❌ FAIL — zero skills detected. Agents ARE dumb.")
            sys.exit(1)

    print(f"\n  ❌ FAIL — health endpoint unreachable after {MAX_RETRIES * RETRY_DELAY}s")
    sys.exit(1)

if __name__ == "__main__":
    main()