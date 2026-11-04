# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os
import logging as standard_logging

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import google.auth
from fastapi import FastAPI, Request
from google.adk.cli.fast_api import get_fast_api_app
from google.cloud import logging as google_cloud_logging

from app.app_utils.telemetry import setup_telemetry
from app.app_utils.typing import Feedback

setup_telemetry()

# Configure standard fallback logger
std_logger = standard_logging.getLogger(__name__)
use_gcp_logging = False
logger = std_logger

try:
    if os.getenv("INTEGRATION_TEST") == "TRUE":
        raise google.auth.exceptions.DefaultCredentialsError("Using fallback logger for integration tests.")
    _, project_id = google.auth.default()
    logging_client = google_cloud_logging.Client()
    logger = logging_client.logger(__name__)
    use_gcp_logging = True
except Exception as e:
    std_logger.warning(f"GCP Cloud Logging client initialization failed or bypassed: {e}. Falling back to standard logger.")
allow_origins = (
    os.getenv("ALLOW_ORIGINS", "").split(",") if os.getenv("ALLOW_ORIGINS") else None
)

# Artifact bucket for ADK (created by Terraform, passed via env var)
logs_bucket_name = os.environ.get("LOGS_BUCKET_NAME")

# Create a dedicated agent isolation directory to prevent ADK from scanning non-agent folders like tests/ or artifacts/
_app_dir = os.path.dirname(os.path.abspath(__file__))
AGENT_DIR = _app_dir
# In-memory session configuration - no persistent storage
session_service_uri = None

artifact_service_uri = f"gs://{logs_bucket_name}" if logs_bucket_name else None

# Disable cloud trace exporter for local environments to prevent opentelemetry dependency crashes
is_integration_test = os.getenv("INTEGRATION_TEST") == "TRUE"
otel_to_cloud = False

app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=True,
    artifact_service_uri=artifact_service_uri,
    allow_origins=allow_origins,
    session_service_uri=session_service_uri,
    otel_to_cloud=otel_to_cloud,
)
app.title = "conveyor-orchestrator"
app.description = "API for interacting with the Agent conveyor-orchestrator"

from app.app_utils.reasoning_engine_adapter import attach_reasoning_engine_routes
attach_reasoning_engine_routes(app)


@app.post("/feedback")
def collect_feedback(feedback: Feedback) -> dict[str, str]:
    """Collect and log feedback.

    Args:
        feedback: The feedback data to log

    Returns:
        Success message
    """
    if use_gcp_logging:
        try:
            logger.log_struct(feedback.model_dump(), severity="INFO")
        except Exception as e:
            std_logger.warning(f"Failed to log struct to GCP Logging: {e}. Falling back to standard logging.")
            std_logger.info(f"Feedback: {feedback.model_dump()}")
    else:
        std_logger.info(f"Feedback: {feedback.model_dump()}")
    return {"status": "success"}


from fastapi.responses import HTMLResponse

@app.get("/dashboard", response_class=HTMLResponse)
def get_dashboard():
    """Serve the warehouse orchestration dashboard."""
    static_file_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(static_file_path):
        with open(static_file_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>StackBox Conveyor Orchestrator</h1><p>Dashboard static file not found.</p>"


@app.get("/playground", response_class=HTMLResponse)
def get_playground():
    """Serve the ADK Reference Observability Playground."""
    static_file_path = os.path.join(os.path.dirname(__file__), "static", "playground.html")
    if os.path.exists(static_file_path):
        with open(static_file_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>ADK Observability Playground</h1><p>Playground static file not found.</p>"


@app.get("/admin", response_class=HTMLResponse)
def get_admin():
    """Serve the Futuristic IT Admin Console."""
    static_file_path = os.path.join(os.path.dirname(__file__), "static", "admin.html")
    if os.path.exists(static_file_path):
        with open(static_file_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Futuristic IT Admin Console</h1><p>Admin static file not found.</p>"


@app.get("/api/agent_metadata")
def get_agent_metadata():
    """Return live structured metadata about the agents, tools, models, and architecture."""
    return {
        "agent_name": "cymbal-warehouse-automation-agent",
        "display_name": "Cymbal Warehouse Automation Agent",
        "root_workflow": "stackbox_conveyor_orchestrator",
        "model_id": "gemini-3.8-flash",
        "model_version": "gemini-3.8-flash-001",
        "runtime": "Vertex AI Agent Engine",
        "location": "global",
        "reasoning_engine_id": "8594036320127418368",
        "generation_config": {
            "temperature": 0.2,
            "top_p": 0.95,
            "budget": "dynamic"
        },
        "root_agent": {
            "name": "stackbox_conveyor_orchestrator",
            "type": "ROOT WORKFLOW / MULTI-AGENT ORCHESTRATOR",
            "model_id": "gemini-3.8-flash",
            "model_version": "gemini-3.8-flash-001",
            "budget": "dynamic",
            "subagents": ["dispatcher_agent", "sandbox_diagnostic_agent", "cctv_safety_audit_agent", "conversational_safety_agent"]
        },
        "agents": [
            {
                "id": "dispatcher_agent",
                "name": "dispatcher_agent",
                "type": "COMPLEX REASONING AGENT",
                "wraps": "dispatcher_agent",
                "description": "Autonomous warehouse AGV dispatcher and incident resolution specialist. Coordinates inventory checks, runbook procedures, and bot rerouting.",
                "model_id": "gemini-3.8-flash",
                "model_version": "gemini-3.8-flash-001",
                "tier": "FLASH",
                "budget": "high",
                "tools": ["check_wms_stock", "query_runbooks", "dispatch_agv", "discover_okf_catalog", "fetch_okf_document_section"]
            },
            {
                "id": "sandbox_diagnostic_agent",
                "name": "sandbox_diagnostic_agent",
                "type": "CODE DIAGNOSTIC AGENT",
                "wraps": "sandbox_diagnostic_agent",
                "description": "Telemetry and data diagnostics specialist. Generates and executes isolated Python code in a secure sandbox to calculate stress indices and isolate hotspots.",
                "model_id": "claude-opus-4-7",
                "model_version": "claude-opus-4-7",
                "tier": "OPUS",
                "budget": "high",
                "tools": ["write_file_to_sandbox", "execute_python_in_sandbox", "read_file_from_sandbox"]
            },
            {
                "id": "cctv_safety_audit_agent",
                "name": "cctv_safety_audit_agent",
                "type": "MULTIMODAL VISION AGENT",
                "wraps": "cctv_safety_audit_agent",
                "description": "Visual safety auditing specialist for warehouse CCTV feeds. Detects hazards, PPE violations, and conveyor obstruction events.",
                "model_id": "gemini-3.5-flash",
                "model_version": "gemini-3.5-flash-001",
                "tier": "FLASH",
                "budget": "medium",
                "tools": ["search_cctv_footages", "analyze_video_posture_and_hygiene", "discover_okf_catalog", "fetch_okf_document_section"]
            },
            {
                "id": "conversational_safety_agent",
                "name": "conversational_safety_agent",
                "type": "FAST CONVERSATIONAL AGENT",
                "wraps": "conversational_safety_agent",
                "description": "Interactive warehouse floor safety and policy specialist. Uses OKF progressive disclosure for HR policies, payroll, healthcare, and floor safety.",
                "model_id": "claude-sonnet-4-6",
                "model_version": "claude-sonnet-4-6",
                "tier": "SONNET",
                "budget": "low",
                "tools": ["discover_okf_catalog", "fetch_okf_document_section", "vertex_ai_rag_retrieval", "list_available_agvs", "get_agv_vitals"]
            }
        ],
        "tools": [
            {
                "id": "check_wms_stock",
                "name": "check_wms_stock",
                "type": "FUNCTION",
                "description": "Verify stock status and block condition for a specific SKU in the Warehouse Management System (WMS).",
                "parameters": {
                    "sku": {"type": "str", "description": "The SKU to query, e.g. SKU-991, SKU-502"}
                }
            },
            {
                "id": "query_runbooks",
                "name": "query_runbooks",
                "type": "FUNCTION",
                "description": "Query the maintenance Vector Search database for repair instructions matching an error code.",
                "parameters": {
                    "error_code": {"type": "str", "description": "The machine error code, e.g. 'Error 4042'"}
                }
            },
            {
                "id": "dispatch_agv",
                "name": "dispatch_agv",
                "type": "FUNCTION",
                "description": "Command an Autonomous Guided Vehicle (AGV) or picker bot to perform a bypass task in a specific aisle.",
                "parameters": {
                    "aisle": {"type": "str", "description": "Target aisle, e.g. 'Aisle 4'"},
                    "task": {"type": "str", "description": "Routing or bypass task instructions"},
                    "bot_id": {"type": "str", "description": "AGV identifier (default: 'PickerBot-Alpha')"}
                }
            },
            {
                "id": "execute_python_in_sandbox",
                "name": "execute_python_in_sandbox",
                "type": "FUNCTION",
                "description": "Execute a Python script in an isolated, monitored subprocess environment inside the sandbox.",
                "parameters": {
                    "script_name": {"type": "str", "description": "Name of the script to execute (e.g. 'diagnose_stress.py')"},
                    "timeout_seconds": {"type": "int", "description": "Maximum execution duration in seconds (default: 15)"}
                }
            },
            {
                "id": "write_file_to_sandbox",
                "name": "write_file_to_sandbox",
                "type": "FUNCTION",
                "description": "Write or create a file containing script code, text, or reports inside the secure agent sandbox.",
                "parameters": {
                    "filename": {"type": "str", "description": "File name to create"},
                    "content": {"type": "str", "description": "Text content or Python script code"}
                }
            },
            {
                "id": "read_file_from_sandbox",
                "name": "read_file_from_sandbox",
                "type": "FUNCTION",
                "description": "Read and retrieve the raw contents of a specific file located inside the secure agent sandbox.",
                "parameters": {
                    "filename": {"type": "str", "description": "Name of the file to retrieve from sandbox"}
                }
            },
            {
                "id": "discover_okf_catalog",
                "name": "discover_okf_catalog",
                "type": "FUNCTION",
                "description": "Level 1 Discovery: Search the Open Knowledge Format (OKF) catalog index to find relevant policy documents and available sections.",
                "parameters": {
                    "query": {"type": "str", "description": "Keywords or question regarding HR policies, payroll, healthcare, inventory, or floor safety"},
                    "domain": {"type": "str", "description": "Optional domain filter ('HR', 'PAYROLL', 'HEALTHCARE', 'GOVERNANCE', 'INVENTORY', 'SAFETY')"}
                }
            },
            {
                "id": "fetch_okf_document_section",
                "name": "fetch_okf_document_section",
                "type": "FUNCTION",
                "description": "Level 2/3 Progressive Disclosure: Retrieve a targeted section or full policy document from the OKF knowledge repository.",
                "parameters": {
                    "doc_id": {"type": "str", "description": "Unique document identifier discovered in catalog, e.g. DOC-HR-LEAVE-001, DOC-PAY-COMP-002, DOC-OPS-INV-005"},
                    "section": {"type": "str", "description": "Specific section title to retrieve to avoid context bloat"}
                }
            },
            {
                "id": "get_operator_profile",
                "name": "get_operator_profile",
                "type": "FUNCTION",
                "description": "Retrieve the operator's structured memory profile from GEAP Memory Bank (certifications, shift role, assigned zone, alert verbosity).",
                "parameters": {
                    "operator_id": {"type": "str", "description": "Operator badge ID, e.g. 'TECH-402', 'ENG-091'"}
                }
            }
        ],
        "workflow_nodes": [
            "telemetry_ingest",
            "runbook_lookup",
            "wms_access",
            "log_recoverable",
            "conversational_safety_agent",
            "cctv_safety_audit_agent",
            "sandbox_diagnostic_agent",
            "join",
            "format_dispatcher_input",
            "dispatcher_agent"
        ]
    }


# ==============================================================================
# GEAP Memory Bank Endpoints
# ==============================================================================
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from app.app_utils import memory_bank_service


class IngestEventsRequest(BaseModel):
    stream_id: str = "operator_session_TECH-402"
    events: List[Dict[str, Any]] = []
    force_flush: bool = False
    event_count_threshold: int = 5
    idle_duration_seconds: int = 300


class GenerateMemoriesRequest(BaseModel):
    scope: Dict[str, str] = {"user_id": "TECH-402", "warehouse_id": "stackbox_austin_1"}
    events: Optional[List[Dict[str, Any]]] = None
    allowed_topics: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    metadata_merge_strategy: str = "MERGE"


class RollbackMemoryRequest(BaseModel):
    memory_name: str = memory_bank_service.TARGET_MEMORY_NAME
    target_revision_id: str = "881173220072357888"


class TriggerDreamRequest(BaseModel):
    memory_name: str = memory_bank_service.TARGET_MEMORY_NAME
    scope: Optional[Dict[str, str]] = {"user_id": "TECH-402", "warehouse_id": "stackbox_austin_1", "zone": "Zone B"}
    model_tier: str = "gemini-3.5-flash-lite"
    force_run: bool = False


class FleetDreamRequest(BaseModel):
    model_tier: str = "gemini-3.5-flash-lite"


@app.get("/api/memory_bank/profiles")
def get_memory_bank_profile(user_id: str = "TECH-402"):
    """Retrieve structured operator profile from Memory Bank."""
    return memory_bank_service.retrieve_operator_profile(user_id=user_id)


@app.post("/api/memory_bank/ingest_events")
def post_memory_bank_ingest_events(req: IngestEventsRequest):
    """Ingest streaming events into Memory Bank buffer with generation triggers."""
    return memory_bank_service.ingest_events(
        stream_id=req.stream_id,
        events=req.events,
        force_flush=req.force_flush,
        event_count_threshold=req.event_count_threshold,
        idle_duration_seconds=req.idle_duration_seconds,
    )


@app.post("/api/memory_bank/generate_memories")
def post_memory_bank_generate_memories(req: GenerateMemoriesRequest):
    """Trigger dynamic memory extraction and consolidation into Memory Bank."""
    return memory_bank_service.generate_memories(
        scope=req.scope,
        events=req.events,
        allowed_topics=req.allowed_topics,
        metadata=req.metadata,
        metadata_merge_strategy=req.metadata_merge_strategy,
    )


@app.get("/api/memory_bank/revisions")
def get_memory_bank_revisions(
    memory_name: str = memory_bank_service.TARGET_MEMORY_NAME,
    filter_expr: Optional[str] = None
):
    """List historical immutable revisions and lineage for a memory resource."""
    return memory_bank_service.list_memory_revisions(
        memory_name=memory_name,
        filter_expr=filter_expr
    )


@app.post("/api/memory_bank/rollback")
def post_memory_bank_rollback(req: RollbackMemoryRequest):
    """Rollback a memory resource to a specified revision ID."""
    return memory_bank_service.rollback_memory(
        memory_name=req.memory_name,
        target_revision_id=req.target_revision_id
    )


@app.post("/api/memory_bank/dream")
def post_memory_bank_dream(req: TriggerDreamRequest):
    """Trigger an offline memory dreaming and background reflection cycle."""
    return memory_bank_service.trigger_dream_cycle(
        memory_name=req.memory_name,
        scope=req.scope,
        model_tier=req.model_tier,
        force_run=req.force_run
    )


@app.get("/api/memory_bank/dream/status")
def get_memory_bank_dream_status(memory_name: str = memory_bank_service.TARGET_MEMORY_NAME):
    """Retrieve current dreaming cycle status, epiphanies, and reflection telemetry."""
    return memory_bank_service.get_dreaming_status(memory_name=memory_name)


@app.post("/api/admin/memory_banks/dream_fleet")
def post_admin_dream_fleet(req: FleetDreamRequest):
    """Dispatch fleet-wide dreaming cycle across all operator memory banks."""
    return admin_service.trigger_fleet_dreaming(model_tier=req.model_tier)


# ==============================================================================
# IT Admin & Governance Endpoints
# ==============================================================================
from app.app_utils import admin_service, skill_registry_service


class ResolveIncidentRequest(BaseModel):
    incident_id: str
    action: str = "RESOLVE"  # "RESOLVE" or "QUARANTINE"


class ToggleQuarantineRequest(BaseModel):
    session_id: str


@app.get("/api/admin/overview")
def get_api_admin_overview():
    """Return top-level telemetry KPIs and DEFCON threat status."""
    return admin_service.get_admin_overview()


class RecordUsageRequest(BaseModel):
    model_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    ttft_ms: Optional[int] = None


@app.get("/api/admin/costs")
def get_api_admin_costs():
    """Return cost and token breakdown by model tier and department."""
    return admin_service.get_cost_and_token_breakdown()


@app.post("/api/admin/record_usage")
def post_api_admin_record_usage(req: RecordUsageRequest):
    """Dynamically record model usage, tokens, and TTFT across the Model Fleet."""
    return admin_service.record_model_usage(
        model_id=req.model_id,
        input_tokens=req.input_tokens,
        output_tokens=req.output_tokens,
        cached_tokens=req.cached_tokens,
        ttft_ms=req.ttft_ms
    )


@app.get("/api/admin/latency")
def get_api_admin_latency():
    """Return latency percentiles and tool benchmark timings."""
    return admin_service.get_latency_stats()


@app.get("/api/admin/sessions")
def get_api_admin_sessions():
    """Return all active and historical multi-user sessions."""
    return admin_service.get_user_sessions()


@app.get("/api/admin/memory_banks")
def get_api_admin_memory_banks():
    """Return GEAP Memory Bank fleet status."""
    return admin_service.get_memory_bank_fleet()


@app.get("/api/admin/security")
def get_api_admin_security():
    """Return SAIF & SGP security and safety audit events."""
    return admin_service.get_security_audit_log()


@app.post("/api/admin/security/resolve")
def post_api_admin_security_resolve(req: ResolveIncidentRequest):
    """Acknowledge, resolve, or quarantine a security incident."""
    return admin_service.resolve_security_incident(
        incident_id=req.incident_id, action=req.action
    )


@app.post("/api/admin/sessions/toggle_quarantine")
def post_api_admin_toggle_quarantine(req: ToggleQuarantineRequest):
    """Toggle quarantine status for a session."""
    return admin_service.toggle_session_quarantine(session_id=req.session_id)


@app.get("/api/admin/evaluations")
def get_api_admin_evaluations():
    """Return real-time agent hillclimbing evaluation scorecard, rubrics, and trace results."""
    return admin_service.get_evaluations_summary()


@app.post("/api/admin/evaluations/run")
def post_api_admin_evaluations_run():
    """Trigger an on-demand evaluation grading pass."""
    return admin_service.run_evaluations_job()


@app.get("/api/admin/hillclimbing_mods")
def get_api_admin_hillclimbing_mods():
    """Return prompt and architecture modifications log based on hillclimbing exercises."""
    return admin_service.get_hillclimbing_modifications()


class SimulateAlertRequest(BaseModel):
    metric_name: Optional[str] = "Safety & LOTO Compliance"
    observed_value: Optional[float] = 0.54
    threshold_value: Optional[float] = 0.70
    summary: Optional[str] = "Online Monitor metric dropped below SLA threshold."
    policy_name: Optional[str] = "Cymbal Online Monitor Metric Degradation"


class DismissAlertRequest(BaseModel):
    alert_id: str


@app.post("/api/admin/evaluations/webhook")
async def post_api_admin_evaluations_webhook(request: Request):
    """Webhook endpoint for Google Cloud Monitoring Alert Policies.
    
    Receives incident notifications when online evaluation metrics breach SLA thresholds.
    """
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    return admin_service.process_evaluation_alert(payload)


@app.post("/api/admin/evaluations/alerts/simulate")
def post_api_admin_evaluations_alerts_simulate(req: SimulateAlertRequest):
    """Simulate a Google Cloud Monitoring alert trigger for testing."""
    return admin_service.process_evaluation_alert(req.model_dump())


@app.post("/api/admin/evaluations/alerts/dismiss")
def post_api_admin_evaluations_alerts_dismiss(req: DismissAlertRequest):
    """Dismiss an active evaluation alert."""
    return admin_service.dismiss_evaluation_alert(req.alert_id)


# ==============================================================================
# GEAP Agent Skills Registry & OKF Knowledge Catalog Endpoints
# ==============================================================================
@app.get("/api/skills")
def get_api_skills():
    """Return the complete 3-tier hierarchical skills catalog enriched with GEAP registry status."""
    return skill_registry_service.get_hierarchical_skills_catalog()


@app.post("/api/skills/sync_registry")
def post_api_skills_sync_registry():
    """Package and synchronize all 3-level skills to the GEAP / Vertex AI Skill Registry."""
    return skill_registry_service.sync_all_skills_to_geap()


@app.post("/api/skills/{skill_id}/sync")
def post_api_skill_sync(skill_id: str):
    """Package and upload a specific skill to the GEAP Skill Registry."""
    return skill_registry_service.upload_skill_to_geap(skill_id)


@app.get("/api/skills/{skill_id}")
def get_api_skill_details(skill_id: str):
    """Return detailed metadata, disciplines, micro-skills, and SOP markdown for a skill."""
    return skill_registry_service.get_skill_details(skill_id)



# Main execution
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8555)
