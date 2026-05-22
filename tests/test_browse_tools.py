"""
Smoke test for browse.sh browser tools in AgentSystem.

Run: python3 tests/test_browse_tools.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.browse_tools import browse_fetch, browse_snapshot, browse_interact, browse_shutdown


async def main():
    passed = 0
    failed = 0

    # ── Test 1: browse_fetch ──────────────────────────────────────────
    print("=" * 50)
    print("TEST 1: browse_fetch — fetch text from a JS-rendered page")
    print("=" * 50)
    try:
        result = await browse_fetch("https://httpbin.org/ip", max_chars=500)
        assert "origin" in result, f"Expected 'origin' in output, got: {result[:200]}"
        print(result[:300])
        print("  PASSED ✓")
        passed += 1
    except Exception as e:
        print(f"  FAILED ✗ — {e}")
        failed += 1

    # ── Test 2: browse_fetch (standard HTML) ──────────────────────────
    print()
    print("=" * 50)
    print("TEST 2: browse_fetch — HTML page with forms")
    print("=" * 50)
    try:
        result = await browse_fetch("https://httpbin.org/forms/post", max_chars=1000)
        assert any(w in result.lower() for w in ("customer", "pizza", "form")), \
            f"Expected form content, got: {result[:200]}"
        print(result[:300])
        print("  PASSED ✓")
        passed += 1
    except Exception as e:
        print(f"  FAILED ✗ — {e}")
        failed += 1

    # ── Test 3: browse_snapshot ───────────────────────────────────────
    print()
    print("=" * 50)
    print("TEST 3: browse_snapshot — interactive element tree")
    print("=" * 50)
    try:
        result = await browse_snapshot(url="https://httpbin.org/forms/post", compact=True)
        assert "@" not in result and "[" in result, \
            f"Expected accessibility tree with [refs], got: {result[:200]}"
        print(result[:400])
        print("  PASSED ✓")
        passed += 1
    except Exception as e:
        print(f"  FAILED ✗ — {e}")
        failed += 1

    # ── Test 4: browse_interact (screenshot) ──────────────────────────
    print()
    print("=" * 50)
    print("TEST 4: browse_interact — screenshot")
    print("=" * 50)
    try:
        result = await browse_interact(action="screenshot")
        assert "Screenshot saved" in result, f"Expected screenshot confirmation, got: {result}"
        print(result)
        print("  PASSED ✓")
        passed += 1
    except Exception as e:
        print(f"  FAILED ✗ — {e}")
        failed += 1

    # ── Cleanup ───────────────────────────────────────────────────────
    print()
    print("=" * 50)
    await browse_shutdown()

    print(f"\n  RESULTS: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
