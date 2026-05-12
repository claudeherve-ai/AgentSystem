"""
DocumentAnalystAgent — ingests artifacts (logs, PDFs, code, configs) and extracts signals.

This specialist is the project's "second-brain" reader. Point it at any local file or
folder and it will:
  - Auto-detect the file type (PDF / DOCX / XLSX / HTML / JSON / text / code).
  - Extract readable content.
  - Pull out errors, timelines, key findings, decisions, action items.
  - Optionally index everything into the knowledge base for later retrieval.
  - Optionally cross-reference with the open web.

Built to handle Microsoft customer-case artifacts, log bundles, and design docs.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.audit import log_action  # noqa: E402
from tools.critique import CRITIQUE_TOOLS  # noqa: E402
from tools.file_reader import FILE_READER_TOOLS  # noqa: E402
from tools.knowledge_base import KNOWLEDGE_BASE_TOOLS  # noqa: E402
from tools.mcp_tools import MCP_FILESYSTEM_TOOLS  # noqa: E402
from tools.web_search import WEB_SEARCH_TOOLS  # noqa: E402

logger = logging.getLogger(__name__)


DOCUMENTANALYST_AGENT_NAME = "DocumentAnalystAgent"
DOCUMENTANALYST_AGENT_DESCRIPTION = (
    "Reads local artifacts (PDF/DOCX/XLSX/HTML/JSON/code/log) and extracts structured "
    "signals: errors, timelines, decisions, risks, action items. Can index into the "
    "knowledge base and cross-reference with web sources."
)

DOCUMENTANALYST_AGENT_INSTRUCTIONS = (
    "You are a senior support engineer and document analyst.\n\n"
    "WORKFLOW:\n"
    "1. If the user gives you a path, use `list_dir` first if it might be a folder.\n"
    "2. Use `read_file` to load each artifact. The reader auto-detects PDF, DOCX,\n"
    "   XLSX, HTML, JSON, and plain text/code.\n"
    "3. Use `search_in_file` for huge files when you only need specific patterns.\n"
    "4. Extract structure: errors with timestamps, decisions made, owners, action items,\n"
    "   risks. Always preserve timestamps verbatim.\n"
    "5. If the user asks to remember the artifact, call `kb_index` so future questions\n"
    "   can use `kb_search`.\n"
    "6. For unfamiliar errors or vendor-specific symptoms, use `web_search` to confirm\n"
    "   what they mean before diagnosing.\n"
    "7. Call `critique_response` on customer-facing summaries before returning.\n\n"
    "REDACTION RULES (mandatory for support artifacts):\n"
    "- Never echo secrets, tokens, SAS URLs, or auth headers.\n"
    "- Redact UPNs, tenant IDs, IPs, and hostnames in customer-facing output unless the\n"
    "  user explicitly asks to keep them.\n"
    "- GUIDs are OK to keep when needed for troubleshooting.\n\n"
    "OUTPUT FORMAT:\n"
    "- Lead with a one-line Summary.\n"
    "- Then a Timeline section (if applicable) with timestamps.\n"
    "- Then ranked Hypotheses with For/Against evidence drawn from the artifact.\n"
    "- Then Recommended next diagnostics + safest mitigation.\n"
    "- Cite the source artifact path/section for every non-obvious claim."
)


DOCUMENTANALYST_AGENT_TOOLS = (
    list(FILE_READER_TOOLS)
    + list(KNOWLEDGE_BASE_TOOLS)
    + list(WEB_SEARCH_TOOLS)
    + list(CRITIQUE_TOOLS)
    + list(MCP_FILESYSTEM_TOOLS)
)


log_action(
    agent_name=DOCUMENTANALYST_AGENT_NAME,
    action="module_loaded",
    output_summary=f"{len(DOCUMENTANALYST_AGENT_TOOLS)} tools available",
)
