"""
toolkits.textutils — text diffing & comparison (stdlib only).

Computes unified/side-by-side diffs and change summaries using `difflib`.
Deterministic; fail-soft; no LLM, no network, no credentials.
"""
from __future__ import annotations

import difflib
from typing import Annotated

_MAX = 200_000


def text_diff(
    before: Annotated[str, "Original text"],
    after: Annotated[str, "Revised text"],
    mode: Annotated[str, "Diff style: 'unified' (default), 'context', or 'summary'"] = "unified",
) -> str:
    """Diff two blocks of text and summarize additions/removals (stdlib difflib).

    'unified' returns a unified diff, 'context' a context diff, and 'summary' just
    the counts plus the changed lines. Guards against oversized input. Useful for
    comparing config/code/document revisions deterministically.
    """
    try:
        a = str(before)
        b = str(after)
        if len(a) > _MAX or len(b) > _MAX:
            return f"❌ Error: input too large (limit {_MAX} chars each)"
        a_lines = a.splitlines()
        b_lines = b.splitlines()

        added = 0
        removed = 0
        sm = difflib.SequenceMatcher(a=a_lines, b=b_lines)
        ratio = sm.ratio()
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag in ("replace", "delete"):
                removed += (i2 - i1)
            if tag in ("replace", "insert"):
                added += (j2 - j1)

        header = (f"# Text Diff\n\n"
                  f"**Similarity:** {ratio * 100:.1f}% | "
                  f"**+{added} added / -{removed} removed lines**\n")

        m = mode.lower().strip()
        if m == "summary":
            changed = []
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == "delete":
                    changed += [f"- {ln}" for ln in a_lines[i1:i2]]
                elif tag == "insert":
                    changed += [f"+ {ln}" for ln in b_lines[j1:j2]]
                elif tag == "replace":
                    changed += [f"- {ln}" for ln in a_lines[i1:i2]]
                    changed += [f"+ {ln}" for ln in b_lines[j1:j2]]
            body = "\n".join(changed[:400]) if changed else "(no line-level changes)"
            return f"{header}\n```diff\n{body}\n```"

        if m == "context":
            diff = difflib.context_diff(a_lines, b_lines, "before", "after", lineterm="")
        else:
            diff = difflib.unified_diff(a_lines, b_lines, "before", "after", lineterm="")
        body = "\n".join(list(diff)[:600])
        if not body.strip():
            body = "(texts are identical)"
        return f"{header}\n```diff\n{body}\n```"
    except Exception as e:  # noqa: BLE001
        return f"❌ Error: {e}"


TEXT_TOOLS = [text_diff]
