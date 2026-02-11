"""Pydantic v2 models for the Triad Orchestration System.

Defines TaskPacket, ImplementationReport, ReviewReport, and the
full CONTEXT.json schema — all derived from AGENTS.md specifications.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Phase(str, Enum):
    """Workflow phases from CLAUDE.md state machine."""

    PLANNING = "planning"
    IMPLEMENTATION = "implementation"
    REVIEW = "review"
    APPROVED = "approved"
    REJECTED = "rejected"


class AgentRole(str, Enum):
    """Agent identifiers."""

    ARCHITECT = "architect"
    IMPLEMENTER = "implementer"
    AUDITOR = "auditor"


class Priority(str, Enum):
    """Task priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Severity(str, Enum):
    """Review finding severity."""

    INFO = "info"
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"


class Verdict(str, Enum):
    """Auditor review verdict."""

    APPROVED = "approved"
    REJECTED = "rejected"


class FileAction(str, Enum):
    """File change action types."""

    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"


# ---------------------------------------------------------------------------
# Task Packet (Architect → Implementer)
# ---------------------------------------------------------------------------

class TaskPacket(BaseModel):
    """Work unit created by Architect for Implementer."""

    task_id: str = Field(..., pattern=r"^TASK-\d{3,}$")
    title: str
    description: str
    acceptance_criteria: list[str] = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)
    affected_files: list[str] = Field(default_factory=list)
    priority: Priority = Priority.MEDIUM
    depends_on: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Implementation Report (Implementer → Auditor)
# ---------------------------------------------------------------------------

class FileChange(BaseModel):
    """Single file change record."""

    path: str
    action: FileAction
    summary: str


class TestResult(BaseModel):
    """Aggregated test execution results."""

    total: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    coverage: float = Field(ge=0, le=100)


class ImplementationReport(BaseModel):
    """Report submitted by Implementer after completing a task."""

    task_id: str
    status: str = "completed"
    files_changed: list[FileChange] = Field(default_factory=list)
    tests: TestResult | None = None
    deviations: list[str] = Field(default_factory=list)
    notes: str = ""


# ---------------------------------------------------------------------------
# Review Report (Auditor)
# ---------------------------------------------------------------------------

class ReviewItem(BaseModel):
    """Single review finding."""

    file: str
    line: int | None = None
    severity: Severity
    message: str


class PrdCompliance(BaseModel):
    """PRD requirement tracking."""

    requirements_met: list[str] = Field(default_factory=list)
    requirements_missing: list[str] = Field(default_factory=list)


class ReviewReport(BaseModel):
    """Report submitted by Auditor after reviewing implementation."""

    task_id: str
    verdict: Verdict
    review_items: list[ReviewItem] = Field(default_factory=list)
    prd_compliance: PrdCompliance = Field(default_factory=PrdCompliance)
    security_findings: list[str] = Field(default_factory=list)
    changelog_entry: str = ""


# ---------------------------------------------------------------------------
# Handoff Messages
# ---------------------------------------------------------------------------

class ArchitectToImplementer(BaseModel):
    """Handoff payload: Architect → Implementer."""

    handoff: str = "architect_to_implementer"
    task_packet: TaskPacket
    context_summary: str = ""
    reference_files: list[str] = Field(default_factory=list)


class ImplementerToAuditor(BaseModel):
    """Handoff payload: Implementer → Auditor."""

    handoff: str = "implementer_to_auditor"
    implementation_report: ImplementationReport
    review_scope: list[str] = Field(default_factory=list)
    test_command: str = ""


class AuditorToArchitect(BaseModel):
    """Handoff payload: Auditor → Architect (rejection only)."""

    handoff: str = "auditor_to_architect"
    review_report: ReviewReport
    action_required: str = ""
    suggested_approach: str = ""


# ---------------------------------------------------------------------------
# Reasoning Log Entry
# ---------------------------------------------------------------------------

class ReasoningLog(BaseModel):
    """Single entry in the reasoning_logs array."""

    timestamp: datetime = Field(default_factory=datetime.now)
    agent: AgentRole
    task_id: str | None = None
    action: str
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# CONTEXT.json Root Schema
# ---------------------------------------------------------------------------

class StyleConfig(BaseModel):
    """Code style configuration."""

    python: str = "black"
    typescript: str = "prettier"


class TestingConfig(BaseModel):
    """Testing configuration."""

    framework: list[str] = Field(default_factory=lambda: ["pytest", "jest"])
    min_coverage: int = 80


class ActiveConstraints(BaseModel):
    """Project-wide constraints."""

    language: list[str] = Field(
        default_factory=lambda: ["Python 3.12+", "TypeScript 5.5+"]
    )
    style: StyleConfig = Field(default_factory=StyleConfig)
    testing: TestingConfig = Field(default_factory=TestingConfig)
    typing: str = "strict"


class KnownIssue(BaseModel):
    """Tracked known issue."""

    id: str
    description: str
    severity: Severity = Severity.MINOR
    reported_by: AgentRole = AgentRole.AUDITOR


class ProjectContext(BaseModel):
    """Root schema for docs/CONTEXT.json — Single Source of Truth."""

    project_name: str = "context-trio"
    global_phase: Phase = Phase.PLANNING
    current_task: str | None = None
    task_queue: list[TaskPacket] = Field(default_factory=list)
    completed_tasks: list[str] = Field(default_factory=list)
    active_constraints: ActiveConstraints = Field(
        default_factory=ActiveConstraints
    )
    reasoning_logs: list[ReasoningLog] = Field(default_factory=list)
    known_issues: list[KnownIssue] = Field(default_factory=list)
    last_updated_by: AgentRole = AgentRole.ARCHITECT
    last_updated_at: datetime = Field(default_factory=datetime.now)
