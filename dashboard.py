"""Internal Streamlit operator console for the durable AgentSystem API."""

from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st


st.set_page_config(
    page_title="AgentSystem Operator Console",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com/claudeherve-ai/AgentSystem",
        "Report a bug": "https://github.com/claudeherve-ai/AgentSystem/issues",
        "About": "Internal control surface for AgentSystem operations.",
    },
)

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Manrope:wght@400;500;600;700&display=swap');
:root {
  --ink: #e8edf2; --muted: #8b98a8; --line: #26313d;
  --panel: rgba(17, 24, 32, .92); --cyan: #43d7c8; --amber: #e8b45a;
}
.stApp {
  color: var(--ink); font-family: "Manrope", sans-serif;
  background:
    radial-gradient(circle at 88% 0%, rgba(67, 215, 200, .08), transparent 28rem),
    linear-gradient(135deg, #0b1016, #101821 58%, #0b1118);
}
.block-container { max-width: 1380px; padding-top: 2rem; }
h1, h2, h3 { font-family: "Manrope", sans-serif !important; letter-spacing: -.025em; }
code, [data-testid="stMetricValue"] { font-family: "IBM Plex Mono", monospace !important; }
[data-testid="stSidebar"] { background: #0c1219; border-right: 1px solid var(--line); }
[data-testid="stMetric"], [data-testid="stExpander"], [data-testid="stDataFrame"] {
  background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
}
[data-testid="stMetric"] { padding: 1rem; }
.operator-kicker {
  color: var(--cyan); font: 600 .72rem "IBM Plex Mono", monospace;
  letter-spacing: .18em; text-transform: uppercase;
}
.operator-hero {
  border: 1px solid var(--line); border-left: 3px solid var(--cyan);
  border-radius: 10px; padding: 1.2rem 1.4rem; margin-bottom: 1.2rem;
  background: linear-gradient(110deg, rgba(67,215,200,.07), rgba(17,24,32,.7));
}
.operator-hero p { color: var(--muted); margin-bottom: 0; }
.stButton > button { border-radius: 7px; font-weight: 600; }
@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
</style>
""",
    unsafe_allow_html=True,
)


class ApiFailure(RuntimeError):
    """Safe API error suitable for display to an operator."""


def _api_base_url() -> str:
    return os.getenv("AGENTSYSTEM_API_URL", "http://localhost:8080").rstrip("/")


def _headers() -> dict[str, str]:
    api_key = os.getenv("AGENTSYSTEM_API_KEY", "").strip()
    if api_key:
        return {"X-API-Key": api_key}

    try:
        incoming = st.context.headers
    except (AttributeError, RuntimeError):
        return {}

    id_token = incoming.get("X-MS-TOKEN-AAD-ID-TOKEN")
    return {"Authorization": f"Bearer {id_token}"} if id_token else {}


def _request(
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    authenticated: bool = True,
) -> Any:
    try:
        response = requests.request(
            method,
            f"{_api_base_url()}{path}",
            headers=_headers() if authenticated else {},
            json=body,
            timeout=(3.05, 20),
        )
    except requests.RequestException as exc:
        raise ApiFailure("The AgentSystem API is unreachable.") from exc

    try:
        payload = response.json()
    except ValueError:
        payload = None

    if not response.ok:
        message = "The API request failed."
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                message = str(error.get("message") or message)
        raise ApiFailure(f"{message} (HTTP {response.status_code})")
    return payload


def _health() -> dict[str, Any] | None:
    try:
        result = _request("GET", "/health/ready", authenticated=False)
        return result if isinstance(result, dict) else None
    except ApiFailure:
        return None


def _format_rows(items: list[dict[str, Any]], fields: tuple[str, ...]) -> list[dict[str, Any]]:
    return [{field: item.get(field) for field in fields} for item in items]


with st.sidebar:
    st.markdown("### AgentSystem")
    st.caption("Internal operator console")
    page = st.radio(
        "Surface",
        ("Operations", "Runs", "Approvals", "Dispatch"),
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("API endpoint")
    st.code(_api_base_url(), language=None)
    if _headers():
        st.success("Authenticated operator identity available")
    else:
        st.warning("No authenticated operator identity is available")

st.markdown(
    """
<div class="operator-hero">
  <div class="operator-kicker">Internal control plane</div>
  <h1>Operator Console</h1>
  <p>Durable state, dependency truth, and authenticated actions from the production API.</p>
</div>
""",
    unsafe_allow_html=True,
)

health = _health()
if health is None:
    st.error("API readiness is unavailable. No operational status can be inferred.")
elif not health.get("ready"):
    st.warning(f"API is not ready: {health.get('status', 'degraded')}")

if page == "Operations":
    if health is None:
        st.info("Start the API or correct AGENTSYSTEM_API_URL to view dependency health.")
    else:
        dependencies = health.get("dependencies") or {}
        healthy = sum(1 for value in dependencies.values() if value.get("healthy"))
        required_failures = sum(
            1
            for value in dependencies.values()
            if value.get("required") and not value.get("healthy")
        )
        first, second, third = st.columns(3)
        first.metric("Readiness", "READY" if health.get("ready") else "NOT READY")
        second.metric("Healthy dependencies", f"{healthy}/{len(dependencies)}")
        third.metric("Required failures", required_failures)
        rows = [
            {
                "dependency": name,
                "status": "healthy" if value.get("healthy") else "unhealthy",
                "required": bool(value.get("required")),
                "detail": value.get("detail", ""),
            }
            for name, value in dependencies.items()
        ]
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.info("The API returned no dependency details.")

elif page == "Runs":
    try:
        payload = _request("GET", "/api/v1/runs?limit=100")
        runs = payload.get("runs", []) if isinstance(payload, dict) else []
        if not runs:
            st.info("No durable runs are available for this identity.")
        else:
            st.dataframe(
                _format_rows(
                    runs,
                    ("id", "status", "input", "selected_agent", "created_at", "updated_at"),
                ),
                use_container_width=True,
                hide_index=True,
            )
            run_id = st.selectbox("Inspect run", [run["id"] for run in runs])
            detail = _request("GET", f"/api/v1/runs/{run_id}")
            st.json(detail, expanded=False)
            if detail.get("status") not in {"completed", "failed", "cancelled"}:
                if st.button("Request cancellation", type="secondary"):
                    _request("POST", f"/api/v1/runs/{run_id}/cancel")
                    st.success("Cancellation requested. The worker must acknowledge it.")
                    st.rerun()
    except ApiFailure as exc:
        st.error(str(exc))

elif page == "Approvals":
    try:
        payload = _request("GET", "/api/v1/approvals?status=pending")
        approvals = payload.get("approvals", []) if isinstance(payload, dict) else []
        if not approvals:
            st.info("No pending approvals are available for this workspace.")
        for approval in approvals:
            with st.container(border=True):
                st.markdown(f"**{approval.get('action', 'Approval required')}**")
                st.caption(
                    f"{approval.get('agent_name', 'agent')} · {approval.get('id', '')}"
                )
                st.json(approval.get("details") or {}, expanded=False)
                feedback = st.text_area(
                    "Decision note",
                    key=f"feedback-{approval['id']}",
                    max_chars=4000,
                )
                approve_col, reject_col = st.columns(2)
                if approve_col.button(
                    "Approve", key=f"approve-{approval['id']}", type="primary"
                ):
                    _request(
                        "POST",
                        f"/api/v1/approvals/{approval['id']}/approve",
                        body={"feedback": feedback},
                    )
                    st.rerun()
                if reject_col.button("Reject", key=f"reject-{approval['id']}"):
                    _request(
                        "POST",
                        f"/api/v1/approvals/{approval['id']}/reject",
                        body={"feedback": feedback},
                    )
                    st.rerun()
    except ApiFailure as exc:
        st.error(str(exc))

else:
    with st.form("dispatch-run", clear_on_submit=True):
        message = st.text_area(
            "Desired outcome",
            placeholder="Describe the result, constraints, and acceptance criteria.",
            min_chars=1,
            max_chars=20_000,
            height=180,
        )
        agent = st.text_input(
            "Agent override",
            placeholder="Leave empty for automatic routing",
        )
        submitted = st.form_submit_button("Dispatch durable run", type="primary")
    if submitted:
        body: dict[str, Any] = {"message": message.strip()}
        if agent.strip():
            body["preferred_agent"] = agent.strip()
        try:
            run = _request("POST", "/api/v1/runs", body=body)
            st.success(f"Run {run.get('id')} accepted with status {run.get('status')}.")
        except ApiFailure as exc:
            st.error(str(exc))
