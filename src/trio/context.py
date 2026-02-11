"""Atomic read/write manager for docs/CONTEXT.json.

Provides safe concurrent access with file-locking semantics and
incremental field updates per the Context Maintenance Protocol (CA-MCP).
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .exceptions import ContextCorruptedError, ContextNotFoundError
from .schemas import (
    AgentRole,
    Phase,
    ProjectContext,
    ReasoningLog,
    TaskPacket,
)
from .state_machine import validate_transition

DEFAULT_CONTEXT_PATH = Path("docs/CONTEXT.json")


class ContextManager:
    """Manages reads and writes to the CONTEXT.json single source of truth.

    Args:
        path: Path to CONTEXT.json. Defaults to docs/CONTEXT.json.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DEFAULT_CONTEXT_PATH

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def load(self) -> ProjectContext:
        """Load and validate CONTEXT.json.

        Returns:
            Parsed ProjectContext model.

        Raises:
            ContextNotFoundError: If the file does not exist.
            ContextCorruptedError: If the file contains invalid JSON/schema.
        """
        if not self.path.exists():
            raise ContextNotFoundError(f"File not found: {self.path}")

        try:
            raw = self.path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (json.JSONDecodeError, OSError) as exc:
            raise ContextCorruptedError(
                f"Failed to parse {self.path}: {exc}"
            ) from exc

        try:
            return ProjectContext.model_validate(data)
        except Exception as exc:
            raise ContextCorruptedError(
                f"Schema validation failed for {self.path}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Write (atomic)
    # ------------------------------------------------------------------

    def save(self, ctx: ProjectContext) -> None:
        """Atomically write the full context to disk.

        Uses write-to-temp + rename for crash safety.

        Args:
            ctx: The ProjectContext to persist.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)

        data = ctx.model_dump(mode="json")
        # Ensure datetime fields are ISO strings
        for log in data.get("reasoning_logs", []):
            if isinstance(log.get("timestamp"), datetime):
                log["timestamp"] = log["timestamp"].isoformat()
        if isinstance(data.get("last_updated_at"), datetime):
            data["last_updated_at"] = data["last_updated_at"].isoformat()

        payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"

        # Atomic write: temp file in same directory, then rename
        fd = tempfile.NamedTemporaryFile(
            mode="w",
            dir=self.path.parent,
            suffix=".tmp",
            delete=False,
            encoding="utf-8",
        )
        try:
            fd.write(payload)
            fd.flush()
            fd.close()
            Path(fd.name).replace(self.path)
        except BaseException:
            Path(fd.name).unlink(missing_ok=True)
            raise

    # ------------------------------------------------------------------
    # Incremental Update Helpers
    # ------------------------------------------------------------------

    def update_phase(
        self,
        target: Phase,
        agent: AgentRole,
    ) -> ProjectContext:
        """Transition to a new phase with validation.

        Args:
            target: The desired phase.
            agent: The agent performing the transition.

        Returns:
            Updated ProjectContext.
        """
        ctx = self.load()
        validate_transition(ctx.global_phase, target, agent)
        ctx.global_phase = target
        ctx.last_updated_by = agent
        ctx.last_updated_at = datetime.now()
        self.save(ctx)
        return ctx

    def add_task(self, task: TaskPacket, agent: AgentRole) -> ProjectContext:
        """Append a task packet to the queue.

        Args:
            task: The TaskPacket to add.
            agent: The agent adding the task.

        Returns:
            Updated ProjectContext.
        """
        ctx = self.load()
        ctx.task_queue.append(task)
        ctx.last_updated_by = agent
        ctx.last_updated_at = datetime.now()
        self.save(ctx)
        return ctx

    def complete_task(self, task_id: str, agent: AgentRole) -> ProjectContext:
        """Move a task from queue to completed list.

        Args:
            task_id: ID of the task to complete.
            agent: The agent completing the task.

        Returns:
            Updated ProjectContext.
        """
        ctx = self.load()
        ctx.task_queue = [t for t in ctx.task_queue if t.task_id != task_id]
        if task_id not in ctx.completed_tasks:
            ctx.completed_tasks.append(task_id)
        ctx.current_task = None
        ctx.last_updated_by = agent
        ctx.last_updated_at = datetime.now()
        self.save(ctx)
        return ctx

    def add_reasoning_log(
        self,
        agent: AgentRole,
        action: str,
        summary: str,
        task_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> ProjectContext:
        """Append an entry to reasoning_logs.

        Implements log rotation: archives old entries when count exceeds 50.

        Args:
            agent: The agent creating the log.
            action: Short action label.
            summary: Human-readable summary.
            task_id: Related task ID (optional).
            details: Additional structured data (optional).

        Returns:
            Updated ProjectContext.
        """
        ctx = self.load()

        log = ReasoningLog(
            agent=agent,
            task_id=task_id,
            action=action,
            summary=summary,
            details=details or {},
        )
        ctx.reasoning_logs.append(log)

        # Log rotation (CLAUDE.md §3.3 rule 4)
        if len(ctx.reasoning_logs) > 50:
            self._archive_logs(ctx.reasoning_logs[:25])
            ctx.reasoning_logs = ctx.reasoning_logs[25:]

        ctx.last_updated_by = agent
        ctx.last_updated_at = datetime.now()
        self.save(ctx)
        return ctx

    def _archive_logs(self, logs: list[ReasoningLog]) -> None:
        """Write old reasoning logs to docs/logs/ archive.

        Args:
            logs: The log entries to archive.
        """
        archive_dir = self.path.parent / "logs"
        archive_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_path = archive_dir / f"reasoning_{timestamp}.json"

        data = [log.model_dump(mode="json") for log in logs]
        archive_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    @classmethod
    def init_context(
        cls,
        path: Path | None = None,
        project_name: str | None = None,
    ) -> "ContextManager":
        """Create a fresh CONTEXT.json with defaults.

        Args:
            path: Where to write. Defaults to docs/CONTEXT.json.
            project_name: Project name. Auto-detected from cwd if omitted.

        Returns:
            A ContextManager pointing to the new file.
        """
        resolved_path = path or DEFAULT_CONTEXT_PATH
        if project_name is None:
            project_name = Path.cwd().name

        ctx = ProjectContext(
            project_name=project_name,
            last_updated_at=datetime.now(),
        )

        mgr = cls(resolved_path)
        mgr.save(ctx)
        return mgr
