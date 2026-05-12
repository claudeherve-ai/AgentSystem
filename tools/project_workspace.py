"""
Project workspace tool — multi-day project state for long-running engagements.

Each project lives in `memory/projects/<slug>/` with:
  - meta.json       (name, description, created, last_active, tags)
  - notes.md        (running engineering log, append-only)
  - timeline.json   (structured events: status changes, decisions, links)
  - artifacts/      (files the agent produced for this project)

The "active" project is tracked in `memory/active_project.json` so subsequent
notes / file reads default to its scope.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from pydantic import Field

from .audit import audit_log

logger = logging.getLogger(__name__)

PROJECTS_DIR = Path(__file__).resolve().parent.parent / "memory" / "projects"
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
ACTIVE_FILE = Path(__file__).resolve().parent.parent / "memory" / "active_project.json"


def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip().lower())
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "project"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _project_dir(slug: str) -> Path:
    return PROJECTS_DIR / slug


def _set_active(slug: str | None) -> None:
    if slug is None:
        if ACTIVE_FILE.exists():
            ACTIVE_FILE.unlink()
        return
    ACTIVE_FILE.write_text(json.dumps({"slug": slug}), encoding="utf-8")


def _get_active() -> str | None:
    if not ACTIVE_FILE.exists():
        return None
    try:
        return json.loads(ACTIVE_FILE.read_text(encoding="utf-8")).get("slug")
    except Exception:  # noqa: BLE001
        return None


async def project_create(
    name: Annotated[str, Field(description="Display name of the project")],
    description: Annotated[str, Field(description="One-paragraph description / mission")] = "",
    tags: Annotated[str, Field(description="Comma-separated tags (e.g. 'azure,databricks,customer-x')")] = "",
) -> str:
    """Create a new project workspace and set it as active."""
    audit_id = audit_log("Project.create", "started", {"name": name})
    slug = _slug(name)
    pdir = _project_dir(slug)
    if pdir.exists():
        _set_active(slug)
        return f"Project {slug!r} already exists. Set as active."
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "artifacts").mkdir(exist_ok=True)
    meta = {
        "slug": slug,
        "name": name,
        "description": description,
        "tags": [t.strip() for t in tags.split(",") if t.strip()],
        "created": _now(),
        "last_active": _now(),
        "status": "active",
    }
    (pdir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (pdir / "notes.md").write_text(f"# {name}\n\n{description}\n", encoding="utf-8")
    (pdir / "timeline.json").write_text(
        json.dumps([{"ts": _now(), "event": "created", "detail": name}], indent=2),
        encoding="utf-8",
    )
    _set_active(slug)
    audit_log("Project.create", "completed", {"slug": slug}, parent_id=audit_id)
    return f"Created project {slug!r} ({pdir}) and set as active."


async def project_open(
    name: Annotated[str, Field(description="Project name or slug to switch to")],
) -> str:
    """Switch the active project."""
    slug = _slug(name)
    if not _project_dir(slug).exists():
        return f"No such project: {slug}"
    _set_active(slug)
    pdir = _project_dir(slug)
    try:
        meta = json.loads((pdir / "meta.json").read_text(encoding="utf-8"))
        meta["last_active"] = _now()
        (pdir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return f"Active project: {slug}"


async def project_note(
    text: Annotated[str, Field(description="Note text to append to the active project's log")],
    project: Annotated[str, Field(description="Project name/slug (defaults to active)")] = "",
) -> str:
    """Append a timestamped note to the project's running log."""
    slug = _slug(project) if project else _get_active()
    if not slug:
        return "No active project. Use project_open or project_create first."
    pdir = _project_dir(slug)
    if not pdir.exists():
        return f"Project not found: {slug}"
    notes = pdir / "notes.md"
    notes.parent.mkdir(parents=True, exist_ok=True)
    with notes.open("a", encoding="utf-8") as fh:
        fh.write(f"\n## {_now()}\n{text}\n")
    return f"Note added to {slug}."


async def project_status(
    project: Annotated[str, Field(description="Project name/slug (defaults to active)")] = "",
) -> str:
    """Return a Markdown summary of a project (meta + last 20 notes + artifacts)."""
    slug = _slug(project) if project else _get_active()
    if not slug:
        return "No active project."
    pdir = _project_dir(slug)
    if not pdir.exists():
        return f"Project not found: {slug}"

    try:
        meta = json.loads((pdir / "meta.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        meta = {"slug": slug, "name": slug}
    notes_text = ""
    notes_path = pdir / "notes.md"
    if notes_path.exists():
        notes_text = notes_path.read_text(encoding="utf-8", errors="replace")
        sections = re.split(r"^## ", notes_text, flags=re.MULTILINE)
        recent = sections[-20:] if len(sections) > 20 else sections
        notes_text = "## ".join(recent) if recent else notes_text

    artifacts = []
    art_dir = pdir / "artifacts"
    if art_dir.exists():
        for f in sorted(art_dir.glob("**/*"))[:50]:
            if f.is_file():
                artifacts.append(f"- {f.relative_to(pdir)}")

    out = [
        f"# Project: {meta.get('name', slug)} ({slug})",
        f"_Status: {meta.get('status','active')} • created {meta.get('created','?')} • last active {meta.get('last_active','?')}_",
        f"_Tags: {', '.join(meta.get('tags', [])) or '(none)'}_",
        "",
        meta.get("description", ""),
        "",
        "## Recent notes",
        notes_text or "(none)",
    ]
    if artifacts:
        out.append("\n## Artifacts")
        out.extend(artifacts)
    return "\n".join(out)


async def project_list() -> str:
    """List every project workspace."""
    items = []
    active = _get_active()
    for pdir in sorted(PROJECTS_DIR.iterdir()):
        if not pdir.is_dir():
            continue
        try:
            meta = json.loads((pdir / "meta.json").read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        marker = " ⭐ ACTIVE" if pdir.name == active else ""
        items.append(
            f"- **{pdir.name}** — {meta.get('name','?')} "
            f"(status: {meta.get('status','active')}, last active {meta.get('last_active','?')}){marker}"
        )
    if not items:
        return "No projects yet. Use project_create to start one."
    return "# Projects\n" + "\n".join(items)


async def project_archive(
    project: Annotated[str, Field(description="Project name/slug to archive")],
) -> str:
    """Archive a project (sets status=archived; keeps files)."""
    slug = _slug(project)
    pdir = _project_dir(slug)
    if not pdir.exists():
        return f"Project not found: {slug}"
    try:
        meta = json.loads((pdir / "meta.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        meta = {"slug": slug}
    meta["status"] = "archived"
    meta["archived_at"] = _now()
    (pdir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if _get_active() == slug:
        _set_active(None)
    return f"Project {slug!r} archived."


PROJECT_WORKSPACE_TOOLS = [
    project_create,
    project_open,
    project_note,
    project_status,
    project_list,
    project_archive,
]
