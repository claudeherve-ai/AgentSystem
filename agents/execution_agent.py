"""ExecutionAgent — Research, code, review, critique loop.
Merges: CodeExecutor + ProblemSolver + Research + Critic"""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agents.codeexecutor_agent import (CODEEXECUTOR_AGENT_TOOLS as ce_tools,CODEEXECUTOR_AGENT_NAME as ce_name,CODEEXECUTOR_AGENT_DESCRIPTION as ce_desc)
from agents.problemsolver_agent import (PROBLEMSOLVER_TOOLS as ps_tools)
from agents.research_agent import (RESEARCH_AGENT_TOOLS as rs_tools,RESEARCH_AGENT_NAME as rs_name,RESEARCH_AGENT_DESCRIPTION as rs_desc)
from agents.critic_agent import (CRITIC_AGENT_TOOLS as cr_tools,CRITIC_AGENT_NAME as cr_name,CRITIC_AGENT_DESCRIPTION as cr_desc)
EXECUTION_TOOLS = list(ce_tools)+list(ps_tools)+list(rs_tools)+list(cr_tools)
__all__=["EXECUTION_TOOLS"]
