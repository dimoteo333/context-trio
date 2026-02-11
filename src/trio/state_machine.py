"""Phase transition state machine for the Triad Orchestration workflow.

Implements the state machine defined in CLAUDE.md Section 2:

    planning → implementation → review → approved
                                  ↓
                               rejected → planning
"""

from __future__ import annotations

from .exceptions import PhaseTransitionError
from .schemas import AgentRole, Phase

# Valid transitions: (from_phase, to_phase) → required_agent
TRANSITIONS: dict[tuple[Phase, Phase], AgentRole | None] = {
    (Phase.PLANNING, Phase.IMPLEMENTATION): AgentRole.ARCHITECT,
    (Phase.IMPLEMENTATION, Phase.REVIEW): AgentRole.IMPLEMENTER,
    (Phase.REVIEW, Phase.APPROVED): AgentRole.AUDITOR,
    (Phase.REVIEW, Phase.REJECTED): AgentRole.AUDITOR,
    (Phase.REJECTED, Phase.PLANNING): AgentRole.ARCHITECT,
}


def validate_transition(
    current: Phase,
    target: Phase,
    agent: AgentRole | None = None,
) -> bool:
    """Check whether a phase transition is valid.

    Args:
        current: The current workflow phase.
        target: The desired next phase.
        agent: The agent requesting the transition (optional strict check).

    Returns:
        True if the transition is valid.

    Raises:
        PhaseTransitionError: If the transition is not allowed.
    """
    key = (current, target)
    if key not in TRANSITIONS:
        raise PhaseTransitionError(current.value, target.value)

    required_agent = TRANSITIONS[key]
    if agent is not None and required_agent is not None and agent != required_agent:
        raise PhaseTransitionError(
            current.value,
            f"{target.value} (requires {required_agent.value}, got {agent.value})",
        )

    return True


def get_valid_targets(current: Phase) -> list[Phase]:
    """Return all phases reachable from the current phase.

    Args:
        current: The current workflow phase.

    Returns:
        List of valid target phases.
    """
    return [target for (src, target) in TRANSITIONS if src == current]


def get_active_agent(phase: Phase) -> AgentRole | None:
    """Return the agent responsible for the given phase.

    Args:
        phase: The workflow phase.

    Returns:
        The active agent, or None for terminal phases.
    """
    phase_agents: dict[Phase, AgentRole | None] = {
        Phase.PLANNING: AgentRole.ARCHITECT,
        Phase.IMPLEMENTATION: AgentRole.IMPLEMENTER,
        Phase.REVIEW: AgentRole.AUDITOR,
        Phase.APPROVED: None,
        Phase.REJECTED: AgentRole.ARCHITECT,
    }
    return phase_agents.get(phase)
