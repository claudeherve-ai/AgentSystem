"""UX architect agent.

Specialises in technical architecture foundations for user experience:
CSS systems, responsive design, accessibility (WCAG 2.1 AA), and
developer handoff documentation.
"""

import logging
import sys
from pathlib import Path
from typing import Annotated, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.audit import log_action

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


async def create_design_system(
    project_name: Annotated[str, "Name of the project or product"],
    brand_colors: Annotated[str, "Brand colour hex codes (comma-separated, e.g. #1a73e8,#34a853)"] = "",
    typography: Annotated[str, "Font families to use (e.g. Inter, Roboto Mono)"] = "",
    spacing: Annotated[str, "Base spacing unit in px (e.g. 4, 8)"] = "",
) -> str:
    """Create a complete CSS design system.

    Returns CSS custom properties, theme toggle support, responsive
    breakpoints, and usage guidelines.
    """
    logger.info("Creating design system for: %s", project_name)

    # Parse inputs with sensible defaults
    colors = [c.strip() for c in brand_colors.split(",") if c.strip()] if brand_colors else ["#2563eb", "#7c3aed", "#06b6d4"]
    fonts = typography if typography else "Inter, system-ui, sans-serif"
    base_space = int(spacing) if spacing.isdigit() else 4

    # Generate spacing scale
    scale = {f"--space-{i}": f"{base_space * i}px" for i in (1, 2, 3, 4, 6, 8, 12, 16)}

    result = (
        "═══════════════════════════════════════════\n"
        "  🎨  DESIGN SYSTEM\n"
        "═══════════════════════════════════════════\n"
        f"  Project  : {project_name}\n"
        f"  Colours  : {', '.join(colors)}\n"
        f"  Fonts    : {fonts}\n"
        f"  Base Unit: {base_space}px\n"
        "───────────────────────────────────────────\n"
        "  CSS CUSTOM PROPERTIES\n"
        "───────────────────────────────────────────\n"
        "  :root {\n"
        "    /* ── Colour Tokens ── */\n"
    )
    color_names = ["primary", "secondary", "accent", "success", "warning", "error"]
    for i, color in enumerate(colors):
        name = color_names[i] if i < len(color_names) else f"brand-{i+1}"
        result += f"    --color-{name}: {color};\n"

    result += (
        "\n"
        "    /* ── Typography ── */\n"
        f'    --font-sans: "{fonts}";\n'
        '    --font-mono: "JetBrains Mono", monospace;\n'
        "    --text-xs: 0.75rem;   --leading-xs: 1rem;\n"
        "    --text-sm: 0.875rem;  --leading-sm: 1.25rem;\n"
        "    --text-base: 1rem;    --leading-base: 1.5rem;\n"
        "    --text-lg: 1.125rem;  --leading-lg: 1.75rem;\n"
        "    --text-xl: 1.25rem;   --leading-xl: 1.75rem;\n"
        "    --text-2xl: 1.5rem;   --leading-2xl: 2rem;\n"
        "\n"
        "    /* ── Spacing Scale ── */\n"
    )
    for token, value in scale.items():
        result += f"    {token}: {value};\n"

    result += (
        "\n"
        "    /* ── Breakpoints ── */\n"
        "    --bp-sm: 640px;\n"
        "    --bp-md: 768px;\n"
        "    --bp-lg: 1024px;\n"
        "    --bp-xl: 1280px;\n"
        "\n"
        "    /* ── Elevation ── */\n"
        "    --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);\n"
        "    --shadow-md: 0 4px 6px rgba(0,0,0,0.07);\n"
        "    --shadow-lg: 0 10px 15px rgba(0,0,0,0.1);\n"
        "\n"
        "    /* ── Radii ── */\n"
        "    --radius-sm: 0.25rem;\n"
        "    --radius-md: 0.5rem;\n"
        "    --radius-lg: 1rem;\n"
        "    --radius-full: 9999px;\n"
        "  }\n"
        "\n"
        "  /* ── Dark Theme ── */\n"
        '  [data-theme="dark"] {\n'
        "    --color-bg: #0f172a;\n"
        "    --color-surface: #1e293b;\n"
        "    --color-text: #f1f5f9;\n"
        "  }\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  THEME TOGGLE (JS)\n"
        "───────────────────────────────────────────\n"
        "  document.documentElement.dataset.theme =\n"
        '    localStorage.getItem("theme") || "light";\n'
        "\n"
        "───────────────────────────────────────────\n"
        "  USAGE GUIDELINES\n"
        "───────────────────────────────────────────\n"
        "  • Always use tokens — never hard-code values\n"
        "  • Spacing: multiples of base unit only\n"
        "  • Colour: semantic names (--color-primary) not raw hex\n"
        "  • Typography: use --text-* and --leading-* together\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "UXArchitectAgent",
        "create_design_system",
        f"Project: {project_name}, Colours: {len(colors)}",
        "Design system generated",
    )
    return result


async def design_layout(
    page_type: Annotated[str, "Type of page (e.g. dashboard, landing, settings, article)"],
    content_sections: Annotated[str, "Comma-separated list of content sections for the page"] = "",
    responsive: Annotated[bool, "Whether to include responsive breakpoint behaviour"] = True,
) -> str:
    """Design a page layout using CSS Grid / Flexbox.

    Returns a layout specification with responsive behaviour, semantic
    HTML structure, and CSS implementation notes.
    """
    logger.info("Designing layout for: %s", page_type)

    sections = [s.strip() for s in content_sections.split(",") if s.strip()] if content_sections else ["header", "main", "sidebar", "footer"]

    result = (
        "═══════════════════════════════════════════\n"
        "  📐  LAYOUT SPECIFICATION\n"
        "═══════════════════════════════════════════\n"
        f"  Page Type  : {page_type}\n"
        f"  Sections   : {', '.join(sections)}\n"
        f"  Responsive : {responsive}\n"
        "───────────────────────────────────────────\n"
        "  LAYOUT DIAGRAM\n"
        "───────────────────────────────────────────\n"
        "\n"
        "  Desktop (≥1024px)\n"
        "  ┌────────────────────────────────────┐\n"
        "  │            HEADER / NAV            │\n"
        "  ├──────────────────────┬─────────────┤\n"
        "  │                     │             │\n"
        "  │       MAIN          │   SIDEBAR   │\n"
        "  │     CONTENT         │             │\n"
        "  │                     │             │\n"
        "  ├──────────────────────┴─────────────┤\n"
        "  │             FOOTER                 │\n"
        "  └────────────────────────────────────┘\n"
        "\n"
    )

    if responsive:
        result += (
            "  Mobile (<768px)\n"
            "  ┌──────────────────┐\n"
            "  │     HEADER       │\n"
            "  ├──────────────────┤\n"
            "  │     MAIN         │\n"
            "  │     CONTENT      │\n"
            "  ├──────────────────┤\n"
            "  │     SIDEBAR      │\n"
            "  ├──────────────────┤\n"
            "  │     FOOTER       │\n"
            "  └──────────────────┘\n"
            "\n"
        )

    result += (
        "───────────────────────────────────────────\n"
        "  HTML STRUCTURE\n"
        "───────────────────────────────────────────\n"
        '  <div class="layout">\n'
    )
    for section in sections:
        tag = "header" if section == "header" else ("footer" if section == "footer" else ("aside" if section == "sidebar" else "main"))
        result += f'    <{tag} class="layout__{section}">{section}</{tag}>\n'
    result += (
        "  </div>\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  CSS IMPLEMENTATION\n"
        "───────────────────────────────────────────\n"
        "  .layout {\n"
        '    display: grid;\n'
        '    grid-template-columns: 1fr 300px;\n'
        '    grid-template-rows: auto 1fr auto;\n'
        "    min-height: 100dvh;\n"
        "    gap: var(--space-4);\n"
        "  }\n"
        "\n"
    )

    if responsive:
        result += (
            "  @media (max-width: 768px) {\n"
            "    .layout {\n"
            "      grid-template-columns: 1fr;\n"
            "    }\n"
            "  }\n"
        )

    result += "═══════════════════════════════════════════"

    log_action(
        "UXArchitectAgent",
        "design_layout",
        f"Page: {page_type}, Sections: {len(sections)}, Responsive: {responsive}",
        "Layout specification generated",
    )
    return result


async def create_component_spec(
    component_name: Annotated[str, "Name of the UI component (e.g. Button, Modal, Card)"],
    variants: Annotated[str, "Comma-separated visual variants (e.g. primary, secondary, ghost)"] = "",
    states: Annotated[str, "Comma-separated interactive states (e.g. hover, focus, disabled, loading)"] = "",
    accessibility: Annotated[str, "Specific accessibility requirements or ARIA roles"] = "",
) -> str:
    """Create a component specification with HTML structure, CSS, and
    accessibility requirements.

    Returns an implementation-ready spec including variants, states,
    ARIA attributes, and keyboard interactions.
    """
    logger.info("Creating component spec: %s", component_name)

    variant_list = [v.strip() for v in variants.split(",") if v.strip()] if variants else ["default", "primary", "secondary"]
    state_list = [s.strip() for s in states.split(",") if s.strip()] if states else ["hover", "focus", "active", "disabled"]
    a11y_note = accessibility if accessibility else "Follow WAI-ARIA 1.2 guidelines for this component type"

    result = (
        "═══════════════════════════════════════════\n"
        "  🧱  COMPONENT SPECIFICATION\n"
        "═══════════════════════════════════════════\n"
        f"  Component     : {component_name}\n"
        f"  Variants      : {', '.join(variant_list)}\n"
        f"  States        : {', '.join(state_list)}\n"
        f"  Accessibility : {a11y_note}\n"
        "───────────────────────────────────────────\n"
        "  HTML STRUCTURE\n"
        "───────────────────────────────────────────\n"
    )

    tag = "button" if "button" in component_name.lower() else "div"
    result += (
        f'  <{tag}\n'
        f'    class="{component_name.lower()}"\n'
        f'    role="{component_name.lower()}"\n'
    )
    if tag == "button":
        result += '    type="button"\n'
    result += (
        f'    aria-label="{{label}}"\n'
        f'  >\n'
        f'    <!-- content -->\n'
        f'  </{tag}>\n'
        "\n"
        "───────────────────────────────────────────\n"
        "  VARIANTS\n"
        "───────────────────────────────────────────\n"
    )
    for v in variant_list:
        result += f'  .{component_name.lower()}--{v} {{\n'
        if v == "primary":
            result += "    background: var(--color-primary);\n    color: white;\n"
        elif v == "secondary":
            result += "    background: var(--color-secondary);\n    color: white;\n"
        elif v == "ghost":
            result += "    background: transparent;\n    border: 1px solid var(--color-primary);\n"
        else:
            result += "    background: var(--color-surface);\n    color: var(--color-text);\n"
        result += "  }\n\n"

    result += (
        "───────────────────────────────────────────\n"
        "  STATES\n"
        "───────────────────────────────────────────\n"
    )
    for s in state_list:
        if s == "hover":
            result += f"  .{component_name.lower()}:hover {{ opacity: 0.9; cursor: pointer; }}\n"
        elif s == "focus":
            result += f"  .{component_name.lower()}:focus-visible {{ outline: 2px solid var(--color-primary); outline-offset: 2px; }}\n"
        elif s == "disabled":
            result += f"  .{component_name.lower()}:disabled {{ opacity: 0.5; cursor: not-allowed; pointer-events: none; }}\n"
        elif s == "active":
            result += f"  .{component_name.lower()}:active {{ transform: scale(0.98); }}\n"
        elif s == "loading":
            result += f"  .{component_name.lower()}--loading {{ position: relative; pointer-events: none; }}\n"
        else:
            result += f"  .{component_name.lower()}:{s} {{ /* define {s} styles */ }}\n"

    result += (
        "\n"
        "───────────────────────────────────────────\n"
        "  ACCESSIBILITY\n"
        "───────────────────────────────────────────\n"
        f"  • {a11y_note}\n"
        "  • Keyboard: Enter/Space to activate, Tab to focus\n"
        "  • Screen reader: announce variant and state changes\n"
        "  • Minimum touch target: 44×44px\n"
        "  • Colour contrast: ≥4.5:1 (AA) for text, ≥3:1 for large text\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "UXArchitectAgent",
        "create_component_spec",
        f"Component: {component_name}, Variants: {len(variant_list)}",
        f"Spec generated (states: {len(state_list)})",
    )
    return result


async def audit_accessibility(
    page_description: Annotated[str, "Description of the page or component to audit"],
    current_issues: Annotated[str, "Known existing accessibility issues"] = "",
) -> str:
    """Perform a WCAG 2.1 AA accessibility audit.

    Returns a compliance report organised by WCAG principle (Perceivable,
    Operable, Understandable, Robust) with remediation steps.
    """
    logger.info("Auditing accessibility for: %s", page_description[:80])

    issues_note = current_issues if current_issues else "No known issues reported"

    result = (
        "═══════════════════════════════════════════\n"
        "  ♿  ACCESSIBILITY AUDIT (WCAG 2.1 AA)\n"
        "═══════════════════════════════════════════\n"
        f"  Page/Component : {page_description[:100]}\n"
        f"  Known Issues   : {issues_note}\n"
        "───────────────────────────────────────────\n"
        "  1. PERCEIVABLE\n"
        "───────────────────────────────────────────\n"
        "  ☐ 1.1.1 Non-text content has text alternatives (alt, aria-label)\n"
        "  ☐ 1.3.1 Semantic HTML used (headings, landmarks, lists)\n"
        "  ☐ 1.4.1 Colour is not the sole means of conveying info\n"
        "  ☐ 1.4.3 Contrast ratio ≥4.5:1 (text) / ≥3:1 (large text)\n"
        "  ☐ 1.4.4 Text resizable to 200% without loss of content\n"
        "  ☐ 1.4.10 Content reflows at 320px width (no horizontal scroll)\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  2. OPERABLE\n"
        "───────────────────────────────────────────\n"
        "  ☐ 2.1.1 All functionality available via keyboard\n"
        "  ☐ 2.1.2 No keyboard trap\n"
        "  ☐ 2.4.3 Logical focus order follows visual layout\n"
        "  ☐ 2.4.6 Descriptive headings and labels\n"
        "  ☐ 2.4.7 Focus indicator visible (outline or equivalent)\n"
        "  ☐ 2.5.5 Touch target ≥44×44px\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  3. UNDERSTANDABLE\n"
        "───────────────────────────────────────────\n"
        "  ☐ 3.1.1 Page language declared (<html lang=\"en\">)\n"
        "  ☐ 3.2.1 No unexpected context change on focus\n"
        "  ☐ 3.3.1 Input errors clearly identified\n"
        "  ☐ 3.3.2 Labels or instructions for inputs\n"
        "  ☐ 3.3.3 Error suggestions provided\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  4. ROBUST\n"
        "───────────────────────────────────────────\n"
        "  ☐ 4.1.1 Valid HTML — no duplicate IDs\n"
        "  ☐ 4.1.2 Custom components have ARIA name, role, value\n"
        "  ☐ 4.1.3 Status messages use aria-live regions\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  TESTING TOOLS\n"
        "───────────────────────────────────────────\n"
        "  • axe DevTools (browser extension)\n"
        "  • Lighthouse → Accessibility audit\n"
        "  • NVDA / VoiceOver screen reader testing\n"
        "  • Keyboard-only navigation test\n"
        "  • Colour contrast checker (WebAIM)\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  REMEDIATION PRIORITY\n"
        "───────────────────────────────────────────\n"
        "  🔴 Critical: missing alt text, no keyboard access, <3:1 contrast\n"
        "  🟡 Important: focus order, ARIA roles, touch targets\n"
        "  🟢 Enhancement: reduced-motion media query, skip links\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "UXArchitectAgent",
        "audit_accessibility",
        f"Page: {page_description[:80]}",
        "WCAG 2.1 AA audit report generated",
    )
    return result


async def create_developer_handoff(
    design_description: Annotated[str, "Description of the design to hand off"],
    tech_stack: Annotated[str, "Target tech stack for implementation (e.g. React, Vue, Svelte)"] = "",
    breakpoints: Annotated[str, "Responsive breakpoints (e.g. 640,768,1024,1280)"] = "",
) -> str:
    """Create developer handoff documentation with exact specs.

    Returns an implementation guide with measurements, tokens,
    component mapping, and responsive behaviour.
    """
    logger.info("Creating developer handoff for: %s", design_description[:80])

    stack_note = tech_stack if tech_stack else "Framework-agnostic"
    bp_list = [b.strip() for b in breakpoints.split(",") if b.strip()] if breakpoints else ["640", "768", "1024", "1280"]

    result = (
        "═══════════════════════════════════════════\n"
        "  📦  DEVELOPER HANDOFF\n"
        "═══════════════════════════════════════════\n"
        f"  Design    : {design_description[:100]}\n"
        f"  Tech Stack: {stack_note}\n"
        f"  Breakpoints: {', '.join(bp_list)}px\n"
        "───────────────────────────────────────────\n"
        "  TOKEN REFERENCE\n"
        "───────────────────────────────────────────\n"
        "  Colours   → var(--color-primary), var(--color-secondary)\n"
        "  Spacing   → var(--space-{1..16})\n"
        "  Typography→ var(--text-{xs..2xl})\n"
        "  Radius    → var(--radius-{sm,md,lg,full})\n"
        "  Shadow    → var(--shadow-{sm,md,lg})\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  COMPONENT MAPPING\n"
        "───────────────────────────────────────────\n"
        "  Design Element        → Component / CSS Class\n"
        "  ─────────────────────────────────────────\n"
        "  Primary Button        → .btn.btn--primary\n"
        "  Card Container        → .card\n"
        "  Input Field           → .input\n"
        "  Navigation Bar        → .navbar\n"
        "  Modal / Dialog        → .modal (+ aria-modal)\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  RESPONSIVE BEHAVIOUR\n"
        "───────────────────────────────────────────\n"
    )
    for bp in bp_list:
        result += f"  @media (min-width: {bp}px) — adjust layout/visibility\n"

    result += (
        "\n"
        "───────────────────────────────────────────\n"
        "  INTERACTION NOTES\n"
        "───────────────────────────────────────────\n"
        "  • Transitions: 150ms ease-out (use prefers-reduced-motion)\n"
        "  • Hover states: opacity 0.9, subtle transform\n"
        "  • Focus rings: 2px solid primary, 2px offset\n"
        "  • Loading states: skeleton screens, not spinners\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  IMPLEMENTATION CHECKLIST\n"
        "───────────────────────────────────────────\n"
        "  ☐ Use design tokens (no magic numbers)\n"
        "  ☐ Semantic HTML elements\n"
        "  ☐ Keyboard navigation works\n"
        "  ☐ Screen reader announces correctly\n"
        "  ☐ Tested at all breakpoints\n"
        "  ☐ Dark mode verified\n"
        "  ☐ Performance: CLS < 0.1, LCP < 2.5s\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "UXArchitectAgent",
        "create_developer_handoff",
        f"Design: {design_description[:80]}, Stack: {stack_note}",
        f"Handoff doc generated (breakpoints: {len(bp_list)})",
    )
    return result


# ---------------------------------------------------------------------------
# Exported tool list
# ---------------------------------------------------------------------------

# List of tools to register with the UX architect agent
UXARCHITECT_TOOLS = [
    create_design_system,
    design_layout,
    create_component_spec,
    audit_accessibility,
    create_developer_handoff,
]
