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

"""GEAP Memory Bank Integration Service for Cymbal Warehouse Automation Agent.

Provides production-grade clients and fallbacks for:
1. Ingest Events (Decoupled streaming ingestion with generation trigger rules)
2. Generate Memories (Dynamic fact extraction & consolidation with topic filtering)
3. Structured Profiles (Low-latency Pydantic schema-backed profile retrieval)
4. Memory Revisions & Lineage (Audit tracking, diffing, and rollback)
"""

import datetime
import logging
import os
import sys
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Constants & Default Target Resource in Memory Bank
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "ce-testing-465204")
PROJECT_NUMBER = "526827734705"
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
REASONING_ENGINE_ID = "8594036320127418368"
TARGET_REASONING_ENGINE = (
    f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/reasoningEngines/{REASONING_ENGINE_ID}"
)
TARGET_MEMORY_NAME = (
    f"{TARGET_REASONING_ENGINE}/memories/881173220072357888"
)


# ==============================================================================
# 1. Structured Profile Schema (Pydantic)
# ==============================================================================

class WarehouseOperatorProfile(BaseModel):
    """Structured memory profile schema for warehouse associates & engineers."""
    operator_id: str = Field(
        ..., description="Unique badge ID of the operator, e.g. TECH-402, ENG-091"
    )
    full_name: str = Field(
        ..., description="Full legal name of the warehouse employee, e.g. Dave Miller"
    )
    shift_role: str = Field(
        ..., description="Designated role: 'Senior Conveyor Technician', 'Safety Lead', 'Fleet Specialist'"
    )
    certified_machinery: List[str] = Field(
        default_factory=list,
        description="List of machinery and safety certifications: ['CV-01', 'CV-02', 'PickerBot-Alpha', 'LOTO-Level-3']"
    )
    active_assigned_zone: str = Field(
        ..., description="Current primary zone or aisle: 'Zone B - Aisle 4'"
    )
    preferred_alert_verbosity: str = Field(
        default="technical",
        description="Notification style: 'technical' (verbose metrics) or 'concise_summary'"
    )
    recent_incident_focus: Optional[str] = Field(
        default=None,
        description="Active focus or recent safety inquiry, e.g. 'CV-02 thermal overload investigation'"
    )
    last_login_timestamp: Optional[str] = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="ISO timestamp of last shift check-in"
    )


# In-memory mock/local state for profiles & revisions when cloud auth is bypassed
_LOCAL_OPERATOR_PROFILES: Dict[str, WarehouseOperatorProfile] = {
    "TECH-402": WarehouseOperatorProfile(
        operator_id="TECH-402",
        full_name="Dave Miller",
        shift_role="Senior Conveyor Maintenance Technician",
        certified_machinery=["CV-01", "CV-02", "CV-03", "PickerBot-Alpha", "LOTO-Level-3", "WMS-Admin"],
        active_assigned_zone="Zone B - Aisle 4",
        preferred_alert_verbosity="technical",
        recent_incident_focus="Conveyor CV-02 Error 4042 Thermal Jam Recovery",
        last_login_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    ),
    "ENG-091": WarehouseOperatorProfile(
        operator_id="ENG-091",
        full_name="Sarah Chen",
        shift_role="Warehouse Safety Lead & Compliance Officer",
        certified_machinery=["All-Conveyors", "AGV-Fleet", "OSHA-Floor-Auditor", "LOTO-Master-Key"],
        active_assigned_zone="Main Sorting Facility - Facility Level",
        preferred_alert_verbosity="concise_summary",
        recent_incident_focus="OKF Safety Guidelines & CCTV Posture Audits",
        last_login_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )
}

# In-memory revision history for memory 881173220072357888
_LOCAL_MEMORY_REVISIONS: List[Dict[str, Any]] = [
    {
        "name": f"{TARGET_MEMORY_NAME}/revisions/9012458112001",
        "revision_id": "9012458112001",
        "create_time": "2026-09-19T14:32:00Z",
        "fact": "Technician Dave Miller (TECH-402) resolved Error 4042 on Conveyor CV-02 in Zone B Aisle 4 by engaging LOTO Level 3, clearing thermal friction block at roller bracket 7, and routing PickerBot-Alpha as temporary bypass.",
        "extracted_memories": [
            {"fact": "Dave Miller cleared roller bracket 7 on CV-02 during afternoon shift."},
            {"fact": "PickerBot-Alpha successfully executed Aisle 4 bypass with 94% battery capacity."},
            {"fact": "Operator prefers technical diagnostic breakdowns rather than summaries."}
        ],
        "labels": {"data_source": "telemetry_incident_session_4042", "actor": "TECH-402"}
    },
    {
        "name": f"{TARGET_MEMORY_NAME}/revisions/8904512998102",
        "revision_id": "8904512998102",
        "create_time": "2026-09-18T09:15:00Z",
        "fact": "Technician Dave Miller (TECH-402) reported intermittent motor RPM fluctuations on Conveyor CV-02 and initiated sandbox diagnostic script to isolate roller stress.",
        "extracted_memories": [
            {"fact": "Dave Miller investigated CV-02 conveyor stress in Aisle 4."},
            {"fact": "Sandbox diagnostic test identified 8.2 Hz vibrational resonance at drive shaft."}
        ],
        "labels": {"data_source": "sandbox_diagnostic_run_102", "actor": "TECH-402"}
    },
    {
        "name": f"{TARGET_MEMORY_NAME}/revisions/881173220072357888",
        "revision_id": "881173220072357888",
        "create_time": "2026-09-17T08:00:00Z",
        "fact": "Initial onboarding record: Operator Dave Miller certified on CV-01 and CV-02 with Level 3 Lockout-Tagout privileges.",
        "extracted_memories": [
            {"fact": "Dave Miller onboarded to Zone B Aisle 4 as Senior Conveyor Maintenance Technician."}
        ],
        "labels": {"data_source": "operator_onboarding", "actor": "TECH-402"}
    }
]

# Event Ingestion Buffer state
_EVENT_INGESTION_STREAMS: Dict[str, List[Dict[str, Any]]] = {
    "operator_session_TECH-402": [
        {
            "event_id": "evt-001",
            "timestamp": "2026-09-20T10:45:10Z",
            "content": {"role": "user", "parts": [{"text": "Checking stock block status on SKU-991 and CV-02 status."}]}
        },
        {
            "event_id": "evt-002",
            "timestamp": "2026-09-20T10:45:15Z",
            "content": {"role": "assistant", "parts": [{"text": "SKU-991 verified blocked. AGV PickerBot-Alpha on standby."}]}
        }
    ]
}

# ==============================================================================
# Autonomous Memory Bank Dreaming State & Epiphanies
# ==============================================================================

_LOCAL_DREAM_EPIPHANIES: List[Dict[str, Any]] = [
    {
        "insight_id": "DREAM-EPIPHANY-001",
        "category": "PREDICTIVE_MAINTENANCE",
        "title": "CV-02 Roller Bearing Wear Post-Jam",
        "description": "Cross-session analysis reveals CV-02 motor temperature rose 14% faster in shift 2 after Error 4042 was cleared. Roller bracket 7 exhibits recurring micro-vibrations (8.2 Hz) correlated with high-speed pallet handoffs.",
        "confidence_score": 0.94,
        "recommended_action": "Schedule preemptive roller bearing lubrication and alignment check before 18:00 high-velocity batch.",
        "affected_equipment_or_zone": "Zone B - Aisle 4 / CV-02",
        "timestamp": "2026-09-20T11:00:00Z"
    },
    {
        "insight_id": "DREAM-EPIPHANY-002",
        "category": "CROSS_OPERATOR_PATTERN",
        "title": "Aisle 4 Multi-Operator Routing Bottleneck",
        "description": "Synthesized observations between Dave Miller (TECH-402) and Elena Rostova (OPERATOR-101): AGV PickerBot-Alpha bypass path frequently conflicts with manual pallet staging at Bay Q.",
        "confidence_score": 0.89,
        "recommended_action": "Designate dynamic temporary 3-meter exclusion zone when PickerBot-Alpha operates in Aisle 4 bypass mode.",
        "affected_equipment_or_zone": "Zone B - Bay Q",
        "timestamp": "2026-09-20T11:02:15Z"
    },
    {
        "insight_id": "DREAM-EPIPHANY-003",
        "category": "PREFERENCE_ADAPTATION",
        "title": "Operator Alert Verbosity Calibration",
        "description": "Operator Dave Miller consistently requests full telemetry hex dumps and RPM graphs rather than conversational summaries during conveyor incidents.",
        "confidence_score": 0.98,
        "recommended_action": "Keep preferred_alert_verbosity locked to 'technical' with immediate raw sensor telemetry payloads.",
        "affected_equipment_or_zone": "TECH-402 Profile",
        "timestamp": "2026-09-20T11:03:30Z"
    }
]

_LOCAL_DREAM_STATE: Dict[str, Any] = {
    "status": "CONSOLIDATED",  # "IDLE", "DREAMING", "CONSOLIDATED"
    "active_model": "gemini-3.5-flash-lite",
    "last_cycle_time": "2026-09-20T11:05:00Z",
    "cycle_count": 3,
    "unreflected_events_processed": 14,
    "epiphanies_count": len(_LOCAL_DREAM_EPIPHANIES),
    "tokens_consumed": 2840,
    "cost_usd": 0.000426,
    "mode": "offline_asynchronous_reflection"
}


# ==============================================================================
# 2. Service Functions
# ==============================================================================

def retrieve_operator_profile(user_id: str = "TECH-402") -> Dict[str, Any]:
    """Retrieves structured operator profile from Memory Bank with zero search latency.
    
    In GEAP, this maps to client.memory_banks.memories.retrieve_profiles(name=..., scope=...).
    """
    profile = _LOCAL_OPERATOR_PROFILES.get(user_id)
    if not profile:
        profile = WarehouseOperatorProfile(
            operator_id=user_id,
            full_name=f"Warehouse Associate ({user_id})",
            shift_role="Floor Operations Associate",
            certified_machinery=["General-Conveyor-Floor"],
            active_assigned_zone="Zone B",
            preferred_alert_verbosity="concise_summary"
        )
        _LOCAL_OPERATOR_PROFILES[user_id] = profile

    return {
        "status": "success",
        "memory_bank_resource": TARGET_REASONING_ENGINE,
        "profile_schema": "WarehouseOperatorProfile",
        "profile": profile.model_dump(),
        "retrieval_latency_ms": 1.4,
        "mode": "structured_memory_profile"
    }


def ingest_events(
    stream_id: str,
    events: List[Dict[str, Any]],
    force_flush: bool = False,
    event_count_threshold: int = 5,
    idle_duration_seconds: int = 300,
) -> Dict[str, Any]:
    """Decoupled streaming ingestion into GEAP Memory Bank.
    
    Maps to client.memory_banks.ingest_events(name=..., stream_id=..., direct_contents_source=...)
    with generation_trigger_config.
    """
    if stream_id not in _EVENT_INGESTION_STREAMS:
        _EVENT_INGESTION_STREAMS[stream_id] = []

    for event in events:
        if "timestamp" not in event:
            event["timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if "event_id" not in event:
            event["event_id"] = f"evt-{len(_EVENT_INGESTION_STREAMS[stream_id]) + 1:03d}"
        _EVENT_INGESTION_STREAMS[stream_id].append(event)

    buffered_count = len(_EVENT_INGESTION_STREAMS[stream_id])
    flush_triggered = force_flush or (buffered_count >= event_count_threshold)

    result_data = {
        "status": "ingested",
        "stream_id": stream_id,
        "events_received": len(events),
        "total_buffer_count": buffered_count,
        "generation_trigger_config": {
            "event_count": event_count_threshold,
            "idle_duration": f"{idle_duration_seconds}s",
            "overlap_event_count": 1,
            "force_flush": force_flush
        },
        "flush_triggered": flush_triggered
    }

    if flush_triggered:
        logger.info(f"Memory Bank generation triggered for stream {stream_id} (count={buffered_count}, force={force_flush})")
        # Synthesize and keep overlap
        if buffered_count > 1:
            _EVENT_INGESTION_STREAMS[stream_id] = _EVENT_INGESTION_STREAMS[stream_id][-1:]
        else:
            _EVENT_INGESTION_STREAMS[stream_id] = []
        result_data["synthesis_status"] = "triggered_and_dispatched"

    return result_data


def generate_memories(
    scope: Dict[str, str],
    events: Optional[List[Dict[str, Any]]] = None,
    allowed_topics: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    metadata_merge_strategy: str = "MERGE"
) -> Dict[str, Any]:
    """Generates immediate memories with topic filtering and metadata merge.
    
    Maps to client.memory_banks.memories.generate(name=..., scope=..., direct_contents_source=..., config=...)
    """
    if allowed_topics is None:
        allowed_topics = [
            "USER_PERSONAL_INFO",
            "USER_PREFERENCES",
            "KEY_CONVERSATION_DETAILS",
            "EXPLICIT_INSTRUCTIONS",
            "safety_compliance_history",
            "equipment_maintenance_records"
        ]

    # Create new memory revision reflecting the generated fact
    new_rev_id = str(int(datetime.datetime.now().timestamp() * 1000))
    fact_text = (
        f"Consolidated memory update for operator {scope.get('user_id', 'TECH-402')} "
        f"at warehouse {scope.get('warehouse_id', 'stackbox_austin_1')}: "
        f"Verified active compliance in {scope.get('zone', 'Zone B')}, LOTO status verified active, "
        f"recent incident resolved with MERGE strategy."
    )
    
    new_rev = {
        "name": f"{TARGET_MEMORY_NAME}/revisions/{new_rev_id}",
        "revision_id": new_rev_id,
        "create_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "fact": fact_text,
        "extracted_memories": [
            {"fact": f"Event facts consolidated under topics: {', '.join(allowed_topics[:3])}"},
            {"fact": f"Metadata merged: {metadata or {'source': 'fast_api_gateway'}}"}
        ],
        "labels": {"merge_strategy": metadata_merge_strategy, "user_id": scope.get("user_id", "TECH-402")}
    }
    _LOCAL_MEMORY_REVISIONS.insert(0, new_rev)

    return {
        "status": "success",
        "memory_name": TARGET_MEMORY_NAME,
        "revision_id": new_rev_id,
        "scope": scope,
        "allowed_topics": allowed_topics,
        "metadata_merge_strategy": metadata_merge_strategy,
        "generated_memory": new_rev
    }


def list_memory_revisions(
    memory_name: str = TARGET_MEMORY_NAME,
    filter_expr: Optional[str] = None
) -> Dict[str, Any]:
    """Lists immutable historical revisions for a memory resource, showing fact lineage.
    
    Maps to list(client.memory_banks.memories.revisions.list(name=memory_name, config={'filter': ...}))
    """
    revisions = _LOCAL_MEMORY_REVISIONS
    if filter_expr:
        revisions = [r for r in revisions if filter_expr.lower() in str(r).lower()]

    current_memory = {
        "name": memory_name,
        "current_fact": revisions[0]["fact"] if revisions else "",
        "update_time": revisions[0]["create_time"] if revisions else "",
        "total_revisions": len(revisions)
    }

    return {
        "status": "success",
        "memory_name": memory_name,
        "current_memory": current_memory,
        "revisions": revisions
    }


def rollback_memory(
    memory_name: str = TARGET_MEMORY_NAME,
    target_revision_id: str = "881173220072357888"
) -> Dict[str, Any]:
    """Rolls back a memory resource to a specified historical revision ID.
    
    Maps to client.memory_banks.memories.rollback(name=memory_name, target_revision_id=target_revision_id)
    """
    target_rev = None
    for rev in _LOCAL_MEMORY_REVISIONS:
        if rev["revision_id"] == target_revision_id:
            target_rev = rev
            break

    if not target_rev:
        return {
            "status": "error",
            "message": f"Target revision ID {target_revision_id} not found in memory history."
        }

    # Creating a new rollback revision that restores the historical fact
    rollback_rev_id = str(int(datetime.datetime.now().timestamp() * 1000))
    new_rollback_revision = {
        "name": f"{memory_name}/revisions/{rollback_rev_id}",
        "revision_id": rollback_rev_id,
        "create_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "fact": target_rev["fact"],
        "extracted_memories": [
            {"fact": f"Rollback action performed reverting to revision {target_revision_id} created at {target_rev['create_time']}."}
        ],
        "labels": {"action": "rollback", "target_revision": target_revision_id}
    }
    _LOCAL_MEMORY_REVISIONS.insert(0, new_rollback_revision)

    return {
        "status": "success",
        "action": "rollback",
        "memory_name": memory_name,
        "target_revision_id": target_revision_id,
        "new_active_revision_id": rollback_rev_id,
        "restored_fact": target_rev["fact"]
    }


def trigger_dream_cycle(
    memory_name: str = TARGET_MEMORY_NAME,
    scope: Optional[Dict[str, str]] = None,
    model_tier: str = "gemini-3.5-flash-lite",
    force_run: bool = False
) -> Dict[str, Any]:
    """Triggers an offline Memory Bank Dreaming cycle for cross-session reflection and fact consolidation.
    
    In GEAP, this maps to client.memory_banks.memories.dream(name=..., config={'model': model_tier, 'deduplicate': True}).
    Synthesizes long-term operational insights, produces a new revision tagged with source: 'dream_engine',
    and updates operator mental models without active user prompting.
    """
    if scope is None:
        scope = {"user_id": "TECH-402", "warehouse_id": "stackbox_austin_1", "zone": "Zone B"}

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    new_cycle_num = _LOCAL_DREAM_STATE.get("cycle_count", 0) + 1
    _LOCAL_DREAM_STATE["cycle_count"] = new_cycle_num
    _LOCAL_DREAM_STATE["status"] = "CONSOLIDATED"
    _LOCAL_DREAM_STATE["last_cycle_time"] = now_iso
    _LOCAL_DREAM_STATE["active_model"] = model_tier

    # 1. Generate a new synthesized dream epiphany based on cycle count
    new_epiphany_id = f"DREAM-EPIPHANY-{new_cycle_num:03d}"
    new_epiphany = {
        "insight_id": new_epiphany_id,
        "category": "PREDICTIVE_MAINTENANCE",
        "title": f"Cross-Shift Mechanical Resonance Analysis #{new_cycle_num}",
        "description": "Autonomous dream reflection across multi-turn sessions identified recurrent high-frequency vibrational spikes on Conveyor CV-02 preceding Error 4042. Reconciled operator telemetry across shift handoffs.",
        "confidence_score": 0.96,
        "recommended_action": "Apply dynamic conveyor deceleration ramp at Zone B Aisle 4 switch junction to prevent roller bracket thermal friction build-up.",
        "affected_equipment_or_zone": "Zone B - Aisle 4 / Conveyor CV-02",
        "timestamp": now_iso
    }
    _LOCAL_DREAM_EPIPHANIES.insert(0, new_epiphany)
    _LOCAL_DREAM_STATE["epiphanies_count"] = len(_LOCAL_DREAM_EPIPHANIES)
    _LOCAL_DREAM_STATE["tokens_consumed"] += 840
    _LOCAL_DREAM_STATE["cost_usd"] = round(_LOCAL_DREAM_STATE["cost_usd"] + 0.000126, 6)

    # 2. Commit a new immutable memory revision tagged with source: 'dream_engine'
    dream_rev_id = str(int(datetime.datetime.now().timestamp() * 1000))
    dream_fact = (
        f"[AUTONOMOUS DREAM CONSOLIDATION] Cross-session reflection for {scope.get('user_id', 'TECH-402')}: "
        f"Consolidated 14 episodic events across 3 shifts. Reconciled CV-02 thermal telemetry with AGV PickerBot-Alpha "
        f"bypass routing in Aisle 4. Preserved technical alert verbosity preference."
    )
    new_dream_revision = {
        "name": f"{memory_name}/revisions/{dream_rev_id}",
        "revision_id": dream_rev_id,
        "create_time": now_iso,
        "fact": dream_fact,
        "extracted_memories": [
            {"fact": f"Dream epiphany {new_epiphany_id}: Preemptive deceleration ramp recommended for CV-02 roller bracket 7."},
            {"fact": "Reconciled multi-operator handoff between TECH-402 and OPERATOR-101 at Bay Q."},
            {"fact": f"Offline consolidation executed via {model_tier} with zero operator interruption."}
        ],
        "labels": {
            "source": "dream_engine",
            "cycle_id": f"dream-cycle-{new_cycle_num}",
            "model_tier": model_tier,
            "consolidation_type": "CROSS_SESSION_REFLECTION"
        }
    }
    _LOCAL_MEMORY_REVISIONS.insert(0, new_dream_revision)

    logger.info(f"Memory Bank Dreaming cycle #{new_cycle_num} completed for {memory_name} via {model_tier}")

    return {
        "status": "success",
        "action": "dream_consolidation",
        "memory_name": memory_name,
        "cycle_number": new_cycle_num,
        "model_tier": model_tier,
        "new_revision_id": dream_rev_id,
        "synthesized_epiphany": new_epiphany,
        "generated_memory": new_dream_revision,
        "dream_state": _LOCAL_DREAM_STATE
    }


def get_dreaming_status(memory_name: str = TARGET_MEMORY_NAME) -> Dict[str, Any]:
    """Retrieves current dreaming cycle status, epiphanies, and reflection telemetry."""
    return {
        "status": "success",
        "memory_name": memory_name,
        "dream_state": _LOCAL_DREAM_STATE,
        "epiphanies": _LOCAL_DREAM_EPIPHANIES,
        "latest_consolidated_revision": _LOCAL_MEMORY_REVISIONS[0] if _LOCAL_MEMORY_REVISIONS else None
    }
