"""
EngineeringAgent — Full-stack engineering powerhouse.
Merges: SoftwareArchitect + SeniorDev + BackendArch + FrontendDev + UXArch + OptimizationArchitect
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.audit import log_action
from tools.mcp_tools import MCP_CONTEXT7_TOOLS, MCP_FILESYSTEM_TOOLS, MCP_SEQUENTIAL_THINKING_TOOLS

logger = logging.getLogger(__name__)

# ── Import all tools from merged agents ─────────────────────────────────────
from agents.softwarearchitect_agent import (
    design_system_architecture as sa_design_system,
    create_adr,
    analyze_tradeoffs,
    design_domain_model,
    evaluate_tech_stack,
)
from agents.seniordev_agent import (
    review_code,
    generate_implementation,
    optimize_performance,
    design_css_system,
    debug_frontend_issue,
)
from agents.backendarchitect_agent import (
    design_system_architecture as be_design_system,
    design_database_schema,
    design_api,
)
from agents.frontenddev_agent import (
    design_component_architecture,
    audit_performance,
    generate_accessibility_report,
)
from agents.uxarchitect_agent import (
    create_design_system,
    design_layout,
    create_component_spec,
    audit_accessibility,
    create_developer_handoff,
)
from agents.optimizationarchitect_agent import (
    design_optimization_strategy,
    create_circuit_breaker,
    analyze_api_costs,
    design_shadow_test,
    create_finops_dashboard,
)

ENGINEERING_TOOLS = [
    # Architecture
    sa_design_system,
    create_adr,
    analyze_tradeoffs,
    design_domain_model,
    evaluate_tech_stack,
    be_design_system,
    # Implementation
    review_code,
    generate_implementation,
    optimize_performance,
    design_css_system,
    debug_frontend_issue,
    # Backend
    design_database_schema,
    design_api,
    # Frontend
    design_component_architecture,
    audit_performance,
    generate_accessibility_report,
    # UX
    create_design_system,
    design_layout,
    create_component_spec,
    audit_accessibility,
    create_developer_handoff,
    # Optimization
    design_optimization_strategy,
    create_circuit_breaker,
    analyze_api_costs,
    design_shadow_test,
    create_finops_dashboard,
    # MCP tools
] + list(MCP_CONTEXT7_TOOLS) + list(MCP_FILESYSTEM_TOOLS) + list(MCP_SEQUENTIAL_THINKING_TOOLS)

__all__ = ["ENGINEERING_TOOLS"]
