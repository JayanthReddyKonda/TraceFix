"""Repair orchestration, state machine, patch generation, and validation.

Workstream B component for TraceFix.
"""

from __future__ import annotations

from tracefix.repair.interfaces import (
    CandidatePatch,
    InvalidStateTransitionError,
    ModelProvider,
    PatchValidationError,
    RepairConfig,
    RepairError,
    RepairRequest,
    RepairResult,
    RepairState,
    RetryEvent,
    RetryExhaustedError,
)
from tracefix.repair.state_machine import RepairOrchestrator, RepairStateMachine

__all__ = [
    "CandidatePatch",
    "InvalidStateTransitionError",
    "ModelProvider",
    "PatchValidationError",
    "RepairConfig",
    "RepairError",
    "RepairOrchestrator",
    "RepairRequest",
    "RepairResult",
    "RepairState",
    "RepairStateMachine",
    "RetryEvent",
    "RetryExhaustedError",
]
