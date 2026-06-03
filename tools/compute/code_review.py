"""
Static code-review engine.

Performs *real* analysis rather than substring matching:
  * Python-like code is parsed with the stdlib ``ast`` module; a SyntaxError
    is itself reported as a critical finding.
  * AST visitors flag genuinely risky constructs (eval/exec, shell=True,
    bare excepts, mutable default args, hardcoded secrets, ``== None`` …).
  * If ``ruff`` and/or ``bandit`` are installed they are invoked in a
    guarded subprocess (``shutil.which`` check, temp file, timeout, output
    cap, full try/except) and their findings merged in. Absence never fails.
  * Non-Python languages fall back to language-aware regex heuristics with a
    clear "static analysis limited" note.

Everything degrades gracefully: no external binary, no Docker, and no
network are required for the core analysis to return useful findings.
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field

_SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


@dataclass
class Finding:
    line: int
    severity: str  # critical | warning | info
    rule: str
    message: str


@dataclass
class ReviewResult:
    language: str
    focus: str
    findings: list[Finding] = field(default_factory=list)
    tools_run: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    syntax_ok: bool = True
    line_count: int = 0

    def counts(self) -> dict[str, int]:
        out = {"critical": 0, "warning": 0, "info": 0}
        for f in self.findings:
            out[f.severity] = out.get(f.severity, 0) + 1
        return out

    def render(self) -> str:
        c = self.counts()
        verdict = (
            "needs work" if c["critical"]
            else "minor issues" if c["warning"]
            else "looks solid"
        )
        parts = [
            f"# Code Review — {self.language}",
            f"\n**Focus:** `{self.focus}`  |  **Verdict:** {verdict}",
            f"\n**Findings:** {c['critical']} critical · {c['warning']} warning · {c['info']} info",
        ]
        if self.tools_run:
            parts.append(f"\n_Analyzers:_ {', '.join(self.tools_run)}")
        if not self.findings:
            parts.append("\nNo issues detected by the available analyzers. "
                         "(Absence of findings is not proof of correctness — "
                         "add tests for behavioral guarantees.)")
        else:
            parts.append("\n## Findings\n")
            ordered = sorted(
                self.findings,
                key=lambda f: (_SEVERITY_ORDER.get(f.severity, 9), f.line),
            )
            parts.append("| Line | Severity | Rule | Issue |")
            parts.append("| --- | --- | --- | --- |")
            for f in ordered:
                msg = f.message.replace("|", "\\|")
                parts.append(f"| {f.line} | {f.severity} | `{f.rule}` | {msg} |")
        if self.notes:
            parts.append("\n## Notes\n")
            parts.extend(f"- {n}" for n in self.notes)
        return "\n".join(parts) + "\n"


_PY_LANGS = {"python", "py", "python3"}


class _PyVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.findings: list[Finding] = []

    def _add(self, node: ast.AST, severity: str, rule: str, message: str) -> None:
        line = getattr(node, "lineno", 0) or 0
        self.findings.append(Finding(line, severity, rule, message))

    def visit_Call(self, node: ast.Call) -> None:
        fname = ""
        if isinstance(node.func, ast.Name):
            fname = node.func.id
        elif isinstance(node.func, ast.Attribute):
            fname = node.func.attr
        if fname in ("eval", "exec", "compile"):
            self._add(node, "critical", "dangerous-call",
                      f"Use of `{fname}()` can execute arbitrary code.")
        # subprocess(..., shell=True)
        for kw in node.keywords:
            if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                self._add(node, "critical", "shell-injection",
                          "`shell=True` enables shell injection; pass an args list instead.")
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            self._add(node, "warning", "bare-except",
                      "Bare `except:` swallows all errors including KeyboardInterrupt.")
        elif isinstance(node.type, ast.Name) and node.type.id == "Exception" and not node.body:
            pass
        self.generic_visit(node)

    def _check_defaults(self, node) -> None:
        for default in node.args.defaults + node.args.kw_defaults:
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                self._add(default, "warning", "mutable-default",
                          "Mutable default argument is shared across calls; use None sentinel.")

    def _check_func(self, node) -> None:
        self._check_defaults(node)
        # missing docstring
        if not ast.get_docstring(node):
            self._add(node, "info", "missing-docstring",
                      f"Function `{node.name}` has no docstring.")
        # long function
        end = getattr(node, "end_lineno", None)
        if end and (end - node.lineno) > 50:
            self._add(node, "warning", "long-function",
                      f"Function `{node.name}` is {end - node.lineno} lines; consider splitting.")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_func(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_func(node)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name == "*":
                self._add(node, "warning", "wildcard-import",
                          f"`from {node.module} import *` pollutes the namespace.")
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        for op, comparator in zip(node.ops, node.comparators):
            if isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(comparator, ast.Constant) and comparator.value is None:
                self._add(node, "warning", "none-compare",
                          "Compare to None with `is`/`is not`, not `==`/`!=`.")
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        # hardcoded secret heuristic
        secret_names = ("password", "passwd", "secret", "api_key", "apikey",
                        "token", "private_key", "access_key")
        for target in node.targets:
            name = getattr(target, "id", "") or getattr(target, "attr", "")
            if name and name.lower() in secret_names and isinstance(node.value, ast.Constant) \
                    and isinstance(node.value.value, str) and len(node.value.value) >= 6:
                self._add(node, "critical", "hardcoded-secret",
                          f"`{name}` appears to be a hardcoded secret; load from env/secret store.")
        self.generic_visit(node)


def _scan_python(code: str) -> ReviewResult:
    res = ReviewResult(language="python", focus="")
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        res.syntax_ok = False
        res.findings.append(
            Finding(exc.lineno or 0, "critical", "syntax-error",
                    f"SyntaxError: {exc.msg}")
        )
        return res
    visitor = _PyVisitor()
    visitor.visit(tree)
    res.findings.extend(visitor.findings)
    # source-level scans (comments aren't in the AST)
    for i, line in enumerate(code.splitlines(), start=1):
        if re.search(r"#\s*(TODO|FIXME|XXX)\b", line):
            res.findings.append(Finding(i, "info", "todo-marker",
                                        "Unresolved TODO/FIXME marker."))
        # nested loop perf hint (very rough): two 'for' on same logical line
        if re.search(r"\bfor\b.*\bfor\b", line):
            res.findings.append(Finding(i, "warning", "nested-loop",
                                        "Nested loop on one line — watch O(n²) cost."))
    res.tools_run.append("ast")
    return res


def _run_external(tool: str, args: list[str], code: str, suffix: str) -> str | None:
    """Run an analyzer on a temp file. Returns stdout or None on any failure."""
    if shutil.which(tool) is None:
        return None
    path = None
    try:
        fd, path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(code)
        proc = subprocess.run(
            [tool, *args, path],
            capture_output=True, text=True, timeout=8,
        )
        return (proc.stdout or "")[:20000]
    except Exception:
        return None
    finally:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass


def _merge_ruff(code: str, res: ReviewResult) -> None:
    out = _run_external("ruff", ["check", "--output-format", "json", "--quiet"], code, ".py")
    if not out:
        return
    try:
        items = json.loads(out)
    except (ValueError, TypeError):
        return
    res.tools_run.append("ruff")
    for it in items[:50]:
        loc = it.get("location") or {}
        res.findings.append(Finding(
            int(loc.get("row", 0) or 0), "warning",
            f"ruff:{it.get('code', '?')}", str(it.get("message", "")).strip(),
        ))


def _merge_bandit(code: str, res: ReviewResult) -> None:
    out = _run_external("bandit", ["-f", "json", "-q"], code, ".py")
    if not out:
        return
    try:
        data = json.loads(out)
    except (ValueError, TypeError):
        return
    res.tools_run.append("bandit")
    sev_map = {"HIGH": "critical", "MEDIUM": "warning", "LOW": "info"}
    for r in data.get("results", [])[:50]:
        res.findings.append(Finding(
            int(r.get("line_number", 0) or 0),
            sev_map.get(str(r.get("issue_severity", "")).upper(), "warning"),
            f"bandit:{r.get('test_id', '?')}", str(r.get("issue_text", "")).strip(),
        ))


# Non-python heuristics: language -> list of (regex, severity, rule, message)
_HEURISTICS: dict[str, list[tuple[str, str, str, str]]] = {
    "javascript": [
        (r"\beval\s*\(", "critical", "dangerous-call", "Use of eval() executes arbitrary code."),
        (r"\bdocument\.write\s*\(", "warning", "dom-write", "document.write can enable XSS."),
        (r"\binnerHTML\s*=", "warning", "inner-html", "Assigning innerHTML risks XSS; use textContent."),
        (r"\bvar\b", "info", "var-usage", "Prefer let/const over var."),
        (r"==[^=]", "info", "loose-eq", "Use === for strict equality."),
        (r"(password|secret|api_?key|token)\s*[:=]\s*['\"][^'\"]{6,}", "critical",
         "hardcoded-secret", "Possible hardcoded secret."),
    ],
    "typescript": [
        (r"\beval\s*\(", "critical", "dangerous-call", "Use of eval() executes arbitrary code."),
        (r":\s*any\b", "info", "any-type", "Avoid `any`; use a precise type."),
        (r"\binnerHTML\s*=", "warning", "inner-html", "Assigning innerHTML risks XSS."),
        (r"(password|secret|api_?key|token)\s*[:=]\s*['\"][^'\"]{6,}", "critical",
         "hardcoded-secret", "Possible hardcoded secret."),
    ],
    "sql": [
        (r"(?i)\bselect\s+\*", "warning", "select-star", "Avoid SELECT *; name columns explicitly."),
        (r"(?i)\bdelete\b(?!.*\bwhere\b)", "critical", "unbounded-delete", "DELETE without WHERE affects all rows."),
        (r"(?i)\bupdate\b(?!.*\bwhere\b)", "critical", "unbounded-update", "UPDATE without WHERE affects all rows."),
        (r"(?i)\bdrop\s+table\b", "warning", "drop-table", "DROP TABLE is destructive and irreversible."),
    ],
    "go": [
        (r"_\s*=\s*err", "warning", "ignored-error", "Error explicitly ignored."),
        (r"(password|secret|api_?key|token)\s*[:=]\s*\"[^\"]{6,}", "critical",
         "hardcoded-secret", "Possible hardcoded secret."),
    ],
    "java": [
        (r"(?i)printStackTrace\s*\(", "warning", "print-stacktrace", "Use a logger, not printStackTrace()."),
        (r"(password|secret|api_?key|token)\s*=\s*\"[^\"]{6,}", "critical",
         "hardcoded-secret", "Possible hardcoded secret."),
    ],
}


def _scan_heuristic(code: str, language: str) -> ReviewResult:
    res = ReviewResult(language=language, focus="")
    rules = _HEURISTICS.get(language, [])
    lines = code.splitlines()
    for i, line in enumerate(lines, start=1):
        for pattern, severity, rule, message in rules:
            if re.search(pattern, line):
                res.findings.append(Finding(i, severity, rule, message))
        if re.search(r"(?i)(TODO|FIXME|XXX)", line):
            res.findings.append(Finding(i, "info", "todo-marker", "Unresolved TODO/FIXME marker."))
    res.tools_run.append("regex-heuristics")
    res.notes.append(
        f"Deep static analysis is limited for `{language}`; findings are "
        f"pattern-based. Run a dedicated linter for full coverage."
    )
    return res


def _normalize_lang(language: str) -> str:
    lang = (language or "python").strip().lower()
    aliases = {"py": "python", "python3": "python", "js": "javascript",
               "ts": "typescript", "golang": "go"}
    return aliases.get(lang, lang)


def review_source(code: str, language: str = "python", focus: str = "quality") -> ReviewResult:
    """Analyze ``code`` and return real findings."""
    lang = _normalize_lang(language)
    code = code or ""
    if not code.strip():
        res = ReviewResult(language=lang, focus=focus)
        res.notes.append("No code supplied to review.")
        return res

    if lang in _PY_LANGS:
        res = _scan_python(code)
        if res.syntax_ok:  # only run linters on parseable code
            _merge_ruff(code, res)
            _merge_bandit(code, res)
    else:
        res = _scan_heuristic(code, lang)

    res.focus = focus
    res.line_count = len(code.splitlines())
    # focus filtering: keep security findings always; filter others loosely.
    if focus and focus.lower() == "security":
        security_rules = ("secret", "injection", "dangerous", "xss", "eval",
                          "shell", "delete", "update", "html")
        res.findings = [
            f for f in res.findings
            if f.severity == "critical" or any(s in f.rule.lower() for s in security_rules)
        ]
    return res
