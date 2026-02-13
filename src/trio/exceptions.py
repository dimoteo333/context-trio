"""Custom exception hierarchy for the Triad Orchestration System."""


class TrioError(Exception):
    """Base exception for all context-trio errors."""


class ContextError(TrioError):
    """Errors related to CONTEXT.json read/write operations."""


class ContextNotFoundError(ContextError):
    """CONTEXT.json file does not exist."""


class ContextCorruptedError(ContextError):
    """CONTEXT.json contains invalid data."""


class PhaseTransitionError(TrioError):
    """Invalid phase transition attempted."""

    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(
            f"Invalid phase transition: {current!r} -> {target!r}"
        )


class TaskError(TrioError):
    """Errors related to task operations."""


class TaskNotFoundError(TaskError):
    """Referenced task does not exist in the queue."""

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(f"Task not found: {task_id!r}")


class ConstraintViolationError(TrioError):
    """Active constraints in CONTEXT.json were violated."""


class AgentError(TrioError):
    """Errors related to external agent invocation."""


class AgentTimeoutError(AgentError):
    """Agent CLI process exceeded its timeout."""

    def __init__(self, agent: str, timeout: int) -> None:
        self.agent = agent
        self.timeout = timeout
        super().__init__(f"Agent {agent!r} timed out after {timeout}s")


class AgentInvocationError(AgentError):
    """Agent CLI process exited with a non-zero code."""

    def __init__(self, agent: str, returncode: int, stderr: str = "") -> None:
        self.agent = agent
        self.returncode = returncode
        self.stderr = stderr
        msg = f"Agent {agent!r} exited with code {returncode}"
        if stderr:
            msg += f": {stderr[:200]}"
        super().__init__(msg)
