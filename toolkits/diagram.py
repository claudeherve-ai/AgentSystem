"""
toolkits.diagram — deterministic Mermaid diagram generators (stdlib only).

Produces valid Mermaid source (flowchart, sequence, gantt) from structured JSON.
IDs and labels are sanitized/escaped so output always parses. The dashboard and
chat UIs render ```mermaid blocks. Fail-soft; no LLM, no network, no credentials.
"""
from __future__ import annotations

import json
import re
from typing import Annotated, Any

_ID_RE = re.compile(r"[^A-Za-z0-9_]")


def _loads(raw: str, label: str) -> Any:
    if raw is None or str(raw).strip() == "":
        raise ValueError(f"{label} is empty")
    return json.loads(raw)


def _safe_id(raw: Any, fallback: str) -> str:
    s = _ID_RE.sub("_", str(raw)).strip("_")
    if not s:
        return fallback
    if s[0].isdigit():
        s = "n_" + s
    return s


def _label(raw: Any) -> str:
    # Escape characters that break Mermaid node labels.
    return (str(raw).replace('"', "'").replace("\n", " ").replace("[", "(")
            .replace("]", ")").replace("{", "(").replace("}", ")").strip()) or " "


def mermaid_flowchart(
    nodes_json: Annotated[
        str,
        'JSON array of nodes, e.g. [{"id":"a","label":"Start","shape":"round"},'
        '{"id":"b","label":"Decide","shape":"diamond"}]. shape: rect|round|diamond|stadium.',
    ],
    edges_json: Annotated[
        str,
        'JSON array of edges, e.g. [{"from":"a","to":"b","label":"yes"}]',
    ],
    direction: Annotated[str, "Flow direction: TD (top-down), LR, RL, or BT"] = "TD",
) -> str:
    """Generate a valid Mermaid flowchart from nodes and edges (renders in the UI).

    Sanitizes node ids and escapes labels so the diagram always parses. Supports
    rect/round/diamond/stadium node shapes and labeled edges. Returns a fenced
    ```mermaid block ready to embed.
    """
    try:
        nodes = _loads(nodes_json, "nodes_json")
        edges = _loads(edges_json, "edges_json") if str(edges_json).strip() else []
        if not isinstance(nodes, list) or not nodes:
            return "❌ Error: nodes_json must be a non-empty JSON array"
        if not isinstance(edges, list):
            return "❌ Error: edges_json must be a JSON array"
        dir_ = direction.upper().strip()
        if dir_ not in {"TD", "TB", "LR", "RL", "BT"}:
            dir_ = "TD"

        idmap: dict[str, str] = {}
        lines = [f"flowchart {dir_}"]
        for i, nd in enumerate(nodes):
            orig = str(nd.get("id", f"n{i}"))
            nid = _safe_id(orig, f"n{i}")
            idmap[orig] = nid
            label = _label(nd.get("label", orig))
            shape = str(nd.get("shape", "rect")).lower()
            if shape == "round":
                lines.append(f'    {nid}("{label}")')
            elif shape == "diamond":
                lines.append(f'    {nid}{{"{label}"}}')
            elif shape == "stadium":
                lines.append(f'    {nid}(["{label}"])')
            else:
                lines.append(f'    {nid}["{label}"]')

        for e in edges:
            f_orig = str(e.get("from", ""))
            t_orig = str(e.get("to", ""))
            if f_orig not in idmap or t_orig not in idmap:
                continue  # skip dangling edge
            f, t = idmap[f_orig], idmap[t_orig]
            elabel = e.get("label")
            if elabel not in (None, ""):
                lines.append(f'    {f} -->|{_label(elabel)}| {t}')
            else:
                lines.append(f"    {f} --> {t}")
        return "```mermaid\n" + "\n".join(lines) + "\n```"
    except json.JSONDecodeError as e:
        return f"❌ Error: invalid JSON — {e}"
    except Exception as e:  # noqa: BLE001
        return f"❌ Error: {e}"


def mermaid_sequence(
    participants_json: Annotated[
        str, 'JSON array of participant names, e.g. ["User","API","DB"]'
    ],
    messages_json: Annotated[
        str,
        'JSON array of messages, e.g. [{"from":"User","to":"API","text":"login","async":false}]',
    ],
) -> str:
    """Generate a valid Mermaid sequence diagram from participants and messages.

    Solid arrows for sync, dashed for async (``"async":true``). Sanitizes
    participant aliases and escapes message text. Returns a fenced ```mermaid block.
    """
    try:
        parts = _loads(participants_json, "participants_json")
        msgs = _loads(messages_json, "messages_json") if str(messages_json).strip() else []
        if not isinstance(parts, list) or not parts:
            return "❌ Error: participants_json must be a non-empty JSON array"
        if not isinstance(msgs, list):
            return "❌ Error: messages_json must be a JSON array"

        alias: dict[str, str] = {}
        lines = ["sequenceDiagram"]
        for i, p in enumerate(parts):
            a = _safe_id(p, f"P{i}")
            alias[str(p)] = a
            lines.append(f'    participant {a} as {_label(p)}')
        for m in msgs:
            f_orig, t_orig = str(m.get("from", "")), str(m.get("to", ""))
            if f_orig not in alias or t_orig not in alias:
                continue
            arrow = "-->>" if m.get("async") else "->>"
            lines.append(f'    {alias[f_orig]}{arrow}{alias[t_orig]}: {_label(m.get("text", ""))}')
        return "```mermaid\n" + "\n".join(lines) + "\n```"
    except json.JSONDecodeError as e:
        return f"❌ Error: invalid JSON — {e}"
    except Exception as e:  # noqa: BLE001
        return f"❌ Error: {e}"


def mermaid_gantt(
    title: Annotated[str, "Chart title"],
    tasks_json: Annotated[
        str,
        'JSON array of tasks, e.g. [{"name":"Design","start":"2024-01-01","duration":"5d",'
        '"section":"Phase 1"}]. Use either start+duration, or after:"<taskId>".',
    ],
) -> str:
    """Generate a valid Mermaid Gantt chart from a task list grouped by section.

    Each task needs a name and either an explicit start date (YYYY-MM-DD) + duration
    (e.g. ``5d``) or an ``after`` reference. Sanitizes task ids and groups by
    section. Returns a fenced ```mermaid block.
    """
    try:
        tasks = _loads(tasks_json, "tasks_json")
        if not isinstance(tasks, list) or not tasks:
            return "❌ Error: tasks_json must be a non-empty JSON array"

        lines = ["gantt", f"    title {_label(title) or 'Schedule'}",
                 "    dateFormat YYYY-MM-DD"]
        sections: dict[str, list[dict[str, Any]]] = {}
        order: list[str] = []
        for t in tasks:
            sec = str(t.get("section", "Tasks")).strip() or "Tasks"
            if sec not in sections:
                sections[sec] = []
                order.append(sec)
            sections[sec].append(t)

        for idx, sec in enumerate(order):
            lines.append(f"    section {_label(sec)}")
            for j, t in enumerate(sections[sec]):
                name = _label(t.get("name", f"Task{j}"))
                tid = _safe_id(t.get("id", f"t{idx}_{j}"), f"t{idx}_{j}")
                after = t.get("after")
                start = t.get("start")
                duration = str(t.get("duration", "1d")).strip() or "1d"
                if after:
                    spec = f"after {_safe_id(after, 'prev')}, {duration}"
                elif start:
                    spec = f"{start}, {duration}"
                else:
                    spec = duration
                lines.append(f"    {name} :{tid}, {spec}")
        return "```mermaid\n" + "\n".join(lines) + "\n```"
    except json.JSONDecodeError as e:
        return f"❌ Error: invalid JSON — {e}"
    except Exception as e:  # noqa: BLE001
        return f"❌ Error: {e}"


DIAGRAM_TOOLS = [mermaid_flowchart, mermaid_sequence, mermaid_gantt]
