"""
toolkits.reasoning — deterministic decision & planning compute tools.

Every function:
- takes JSON-string args (parsed with json.loads),
- performs REAL computation (no LLM, no network, no credentials),
- returns a human-readable, structured ``str``,
- fails soft (returns ``"❌ Error: ..."`` instead of raising).

These give every agent grounded reasoning primitives: weighted decisions,
quantitative risk scoring, and dependency-aware task decomposition.
"""
from __future__ import annotations

import json
from typing import Annotated, Any


def _loads(raw: str, label: str) -> Any:
    if raw is None or str(raw).strip() == "":
        raise ValueError(f"{label} is empty")
    return json.loads(raw)


def decision_matrix(
    options_json: Annotated[
        str,
        'JSON array of options, e.g. [{"name":"AWS","scores":{"Cost":7,"Speed":9}}, ...]',
    ],
    criteria_json: Annotated[
        str,
        'JSON array of criteria with weights, e.g. [{"name":"Cost","weight":0.4},{"name":"Speed","weight":0.6}]',
    ],
) -> str:
    """Score options against weighted criteria and rank them (weighted decision matrix).

    Weights are auto-normalized to sum to 1.0. Each option is scored per criterion
    (missing scores treated as 0). Returns ranked options with weighted totals, the
    recommended winner, the margin over runner-up, and a sensitivity note.
    """
    try:
        criteria = _loads(criteria_json, "criteria_json")
        options = _loads(options_json, "options_json")
        if not isinstance(criteria, list) or not criteria:
            return "❌ Error: criteria_json must be a non-empty JSON array"
        if not isinstance(options, list) or not options:
            return "❌ Error: options_json must be a non-empty JSON array"

        crit: list[tuple[str, float]] = []
        for c in criteria:
            name = str(c.get("name", "")).strip()
            if not name:
                return "❌ Error: every criterion needs a non-empty 'name'"
            weight = float(c.get("weight", 1.0))
            if weight < 0:
                return f"❌ Error: criterion '{name}' has negative weight"
            crit.append((name, weight))
        total_w = sum(w for _, w in crit)
        if total_w <= 0:
            return "❌ Error: criteria weights sum to zero — cannot normalize"
        norm = [(n, w / total_w) for n, w in crit]

        results: list[tuple[str, float, dict[str, float]]] = []
        for opt in options:
            name = str(opt.get("name", "")).strip() or "(unnamed)"
            scores = opt.get("scores", {}) or {}
            contrib: dict[str, float] = {}
            total = 0.0
            for cname, w in norm:
                raw = scores.get(cname, 0)
                try:
                    val = float(raw)
                except (TypeError, ValueError):
                    val = 0.0
                contrib[cname] = val * w
                total += val * w
            results.append((name, total, contrib))

        results.sort(key=lambda r: r[1], reverse=True)

        lines = ["# Decision Matrix", "", "**Normalized weights:**"]
        lines += [f"- {n}: {w:.1%}" for n, w in norm]
        lines += ["", "**Ranked options (weighted score):**"]
        for rank, (name, total, _contrib) in enumerate(results, 1):
            marker = " 🏆" if rank == 1 else ""
            lines.append(f"{rank}. {name}: **{total:.3f}**{marker}")

        winner, win_score, _ = results[0]
        lines += ["", f"**Recommendation:** {winner} (score {win_score:.3f})"]
        if len(results) > 1:
            runner, run_score, _ = results[1]
            margin = win_score - run_score
            pct = (margin / run_score * 100) if run_score else float("inf")
            close = margin < 0.05 * (win_score or 1)
            lines.append(
                f"**Margin over runner-up ({runner}):** {margin:.3f}"
                + (f" ({pct:.1f}%)" if pct != float("inf") else "")
            )
            if close:
                lines.append(
                    "⚠️ Warning: top two options are close — result is sensitive to "
                    "weighting; revisit criterion weights or gather more data."
                )
        return "\n".join(lines)
    except json.JSONDecodeError as e:
        return f"❌ Error: invalid JSON — {e}"
    except Exception as e:  # noqa: BLE001 - fail soft per tool contract
        return f"❌ Error: {e}"


def risk_register(
    risks_json: Annotated[
        str,
        'JSON array of risks, e.g. [{"risk":"Vendor lock-in","likelihood":4,"impact":5,'
        '"mitigation":"Abstraction layer","owner":"Platform"}]. likelihood/impact are 1-5.',
    ],
) -> str:
    """Quantify and prioritize risks (likelihood × impact = severity, RAG-rated, sorted).

    Likelihood and impact are clamped to 1-5. Severity = L×I (1-25). Rated
    🔴 Red (>=15), 🟠 Amber (8-14), 🟢 Green (<8). Returns a sorted register plus
    an exposure summary and the count of Red risks needing immediate mitigation.
    """
    try:
        risks = _loads(risks_json, "risks_json")
        if not isinstance(risks, list) or not risks:
            return "❌ Error: risks_json must be a non-empty JSON array"

        def clamp(v: Any) -> int:
            try:
                n = int(round(float(v)))
            except (TypeError, ValueError):
                n = 1
            return max(1, min(5, n))

        rows = []
        for r in risks:
            name = str(r.get("risk", r.get("name", ""))).strip() or "(unnamed risk)"
            likelihood = clamp(r.get("likelihood", 1))
            impact = clamp(r.get("impact", 1))
            severity = likelihood * impact
            if severity >= 15:
                rag = "🔴 Red"
            elif severity >= 8:
                rag = "🟠 Amber"
            else:
                rag = "🟢 Green"
            mitigation = str(r.get("mitigation", "")).strip() or "— (none provided)"
            owner = str(r.get("owner", "")).strip() or "Unassigned"
            rows.append((severity, likelihood, impact, rag, name, mitigation, owner))

        rows.sort(key=lambda x: x[0], reverse=True)
        reds = sum(1 for x in rows if x[0] >= 15)
        ambers = sum(1 for x in rows if 8 <= x[0] < 15)
        avg = sum(x[0] for x in rows) / len(rows)

        lines = ["# Risk Register", "", "| # | Risk | L | I | Severity | RAG | Owner | Mitigation |",
                 "|---|------|---|---|----------|-----|-------|------------|"]
        for i, (sev, l, im, rag, name, mit, owner) in enumerate(rows, 1):
            lines.append(f"| {i} | {name} | {l} | {im} | {sev} | {rag} | {owner} | {mit} |")
        lines += [
            "",
            f"**Total risks:** {len(rows)} | **Red:** {reds} | **Amber:** {ambers} | "
            f"**Avg severity:** {avg:.1f}/25",
        ]
        if reds:
            lines.append(
                f"⚠️ {reds} Red risk(s) require immediate mitigation and an assigned owner."
            )
        return "\n".join(lines)
    except json.JSONDecodeError as e:
        return f"❌ Error: invalid JSON — {e}"
    except Exception as e:  # noqa: BLE001
        return f"❌ Error: {e}"


def decompose_task(
    goal: Annotated[str, "The overall goal/objective being decomposed"],
    subtasks_json: Annotated[
        str,
        'JSON array of subtasks, e.g. [{"id":"t1","name":"Design schema","deps":[]},'
        '{"id":"t2","name":"Build API","deps":["t1"]}]. deps reference other ids.',
    ],
) -> str:
    """Order subtasks by dependencies (topological sort) into parallelizable waves.

    Validates for duplicate ids, missing dependency references, and cycles (reports
    the cycle path). Returns execution "waves" (sets of tasks that can run in
    parallel), the critical-path length, and total task count.
    """
    try:
        subtasks = _loads(subtasks_json, "subtasks_json")
        if not isinstance(subtasks, list) or not subtasks:
            return "❌ Error: subtasks_json must be a non-empty JSON array"

        names: dict[str, str] = {}
        deps: dict[str, list[str]] = {}
        order_seen: list[str] = []
        for t in subtasks:
            tid = str(t.get("id", "")).strip()
            if not tid:
                return "❌ Error: every subtask needs a non-empty 'id'"
            if tid in names:
                return f"❌ Error: duplicate subtask id '{tid}'"
            names[tid] = str(t.get("name", tid)).strip() or tid
            raw_deps = t.get("deps", t.get("depends_on", [])) or []
            if not isinstance(raw_deps, list):
                return f"❌ Error: deps for '{tid}' must be a JSON array"
            deps[tid] = [str(d).strip() for d in raw_deps if str(d).strip()]
            order_seen.append(tid)

        for tid, dlist in deps.items():
            for d in dlist:
                if d not in names:
                    return f"❌ Error: subtask '{tid}' depends on unknown id '{d}'"
                if d == tid:
                    return f"❌ Error: subtask '{tid}' depends on itself"

        # Kahn's algorithm in waves (preserve input order within a wave).
        indeg = {tid: len(set(deps[tid])) for tid in names}
        remaining = set(names)
        waves: list[list[str]] = []
        while remaining:
            ready = [tid for tid in order_seen if tid in remaining and indeg[tid] == 0]
            if not ready:
                cycle = _find_cycle(deps, remaining)
                path = " → ".join(cycle) if cycle else ", ".join(sorted(remaining))
                return f"❌ Error: dependency cycle detected: {path}"
            waves.append(ready)
            for tid in ready:
                remaining.discard(tid)
            for tid in remaining:
                indeg[tid] = sum(1 for d in set(deps[tid]) if d in remaining)

        lines = [f"# Task Decomposition: {goal.strip() or '(unnamed goal)'}", "",
                 f"**{len(names)} subtasks** organized into **{len(waves)} execution wave(s)** "
                 f"(critical path = {len(waves)} step(s)):", ""]
        for i, wave in enumerate(waves, 1):
            par = " (parallel)" if len(wave) > 1 else ""
            lines.append(f"**Wave {i}{par}:**")
            for tid in wave:
                dtxt = f"  ←  needs: {', '.join(deps[tid])}" if deps[tid] else ""
                lines.append(f"  - [{tid}] {names[tid]}{dtxt}")
            lines.append("")
        max_par = max(len(w) for w in waves)
        lines.append(
            f"**Max parallelism:** {max_par} task(s) at once | "
            f"**Sequential floor:** {len(waves)} wave(s)"
        )
        return "\n".join(lines).rstrip()
    except json.JSONDecodeError as e:
        return f"❌ Error: invalid JSON — {e}"
    except Exception as e:  # noqa: BLE001
        return f"❌ Error: {e}"


def _find_cycle(deps: dict[str, list[str]], nodes: set[str]) -> list[str]:
    """Return one cycle path among ``nodes`` (best effort) for diagnostics."""
    color: dict[str, int] = {n: 0 for n in nodes}  # 0=white,1=gray,2=black
    stack: list[str] = []

    def dfs(n: str) -> list[str]:
        color[n] = 1
        stack.append(n)
        for d in deps.get(n, []):
            if d not in nodes:
                continue
            if color[d] == 1:
                idx = stack.index(d)
                return stack[idx:] + [d]
            if color[d] == 0:
                res = dfs(d)
                if res:
                    return res
        stack.pop()
        color[n] = 2
        return []

    for n in nodes:
        if color[n] == 0:
            res = dfs(n)
            if res:
                return res
    return []


REASONING_TOOLS = [decision_matrix, risk_register, decompose_task]
