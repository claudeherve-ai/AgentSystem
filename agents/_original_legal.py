"""
Proxy module that re-exports the original legal_agent tools.
This exists so the merged legal_agent.py can import from the original
without circular imports.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Re-export the original legal agent's async tools under the same names
from tools.audit import log_action as _log_action  # noqa: E402

# The original legal_agent module content is loaded via importlib to avoid
# shadowing by the merged file of the same name.
import importlib.util as _iu
import types as _types

_ORIGINAL_PATH = Path(__file__).resolve().parent / "legal_agent.py"

# Load the original source as a separate module
_spec = _iu.spec_from_file_location("_original_legal_agent", _ORIGINAL_PATH)
_original = _iu.module_from_spec(_spec)
_spec.loader.exec_module(_original)

# Export the async tools from the original legal agent
draft_legal_document = _original.draft_legal_document
analyze_compliance = _original.analyze_compliance
review_contract = _original.review_contract
create_rfp_response = _original.create_rfp_response
generate_privacy_policy = _original.generate_privacy_policy
legal_research = _original.legal_research
