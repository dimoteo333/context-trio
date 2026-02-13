"""Agent invocation layer for the Triad Orchestration System.

Each function spawns an external CLI process (claude, gemini, etc.)
with the appropriate prompt and environment configuration.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .config import AgentConfig
from .exceptions import AgentInvocationError, AgentTimeoutError

# Timeouts in seconds
PLAN_TIMEOUT = 300       # 5 minutes
IMPLEMENT_TIMEOUT = 900  # 15 minutes
REVIEW_TIMEOUT = 300     # 5 minutes


def _run_agent(
    config: AgentConfig,
    prompt: str,
    *,
    timeout: int,
    extra_args: list[str] | None = None,
    remove_env_keys: list[str] | None = None,
) -> str:
    """Run an agent CLI command and return its stdout.

    Args:
        config: Agent configuration (command, args, env overrides).
        prompt: The prompt text to pass to the agent.
        timeout: Maximum execution time in seconds.
        extra_args: Additional CLI arguments.
        remove_env_keys: Environment variables to remove (e.g. CLAUDECODE).

    Returns:
        The agent's stdout output.

    Raises:
        AgentTimeoutError: If the process exceeds the timeout.
        AgentInvocationError: If the process exits with non-zero code.
    """
    env = os.environ.copy()

    # Apply env overrides from config
    env.update(config.env_overrides)

    # Remove specified keys (e.g. prevent nested sessions)
    for key in remove_env_keys or []:
        env.pop(key, None)

    cmd = [config.command, *config.default_args]
    if extra_args:
        cmd.extend(extra_args)
    cmd.append(prompt)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=Path.cwd(),
        )
    except subprocess.TimeoutExpired as exc:
        raise AgentTimeoutError(config.name, timeout) from exc
    except FileNotFoundError as exc:
        raise AgentInvocationError(
            config.name, -1, f"Command not found: {config.command}"
        ) from exc

    if result.returncode != 0:
        raise AgentInvocationError(
            config.name, result.returncode, result.stderr
        )

    return result.stdout


def invoke_architect(prompt: str, config: AgentConfig) -> str:
    """Invoke the Architect agent to generate a plan.

    Args:
        prompt: System prompt for plan generation.
        config: Architect agent configuration.

    Returns:
        The plan text (markdown).
    """
    return _run_agent(config, prompt, timeout=PLAN_TIMEOUT)


def invoke_implementer(prompt: str, config: AgentConfig) -> str:
    """Invoke the Implementer agent to execute a plan.

    Args:
        prompt: Prompt containing the plan to execute.
        config: Implementer agent configuration.

    Returns:
        The implementation output.
    """
    return _run_agent(
        config,
        prompt,
        timeout=IMPLEMENT_TIMEOUT,
        # Prevent nested claude session detection
        remove_env_keys=["CLAUDECODE"],
    )


def invoke_auditor(prompt: str, config: AgentConfig) -> str:
    """Invoke the Auditor agent to review implementation.

    Args:
        prompt: Review prompt with plan and diff.
        config: Auditor agent configuration.

    Returns:
        The review output.
    """
    return _run_agent(config, prompt, timeout=REVIEW_TIMEOUT)


def get_git_diff() -> str:
    """Capture the current git diff (staged + unstaged).

    Returns:
        The diff text, or empty string if no changes.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def git_commit_and_push(message: str, *, push: bool = True) -> None:
    """Stage all changes, commit, and optionally push.

    Args:
        message: Commit message.
        push: Whether to push after committing.
    """
    subprocess.run(["git", "add", "."], check=True, timeout=30)
    subprocess.run(
        ["git", "commit", "-m", message], check=True, timeout=30
    )
    if push:
        subprocess.run(["git", "push"], check=True, timeout=60)
