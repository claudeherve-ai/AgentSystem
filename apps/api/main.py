"""apps.api — FastAPI application entrypoint.

Reuses the existing :mod:`api` package composition root rather than duplicating
it. Container images and process managers run:

    uvicorn apps.api.main:app --host 0.0.0.0 --port 8080

The ``app`` object is the same durable, multi-tenant FastAPI app defined in
``api.main`` (durable run service, structured errors, Easy Auth / Entra JWT
identity, shared rate limiting, and truthful health).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure the repository root is importable when launched as ``apps.api.main``.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from api.main import app, create_app  # noqa: E402,F401

__all__ = ["app", "create_app"]


def main() -> None:
    import uvicorn

    port = int(os.getenv("API_PORT", "8080"))
    uvicorn.run("apps.api.main:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
