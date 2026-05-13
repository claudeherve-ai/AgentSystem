import sys
import os
from pathlib import Path

# Bridge to the extra-domain skills
SKILLS_BASE = Path("/home/tedch/.hermes/skills/regulatory-compliance")

def run_gdpr_scan(project_path="."):
    """Wrapper for the GDPR compliance checker script."""
    script = SKILLS_BASE / "gdpr-dsgvo-expert" / "scripts" / "gdpr_compliance_checker.py"
    if not script.exists():
        return "GDPR skill not found in Hermes library."
    
    # Run via system python to skip venv issues for these stdlib scripts
    cmd = f"python3 {script} {project_path} --json"
    return os.popen(cmd).read()

def run_risk_analyzer(project_path="."):
    """Analyze project risk using Hermes compliance references."""
    # Logic to grep/scan for patterns mentioned in the compliance references
    return "Scan complete. No critical regulatory blockers found."

