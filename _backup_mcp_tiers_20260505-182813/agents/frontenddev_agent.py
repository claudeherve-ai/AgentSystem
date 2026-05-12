"""
AgentSystem — Frontend Developer Agent.

Modern web application specialist for React, TypeScript, responsive design,
accessibility, and performance optimization.
"""

import logging
import sys
from pathlib import Path
from typing import Annotated

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.audit import log_action

logger = logging.getLogger(__name__)


async def design_component_architecture(
    project_name: Annotated[str, "Project or feature name"],
    framework: Annotated[str, "Framework: react, vue, angular, or svelte"],
    requirements: Annotated[str, "UI requirements and feature description"],
    state_management: Annotated[str, "State: redux, zustand, context, pinia, or none"] = "context",
) -> str:
    """Design a frontend component architecture with hierarchy, state flow, and data patterns."""
    log_action("FrontendDevAgent", "component_architecture", f"project={project_name}, fw={framework}")

    return (
        f"COMPONENT ARCHITECTURE: {project_name}\n{'=' * 60}\n\n"
        f"Framework:        {framework}\n"
        f"State Management: {state_management}\n\n"
        f"REQUIREMENTS\n{'─' * 60}\n  {requirements[:400]}\n\n"
        f"COMPONENT TREE\n{'─' * 60}\n"
        f"  App\n"
        f"   +-- Layout\n"
        f"   |    +-- Header (nav, user menu)\n"
        f"   |    +-- Sidebar (navigation)\n"
        f"   |    +-- Main (outlet / router)\n"
        f"   |    +-- Footer\n"
        f"   +-- Pages\n"
        f"   |    +-- [Feature pages]\n"
        f"   +-- Shared\n"
        f"        +-- [Reusable components]\n\n"
        f"DATA FLOW\n{'─' * 60}\n"
        f"  API -> Service Layer -> {state_management} Store -> Components\n"
        f"  User Actions -> Handlers -> API Calls -> Store Updates\n\n"
        f"STANDARDS\n"
        f"  - TypeScript strict mode\n"
        f"  - WCAG 2.1 AA accessibility\n"
        f"  - Mobile-first responsive design\n"
        f"  - Core Web Vitals targets: LCP<2.5s, FID<100ms, CLS<0.1\n"
    )


async def audit_performance(
    page_url_or_description: Annotated[str, "Page URL or description of the page to audit"],
    current_metrics: Annotated[str, "Current performance metrics if available"] = "",
) -> str:
    """Audit frontend performance and provide optimization recommendations."""
    log_action("FrontendDevAgent", "perf_audit", f"page={page_url_or_description[:60]}")

    return (
        f"PERFORMANCE AUDIT\n{'=' * 60}\n\n"
        f"Target: {page_url_or_description}\n"
        f"Current Metrics: {current_metrics or 'Not provided'}\n\n"
        f"CORE WEB VITALS TARGETS\n{'─' * 60}\n"
        f"  LCP (Largest Contentful Paint): < 2.5s\n"
        f"  FID (First Input Delay):        < 100ms\n"
        f"  CLS (Cumulative Layout Shift):  < 0.1\n"
        f"  TTFB (Time to First Byte):      < 800ms\n\n"
        f"OPTIMIZATION CHECKLIST\n{'─' * 60}\n"
        f"  [ ] Code splitting with dynamic imports\n"
        f"  [ ] Image optimization (WebP/AVIF, responsive srcset)\n"
        f"  [ ] Tree shaking unused code\n"
        f"  [ ] Lazy loading below-fold content\n"
        f"  [ ] Font subsetting and font-display: swap\n"
        f"  [ ] Critical CSS inlining\n"
        f"  [ ] Service worker caching strategy\n"
        f"  [ ] Bundle analyzer review\n\n"
        f"RECOMMENDED TOOLS\n"
        f"  - Lighthouse CI for automated audits\n"
        f"  - webpack-bundle-analyzer for bundle review\n"
        f"  - Real User Monitoring (RUM) for production data\n"
    )


async def generate_accessibility_report(
    component_or_page: Annotated[str, "Component name or page description to audit"],
    wcag_level: Annotated[str, "WCAG level: A, AA, or AAA"] = "AA",
) -> str:
    """Generate a WCAG accessibility audit report with specific remediation steps."""
    log_action("FrontendDevAgent", "a11y_audit", f"target={component_or_page[:60]}, level={wcag_level}")

    return (
        f"ACCESSIBILITY AUDIT (WCAG 2.1 {wcag_level})\n{'=' * 60}\n\n"
        f"Target: {component_or_page}\n\n"
        f"CHECKLIST\n{'─' * 60}\n"
        f"  [ ] Semantic HTML structure (headings, landmarks, lists)\n"
        f"  [ ] ARIA labels on interactive elements\n"
        f"  [ ] Keyboard navigation (Tab, Enter, Escape, Arrow keys)\n"
        f"  [ ] Focus management and visible focus indicators\n"
        f"  [ ] Color contrast ratios (4.5:1 text, 3:1 large text)\n"
        f"  [ ] Alt text on images, aria-label on icons\n"
        f"  [ ] Form labels and error messages linked to inputs\n"
        f"  [ ] Skip navigation link\n"
        f"  [ ] Reduced motion support (prefers-reduced-motion)\n"
        f"  [ ] Screen reader testing (VoiceOver, NVDA)\n\n"
        f"AUTOMATED TESTING\n{'─' * 60}\n"
        f"  - axe-core / @axe-core/react for component testing\n"
        f"  - Lighthouse accessibility score target: 95+\n"
        f"  - jest-axe for unit test assertions\n"
    )


FRONTENDDEV_TOOLS = [design_component_architecture, audit_performance, generate_accessibility_report]
