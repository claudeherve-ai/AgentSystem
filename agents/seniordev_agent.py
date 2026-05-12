"""Senior full-stack developer agent.

Specialises in premium web implementation, Laravel / Livewire,
advanced CSS, Three.js, and performance optimisation.
"""

import logging
import sys
from pathlib import Path
from typing import Annotated, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.audit import log_action
from tools.mcp_tools import (
    MCP_CONTEXT7_TOOLS,
    MCP_DOCS_TOOLS,
    MCP_FILESYSTEM_TOOLS,
    MCP_GIT_TOOLS,
    MCP_GITHUB_TOOLS,
    MCP_SEQUENTIAL_THINKING_TOOLS,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


async def review_code(
    code_snippet: Annotated[str, "Source code to review"],
    language: Annotated[str, "Programming language of the snippet"] = "python",
    focus: Annotated[str, "Review focus: quality, performance, security, or all"] = "quality",
) -> str:
    """Review code for quality, performance, and security.

    Returns structured feedback with severity ratings (🔴 critical,
    🟡 warning, 🟢 ok) covering style, correctness, security, and
    performance.
    """
    logger.info("Reviewing %s code (focus=%s)", language, focus)

    lines = code_snippet.strip().splitlines()
    line_count = len(lines)

    findings: list[str] = []

    # --- Style / quality checks ---
    if focus in ("quality", "all"):
        if line_count > 50:
            findings.append("🟡 [quality] Function exceeds 50 lines — consider extracting helpers.")
        if any(len(ln) > 120 for ln in lines):
            findings.append("🟡 [quality] Lines exceed 120 chars — hurts readability.")
        if not any("def " in ln or "function " in ln or "class " in ln for ln in lines):
            findings.append("🟢 [quality] No structural issues detected in this snippet.")
        else:
            has_docstring = any('"""' in ln or "'''" in ln or "/**" in ln for ln in lines)
            if not has_docstring:
                findings.append("🟡 [quality] Missing docstring / JSDoc — add documentation.")

    # --- Security checks ---
    if focus in ("security", "all"):
        dangerous_patterns = [
            ("eval(", "🔴 [security] Use of eval() — high risk of injection."),
            ("exec(", "🔴 [security] Use of exec() — high risk of injection."),
            ("innerHTML", "🟡 [security] innerHTML usage — risk of XSS. Prefer textContent or sanitise."),
            ("dangerouslySetInnerHTML", "🟡 [security] dangerouslySetInnerHTML — ensure input is sanitised."),
            ("SELECT * FROM", "🟡 [security] SELECT * — prefer explicit columns; check for SQL injection."),
            ("password", "🟡 [security] Possible credential handling — ensure hashing and no logging."),
        ]
        for pattern, msg in dangerous_patterns:
            if any(pattern.lower() in ln.lower() for ln in lines):
                findings.append(msg)
        if not any(p.lower() in code_snippet.lower() for p, _ in dangerous_patterns):
            findings.append("🟢 [security] No obvious security anti-patterns detected.")

    # --- Performance checks ---
    if focus in ("performance", "all"):
        perf_patterns = [
            ("nested for", "🟡 [performance] Nested loops detected — O(n²) risk."),
            ("import *", "🟡 [performance] Wildcard import — increases bundle / startup cost."),
            (".append(", "🟢 [performance] List append detected — consider list comprehension if in a loop."),
        ]
        for pattern, msg in perf_patterns:
            if any(pattern.lower() in ln.lower() for ln in lines):
                findings.append(msg)

    if not findings:
        findings.append("🟢 No issues found — code looks good.")

    result = (
        "═══════════════════════════════════════════\n"
        "  📝  CODE REVIEW REPORT\n"
        "═══════════════════════════════════════════\n"
        f"  Language : {language}\n"
        f"  Focus    : {focus}\n"
        f"  Lines    : {line_count}\n"
        "───────────────────────────────────────────\n"
        "  FINDINGS\n"
        "───────────────────────────────────────────\n"
    )
    for f in findings:
        result += f"  {f}\n"
    result += "═══════════════════════════════════════════"

    log_action(
        "SeniorDevAgent",
        "review_code",
        f"Language: {language}, Focus: {focus}, Lines: {line_count}",
        f"Findings: {len(findings)}",
    )
    return result


async def generate_implementation(
    feature_description: Annotated[str, "Description of the feature to implement"],
    tech_stack: Annotated[str, "Preferred technology stack (e.g. Laravel, React, Next.js)"] = "",
    constraints: Annotated[str, "Technical or business constraints to respect"] = "",
) -> str:
    """Generate an implementation plan with code patterns, file structure,
    and technology choices.

    Returns a detailed implementation blueprint suitable for a senior
    developer to execute.
    """
    logger.info("Generating implementation plan for: %s", feature_description[:80])

    stack_note = tech_stack if tech_stack else "To be determined based on requirements"
    constraint_note = constraints if constraints else "None specified"

    result = (
        "═══════════════════════════════════════════\n"
        "  🏗️  IMPLEMENTATION BLUEPRINT\n"
        "═══════════════════════════════════════════\n"
        f"  Feature     : {feature_description[:100]}\n"
        f"  Tech Stack  : {stack_note}\n"
        f"  Constraints : {constraint_note}\n"
        "───────────────────────────────────────────\n"
        "  1. ARCHITECTURE OVERVIEW\n"
        "───────────────────────────────────────────\n"
        f"  • Feature scope: {feature_description}\n"
        "  • Pattern: MVC / Component-based (select per stack)\n"
        "  • Data flow: Client → Controller/API → Service → Repository → DB\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  2. SUGGESTED FILE STRUCTURE\n"
        "───────────────────────────────────────────\n"
        "  src/\n"
        "  ├── controllers/       # Request handling\n"
        "  ├── services/          # Business logic\n"
        "  ├── models/            # Data models\n"
        "  ├── views|components/  # UI layer\n"
        "  ├── tests/             # Unit + integration\n"
        "  └── config/            # Environment & feature flags\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  3. IMPLEMENTATION STEPS\n"
        "───────────────────────────────────────────\n"
        "  Step 1: Define data model & migrations\n"
        "  Step 2: Implement service layer with validation\n"
        "  Step 3: Create API / controller endpoints\n"
        "  Step 4: Build UI components (responsive, accessible)\n"
        "  Step 5: Write tests (unit, integration, e2e)\n"
        "  Step 6: Performance audit & optimisation pass\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  4. KEY PATTERNS & BEST PRACTICES\n"
        "───────────────────────────────────────────\n"
        "  • Input validation at the boundary\n"
        "  • Repository pattern for data access\n"
        "  • Feature flags for progressive rollout\n"
        "  • Error boundaries / global error handler\n"
        "  • Logging & observability from day one\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "SeniorDevAgent",
        "generate_implementation",
        f"Feature: {feature_description[:100]}",
        f"Blueprint generated (stack={stack_note[:60]})",
    )
    return result


async def optimize_performance(
    component_description: Annotated[str, "Description of the component or system to optimise"],
    current_metrics: Annotated[str, "Current performance metrics (e.g. load time, FPS, TTFB)"] = "",
    target: Annotated[str, "Target performance goal"] = "",
) -> str:
    """Analyse performance bottlenecks and suggest optimisations.

    Returns an optimisation plan with expected improvements covering
    network, rendering, memory, and compute dimensions.
    """
    logger.info("Analysing performance for: %s", component_description[:80])

    metrics_note = current_metrics if current_metrics else "Not provided — baseline measurement recommended"
    target_note = target if target else "Achieve sub-second load / 60 FPS render target"

    result = (
        "═══════════════════════════════════════════\n"
        "  ⚡  PERFORMANCE OPTIMISATION PLAN\n"
        "═══════════════════════════════════════════\n"
        f"  Component : {component_description[:100]}\n"
        f"  Current   : {metrics_note}\n"
        f"  Target    : {target_note}\n"
        "───────────────────────────────────────────\n"
        "  NETWORK\n"
        "───────────────────────────────────────────\n"
        "  • Enable gzip / Brotli compression\n"
        "  • Implement HTTP/2 server push for critical assets\n"
        "  • Use CDN for static resources\n"
        "  • Lazy-load non-critical resources\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  RENDERING\n"
        "───────────────────────────────────────────\n"
        "  • Minimise layout thrashing (batch DOM reads/writes)\n"
        "  • Use CSS containment for complex components\n"
        "  • Virtualise long lists (react-window / virtual scroller)\n"
        "  • Defer off-screen rendering with IntersectionObserver\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  COMPUTE\n"
        "───────────────────────────────────────────\n"
        "  • Move heavy computation to Web Workers\n"
        "  • Debounce / throttle event handlers\n"
        "  • Memoise expensive calculations\n"
        "  • Use requestAnimationFrame for animations\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  MEMORY\n"
        "───────────────────────────────────────────\n"
        "  • Audit event listener cleanup\n"
        "  • Release references in unmount / destroy hooks\n"
        "  • Profile with DevTools Memory panel\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "SeniorDevAgent",
        "optimize_performance",
        f"Component: {component_description[:100]}",
        f"Plan generated (target={target_note[:60]})",
    )
    return result


async def design_css_system(
    project_description: Annotated[str, "Description of the project requiring a CSS system"],
    theme: Annotated[str, "Theme mode: light, dark, or light/dark"] = "light/dark",
    responsive: Annotated[bool, "Whether to include responsive breakpoints"] = True,
) -> str:
    """Create a CSS design system with custom properties, spacing scales,
    typography, and theme support.

    Returns complete CSS architecture including variables, utilities,
    breakpoints, and usage guidelines.
    """
    logger.info("Designing CSS system for: %s", project_description[:80])

    breakpoints_section = ""
    if responsive:
        breakpoints_section = (
            "\n"
            "  /* ── Breakpoints ── */\n"
            "  --bp-sm:  640px;\n"
            "  --bp-md:  768px;\n"
            "  --bp-lg:  1024px;\n"
            "  --bp-xl:  1280px;\n"
            "  --bp-2xl: 1536px;\n"
        )

    result = (
        "═══════════════════════════════════════════\n"
        "  🎨  CSS DESIGN SYSTEM\n"
        "═══════════════════════════════════════════\n"
        f"  Project    : {project_description[:100]}\n"
        f"  Theme      : {theme}\n"
        f"  Responsive : {responsive}\n"
        "───────────────────────────────────────────\n"
        "  :root {\n"
        "  /* ── Colour Palette ── */\n"
        "  --color-primary:    #2563eb;\n"
        "  --color-secondary:  #7c3aed;\n"
        "  --color-accent:     #06b6d4;\n"
        "  --color-success:    #16a34a;\n"
        "  --color-warning:    #eab308;\n"
        "  --color-error:      #dc2626;\n"
        "\n"
        "  /* ── Neutral Scale ── */\n"
        "  --gray-50:  #f9fafb;  --gray-900: #111827;\n"
        "\n"
        "  /* ── Typography ── */\n"
        '  --font-sans:  "Inter", system-ui, sans-serif;\n'
        '  --font-mono:  "JetBrains Mono", monospace;\n'
        "  --text-xs: 0.75rem;   --text-sm: 0.875rem;\n"
        "  --text-base: 1rem;    --text-lg: 1.125rem;\n"
        "  --text-xl: 1.25rem;   --text-2xl: 1.5rem;\n"
        "  --text-3xl: 1.875rem; --text-4xl: 2.25rem;\n"
        "\n"
        "  /* ── Spacing Scale (4px base) ── */\n"
        "  --space-1: 0.25rem;  --space-2: 0.5rem;\n"
        "  --space-3: 0.75rem;  --space-4: 1rem;\n"
        "  --space-6: 1.5rem;   --space-8: 2rem;\n"
        "  --space-12: 3rem;    --space-16: 4rem;\n"
        "\n"
        "  /* ── Border Radius ── */\n"
        "  --radius-sm: 0.25rem;  --radius-md: 0.5rem;\n"
        "  --radius-lg: 1rem;     --radius-full: 9999px;\n"
        "\n"
        "  /* ── Shadows ── */\n"
        "  --shadow-sm:  0 1px 2px rgba(0,0,0,0.05);\n"
        "  --shadow-md:  0 4px 6px rgba(0,0,0,0.1);\n"
        "  --shadow-lg:  0 10px 15px rgba(0,0,0,0.1);\n"
        f"{breakpoints_section}"
        "  }\n"
        "\n"
    )

    if "dark" in theme:
        result += (
            "  /* ── Dark Theme Override ── */\n"
            '  [data-theme="dark"] {\n'
            "    --color-primary:   #60a5fa;\n"
            "    --color-secondary: #a78bfa;\n"
            "    --gray-50:  #111827;  --gray-900: #f9fafb;\n"
            "  }\n"
            "\n"
        )

    if responsive:
        result += (
            "  /* ── Responsive Utilities ── */\n"
            "  @media (min-width: 768px)  { .md\\:hidden { display: none; } }\n"
            "  @media (min-width: 1024px) { .lg\\:hidden { display: none; } }\n"
            "\n"
        )

    result += "═══════════════════════════════════════════"

    log_action(
        "SeniorDevAgent",
        "design_css_system",
        f"Project: {project_description[:80]}, Theme: {theme}",
        f"CSS system generated (responsive={responsive})",
    )
    return result


async def debug_frontend_issue(
    error_description: Annotated[str, "Description of the frontend issue or error message"],
    browser: Annotated[str, "Browser where the issue occurs (e.g. Chrome, Firefox, Safari)"] = "",
    framework: Annotated[str, "Frontend framework in use (e.g. React, Vue, Svelte, Livewire)"] = "",
) -> str:
    """Diagnose frontend issues across browsers and frameworks.

    Returns root cause analysis with fix steps, browser compatibility
    notes, and preventive measures.
    """
    logger.info("Debugging frontend issue: %s", error_description[:80])

    browser_note = browser if browser else "All / unspecified"
    framework_note = framework if framework else "Vanilla JS / unspecified"

    # Build diagnostic checklist
    checks: list[str] = [
        "1. Open DevTools → Console: capture exact error message + stack trace.",
        "2. Network tab: check for failed requests (CORS, 404, 500).",
        "3. Elements tab: inspect DOM for missing / misplaced nodes.",
        "4. Performance tab: check for long tasks blocking the main thread.",
    ]

    if browser.lower() in ("safari", "ios"):
        checks.append("5. Safari-specific: check for missing CSS feature support (e.g. gap in flexbox).")
    if framework.lower() in ("react", "next", "next.js"):
        checks.append("5. React: verify hooks rules, key props on lists, and hydration mismatch.")
    if framework.lower() in ("vue", "nuxt"):
        checks.append("5. Vue: check reactive data, v-if/v-show toggle, and slot rendering.")
    if framework.lower() in ("livewire", "laravel"):
        checks.append("5. Livewire: check wire:model bindings, Alpine.js interop, and morphdom issues.")

    result = (
        "═══════════════════════════════════════════\n"
        "  🐛  FRONTEND DEBUG REPORT\n"
        "═══════════════════════════════════════════\n"
        f"  Issue     : {error_description[:120]}\n"
        f"  Browser   : {browser_note}\n"
        f"  Framework : {framework_note}\n"
        "───────────────────────────────────────────\n"
        "  ROOT CAUSE ANALYSIS\n"
        "───────────────────────────────────────────\n"
        f"  Hypothesis: Based on \"{error_description[:60]}…\"\n"
        "  Likely causes (ranked):\n"
        "    a) Runtime JS error — unhandled exception or type mismatch\n"
        "    b) CSS layout issue — overflow, z-index, or specificity conflict\n"
        "    c) Network / async error — failed fetch or race condition\n"
        "    d) Browser compatibility — missing API or CSS feature\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  DIAGNOSTIC STEPS\n"
        "───────────────────────────────────────────\n"
    )
    for c in checks:
        result += f"  {c}\n"

    result += (
        "\n"
        "───────────────────────────────────────────\n"
        "  RECOMMENDED FIX APPROACH\n"
        "───────────────────────────────────────────\n"
        "  1. Reproduce in isolation (minimal repro / Storybook).\n"
        "  2. Apply targeted fix (smallest change first).\n"
        "  3. Test across browsers: Chrome, Firefox, Safari, Edge.\n"
        "  4. Add regression test to prevent recurrence.\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "SeniorDevAgent",
        "debug_frontend_issue",
        f"Issue: {error_description[:100]}, Browser: {browser_note}",
        f"Debug report generated (framework={framework_note})",
    )
    return result


# ---------------------------------------------------------------------------
# Exported tool list
# ---------------------------------------------------------------------------

# List of tools to register with the senior developer agent
SENIORDEV_TOOLS = [
    review_code,
    generate_implementation,
    optimize_performance,
    design_css_system,
    debug_frontend_issue,
] + list(MCP_DOCS_TOOLS) + list(MCP_GITHUB_TOOLS) + list(MCP_CONTEXT7_TOOLS) + list(MCP_FILESYSTEM_TOOLS) + list(MCP_GIT_TOOLS) + list(MCP_SEQUENTIAL_THINKING_TOOLS)
