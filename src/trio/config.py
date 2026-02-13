"""Agent configuration management for the Triad Orchestration System.

Handles first-time setup (interactive agent selection) and persistent
configuration stored in .trio/config.json.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from pydantic import BaseModel, Field

TRIO_DIR = Path(".trio")
CONFIG_PATH = TRIO_DIR / "config.json"


class AgentConfig(BaseModel):
    """Configuration for a single agent."""

    name: str
    command: str
    env_overrides: dict[str, str] = Field(default_factory=dict)
    default_args: list[str] = Field(default_factory=list)


class TrioConfig(BaseModel):
    """Top-level configuration for the trio pipeline."""

    architect: AgentConfig
    implementer: AgentConfig
    auditor: AgentConfig
    auto_commit: bool = True
    auto_push: bool = True


# ---------------------------------------------------------------------------
# Preset agent configurations
# ---------------------------------------------------------------------------

_PRESETS: dict[str, dict[str, AgentConfig]] = {
    "plan": {
        "Claude (Opus 4.6)": AgentConfig(
            name="claude",
            command="claude",
            default_args=["-p"],
        ),
        "GLM-4.7": AgentConfig(
            name="glm",
            command="claude",
            default_args=["-p"],
        ),
        "Gemini": AgentConfig(
            name="gemini",
            command="gemini",
            default_args=["-p"],
        ),
    },
    "implement": {
        "Claude (Opus 4.6)": AgentConfig(
            name="claude",
            command="claude",
            default_args=["-p"],
        ),
        "GLM-4.7": AgentConfig(
            name="glm",
            command="claude",
            default_args=["-p"],
        ),
        "Gemini": AgentConfig(
            name="gemini",
            command="gemini",
            default_args=["-p"],
        ),
    },
    "review": {
        "Claude (Opus 4.6)": AgentConfig(
            name="claude",
            command="claude",
            default_args=["-p"],
        ),
        "GLM-4.7": AgentConfig(
            name="glm",
            command="claude",
            default_args=["-p"],
        ),
        "Gemini": AgentConfig(
            name="gemini",
            command="gemini",
            default_args=["-p", "-y"],
        ),
    },
}

_DEFAULT_CHOICES = {
    "plan": "Claude (Opus 4.6)",
    "implement": "GLM-4.7",
    "review": "Gemini",
}

# Environment variable names captured from `gt g` for GLM
_GLM_ENV_KEYS = [
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_API_KEY",
]


def _detect_glm_env() -> dict[str, str]:
    """Capture GLM-related environment variables if present."""
    env: dict[str, str] = {}
    for key in _GLM_ENV_KEYS:
        val = os.environ.get(key)
        if val:
            env[key] = val
    return env


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def load_config() -> TrioConfig | None:
    """Load configuration from .trio/config.json.

    Returns:
        TrioConfig if file exists, None otherwise.
    """
    if not CONFIG_PATH.exists():
        return None
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return TrioConfig.model_validate(data)


def save_config(config: TrioConfig) -> None:
    """Persist configuration to .trio/config.json."""
    TRIO_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        config.model_dump(mode="json"), indent=2, ensure_ascii=False
    ) + "\n"
    CONFIG_PATH.write_text(payload, encoding="utf-8")


# ---------------------------------------------------------------------------
# First-time setup (interactive)
# ---------------------------------------------------------------------------

def run_first_time_setup() -> TrioConfig:
    """Run interactive agent selection using questionary.

    Returns:
        The created TrioConfig.
    """
    try:
        import questionary
    except ImportError as exc:
        raise RuntimeError(
            "questionary is required for first-time setup. "
            "Install it: pip install questionary"
        ) from exc

    from rich.console import Console

    console = Console()
    console.print(
        "\n[bold cyan]context-trio 에이전트 설정이 필요합니다.[/bold cyan]\n"
    )

    selections: dict[str, AgentConfig] = {}

    role_labels = {
        "plan": "Plan 에이전트를 선택하세요",
        "implement": "Implement 에이전트를 선택하세요",
        "review": "Review 에이전트를 선택하세요",
    }

    for role, label in role_labels.items():
        choices = list(_PRESETS[role].keys())
        default = _DEFAULT_CHOICES[role]

        choice = questionary.select(
            label,
            choices=choices,
            default=default,
        ).ask()

        if choice is None:
            raise KeyboardInterrupt

        agent_cfg = _PRESETS[role][choice].model_copy()

        # If GLM is selected, detect and capture env vars
        if agent_cfg.name == "glm":
            glm_env = _detect_glm_env()
            if glm_env:
                agent_cfg.env_overrides = glm_env
                console.print(
                    f"  [dim]GLM 환경변수 감지됨: {', '.join(glm_env.keys())}[/dim]"
                )

        selections[role] = agent_cfg

    config = TrioConfig(
        architect=selections["plan"],
        implementer=selections["implement"],
        auditor=selections["review"],
    )

    save_config(config)
    console.print(
        "\n[green]설정이 .trio/config.json에 저장되었습니다.[/green]\n"
    )
    return config


def ensure_config() -> TrioConfig:
    """Load existing config or run first-time setup.

    Returns:
        TrioConfig ready to use.
    """
    config = load_config()
    if config is None:
        config = run_first_time_setup()
    return config
