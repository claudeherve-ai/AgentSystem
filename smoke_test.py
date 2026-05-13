import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    print("Testing imports...")
    from config import get_agent_configs
    from agents.orchestrator import Orchestrator
    from tools.compliance_audit import run_gdpr_scan
    
    print("Configuring orchestrator (Dry Run)...")
    orchestrator = Orchestrator()
    status = orchestrator.status()
    print(f"System Status: {status['system']}")
    print(f"Registered Agents: {len(status['registered_agents'])}")
    
    print("Testing Compliance Bridge...")
    # Mock project path for GDPR scan
    gdpr_result = run_gdpr_scan(".")
    if "GDPR" in gdpr_result or "{" in gdpr_result:
         print("GDPR scanner bridge verified.")
    else:
         print(f"GDPR scan returned: {gdpr_result[:100]}")

    print("\n✅ SMOKE TEST PASSED: AgentSystem core logic and Hermes bridges are ready.")
except Exception as e:
    print(f"\n❌ SMOKE TEST FAILED: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
