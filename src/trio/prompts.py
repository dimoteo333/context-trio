"""Agent-specific system prompt builder.

Assembles complete prompts for each agent by combining:
1. Identity — agent persona from AGENTS.md
2. Rules — relevant sections from CLAUDE.md
3. Context — current CONTEXT.json state
4. Task — concrete work payload
5. Format — expected output JSON schema

This is the core value module of context-trio: it ensures each agent
receives a self-contained prompt with full situational awareness.
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent
from typing import Any

from .schemas import AgentRole, Phase, ProjectContext, TaskPacket


# ---------------------------------------------------------------------------
# File readers (with fallback)
# ---------------------------------------------------------------------------

def _read_file(path: Path | str) -> str:
    """Read a text file, returning empty string if missing."""
    p = Path(path)
    if p.exists():
        return p.read_text(encoding="utf-8")
    return ""


def _read_section(filepath: Path | str, heading: str) -> str:
    """Extract a markdown section by heading (## level).

    Args:
        filepath: Path to the markdown file.
        heading: The heading text to find (without ## prefix).

    Returns:
        The section content, or empty string if not found.
    """
    content = _read_file(filepath)
    if not content:
        return ""

    lines = content.split("\n")
    capture = False
    result: list[str] = []

    for line in lines:
        if line.startswith("## ") and heading.lower() in line.lower():
            capture = True
            result.append(line)
            continue
        if capture and line.startswith("## "):
            break
        if capture:
            result.append(line)

    return "\n".join(result).strip()


# ---------------------------------------------------------------------------
# Persona extraction from AGENTS.md
# ---------------------------------------------------------------------------

_AGENT_HEADING_MAP: dict[AgentRole, str] = {
    AgentRole.ARCHITECT: "1. ARCHITECT",
    AgentRole.IMPLEMENTER: "2. IMPLEMENTER",
    AgentRole.AUDITOR: "3. AUDITOR",
}


def _extract_persona(agents_md: Path | str, role: AgentRole) -> str:
    """Extract the full persona section for an agent from AGENTS.md.

    Args:
        agents_md: Path to AGENTS.md.
        role: Which agent's persona to extract.

    Returns:
        The agent's persona section text.
    """
    heading = _AGENT_HEADING_MAP[role]
    return _read_section(agents_md, heading)


# ---------------------------------------------------------------------------
# Rules extraction from CLAUDE.md
# ---------------------------------------------------------------------------

_RULES_SECTIONS: dict[AgentRole, list[str]] = {
    AgentRole.ARCHITECT: [
        "Workflow State Machine",
        "Context Maintenance Protocol",
        "Handoff Protocol",
        "File Ownership",
        "Prohibited Actions",
    ],
    AgentRole.IMPLEMENTER: [
        "Coding Standards",
        "Context Maintenance Protocol",
        "Handoff Protocol",
        "File Ownership",
        "Error Handling & Escalation",
        "Prohibited Actions",
    ],
    AgentRole.AUDITOR: [
        "Workflow State Machine",
        "Context Maintenance Protocol",
        "Handoff Protocol",
        "File Ownership",
        "Coding Standards",
        "Prohibited Actions",
    ],
}


def _extract_rules(claude_md: Path | str, role: AgentRole) -> str:
    """Extract relevant CLAUDE.md sections for a given agent role.

    Args:
        claude_md: Path to CLAUDE.md.
        role: Which agent's rules to extract.

    Returns:
        Concatenated rules text.
    """
    sections = _RULES_SECTIONS[role]
    parts: list[str] = []
    for heading in sections:
        section = _read_section(claude_md, heading)
        if section:
            parts.append(section)
    return "\n\n---\n\n".join(parts)


# ---------------------------------------------------------------------------
# Context summary
# ---------------------------------------------------------------------------

def _summarize_context(ctx: ProjectContext) -> str:
    """Build a concise context summary from the current project state.

    Args:
        ctx: The current ProjectContext.

    Returns:
        Formatted context summary string.
    """
    task_ids = [t.task_id for t in ctx.task_queue]
    recent_logs = ctx.reasoning_logs[-5:] if ctx.reasoning_logs else []
    log_lines = [
        f"  - [{log.agent.value}] {log.action}: {log.summary}"
        for log in recent_logs
    ]

    return dedent(f"""\
        ## Current Context
        - **Project:** {ctx.project_name}
        - **Phase:** {ctx.global_phase.value}
        - **Current Task:** {ctx.current_task or "None"}
        - **Task Queue:** {json.dumps(task_ids)}
        - **Completed Tasks:** {json.dumps(ctx.completed_tasks)}
        - **Known Issues:** {len(ctx.known_issues)} item(s)
        - **Constraints:** {json.dumps(ctx.active_constraints.model_dump(), ensure_ascii=False)}

        ### Recent Activity
        {chr(10).join(log_lines) if log_lines else "  (no recent logs)"}
    """)


# ---------------------------------------------------------------------------
# Output format schemas
# ---------------------------------------------------------------------------

_OUTPUT_SCHEMAS: dict[AgentRole, str] = {
    AgentRole.ARCHITECT: dedent("""\
        ## Expected Output Format
        You MUST output a valid JSON object matching this schema:
        ```json
        {
          "task_id": "TASK-NNN",
          "title": "string",
          "description": "string",
          "acceptance_criteria": ["string", ...],
          "constraints": ["string", ...],
          "affected_files": ["string", ...],
          "priority": "low|medium|high|critical",
          "depends_on": ["TASK-NNN", ...]
        }
        ```
    """),
    AgentRole.IMPLEMENTER: dedent("""\
        ## Expected Output Format
        You MUST output a valid JSON object matching this schema:
        ```json
        {
          "task_id": "TASK-NNN",
          "status": "completed",
          "files_changed": [
            {"path": "string", "action": "created|modified|deleted", "summary": "string"}
          ],
          "tests": {"total": N, "passed": N, "failed": N, "coverage": N.N},
          "deviations": ["string", ...],
          "notes": "string"
        }
        ```
    """),
    AgentRole.AUDITOR: dedent("""\
        ## Expected Output Format
        You MUST output a valid JSON object matching this schema:
        ```json
        {
          "task_id": "TASK-NNN",
          "verdict": "approved|rejected",
          "review_items": [
            {"file": "string", "line": N, "severity": "info|minor|major|critical", "message": "string"}
          ],
          "prd_compliance": {
            "requirements_met": ["REQ-NNN", ...],
            "requirements_missing": ["REQ-NNN", ...]
          },
          "security_findings": ["string", ...],
          "changelog_entry": "string"
        }
        ```
    """),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_prompt(
    role: AgentRole,
    ctx: ProjectContext,
    *,
    task: TaskPacket | None = None,
    user_request: str = "",
    agents_md: Path | str = Path("AGENTS.md"),
    claude_md: Path | str = Path("CLAUDE.md"),
    extra_context: dict[str, Any] | None = None,
) -> str:
    """Assemble a complete system prompt for the given agent.

    Combines five layers:
    1. Identity (persona from AGENTS.md)
    2. Rules (relevant CLAUDE.md sections)
    3. Context (current CONTEXT.json state)
    4. Task (specific work payload or user request)
    5. Format (expected output JSON schema)

    Args:
        role: Which agent to build the prompt for.
        ctx: The current project context.
        task: A TaskPacket (for Implementer/Auditor). Optional.
        user_request: The user's original request (for Architect). Optional.
        agents_md: Path to AGENTS.md.
        claude_md: Path to CLAUDE.md.
        extra_context: Additional key-value pairs to include.

    Returns:
        A fully assembled prompt string.
    """
    parts: list[str] = []

    # 1. Identity
    persona = _extract_persona(agents_md, role)
    if persona:
        parts.append(f"# Agent Identity\n\n{persona}")

    # 2. Rules
    rules = _extract_rules(claude_md, role)
    if rules:
        parts.append(f"# Rules & Constraints\n\n{rules}")

    # 3. Context
    parts.append(_summarize_context(ctx))

    # 4. Task
    task_section = _build_task_section(role, task, user_request)
    if task_section:
        parts.append(task_section)

    # 5. Format
    output_schema = _OUTPUT_SCHEMAS.get(role, "")
    if output_schema:
        parts.append(output_schema)

    # Extra
    if extra_context:
        extra = "\n".join(f"- **{k}:** {v}" for k, v in extra_context.items())
        parts.append(f"## Additional Context\n{extra}")

    return "\n\n---\n\n".join(parts)


def _build_task_section(
    role: AgentRole,
    task: TaskPacket | None,
    user_request: str,
) -> str:
    """Build the task-specific section of the prompt.

    Args:
        role: The agent role.
        task: A TaskPacket, if applicable.
        user_request: A user request string, if applicable.

    Returns:
        Formatted task section.
    """
    if role == AgentRole.ARCHITECT:
        if user_request:
            return dedent(f"""\
                ## Your Task
                Analyze the following user request and produce a Task Packet:

                > {user_request}

                Break this down into actionable, atomic tasks for the Implementer.
                Record your architectural decisions.
            """)
        return ""

    if task:
        task_json = json.dumps(
            task.model_dump(mode="json"), indent=2, ensure_ascii=False
        )
        label = "Implement" if role == AgentRole.IMPLEMENTER else "Review"
        return dedent(f"""\
            ## Your Task
            {label} the following Task Packet:

            ```json
            {task_json}
            ```
        """)

    return ""
