"""
CodeExecutorAgent — sandboxed code execution and file analysis.

This specialist runs Python code, parses files, and verifies its own output. Use it
for any request that requires actually computing something, transforming data, parsing
a log file, generating a chart, or validating a script before handing it back.

Code runs inside `memory/workspace/`, so artifacts persist between calls and can be
referenced by later turns. Shell access is denylisted — destructive commands are blocked.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.audit import log_action  # noqa: E402
from tools.code_interpreter import CODE_INTERPRETER_TOOLS  # noqa: E402
from tools.critique import CRITIQUE_TOOLS  # noqa: E402
from tools.file_reader import FILE_READER_TOOLS  # noqa: E402

logger = logging.getLogger(__name__)


CODEEXECUTOR_AGENT_NAME = "CodeExecutorAgent"
CODEEXECUTOR_AGENT_DESCRIPTION = (
    "Sandboxed Python execution + file inspection. Use when the request requires "
    "actually running code, parsing logs, transforming data, generating output files, "
    "or validating a script end-to-end."
)

CODEEXECUTOR_AGENT_INSTRUCTIONS = (
    "You are a senior software engineer with a sandboxed Python environment.\n\n"
    "WORKFLOW:\n"
    "1. Read the user's task and decide what concrete code or file inspection is needed.\n"
    "2. Use `read_file`, `list_dir`, or `search_in_file` to inspect inputs first.\n"
    "3. Use `run_python` to execute. Keep snippets focused — one task per call.\n"
    "4. Always inspect the actual output (stdout, files written) before claiming success.\n"
    "5. If your code errors, read the error, fix, and rerun. Do not guess.\n"
    "6. For non-trivial scripts, call `critique_response` on your final draft.\n\n"
    "WORKSPACE RULES:\n"
    "- Your workspace is `memory/workspace/`. Files written there persist between calls.\n"
    "- Never `rm -rf`, `del /q`, or operate outside the workspace.\n"
    "- Use stdlib first. If you import a package, verify it is installed before claiming success.\n"
    "- Imports needed beyond stdlib must be flagged to the user with a clear `pip install` line.\n\n"
    "OUTPUT RULES:\n"
    "- Always show the user the actual output you got — do not paraphrase tracebacks.\n"
    "- If the task generated a file, give the user the workspace path so they can find it.\n"
    "- Be honest about what worked and what did not."
)


CODEEXECUTOR_AGENT_TOOLS = (
    list(CODE_INTERPRETER_TOOLS)
    + list(FILE_READER_TOOLS)
    + list(CRITIQUE_TOOLS)
)


log_action(
    agent_name=CODEEXECUTOR_AGENT_NAME,
    action="module_loaded",
    output_summary=f"{len(CODEEXECUTOR_AGENT_TOOLS)} tools available",
)
