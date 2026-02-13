"""Pipeline engine for the Triad Orchestration System.

Orchestrates the Plan -> Implement -> Review cycle by invoking
external agent CLIs in sequence and managing artifacts.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from .agents import (
    get_git_diff,
    git_commit_and_push,
    invoke_architect,
    invoke_auditor,
    invoke_implementer,
)
from .config import TrioConfig
from .context import ContextManager
from .exceptions import AgentError
from .prompts import build_implement_prompt, build_plan_prompt, build_review_prompt
from .schemas import AgentRole, Phase

TRIO_DIR = Path(".trio")
PLAN_FILE = TRIO_DIR / "plan.md"
IMPL_OUTPUT_FILE = TRIO_DIR / "impl_output.txt"
REVIEW_FILE = TRIO_DIR / "review.txt"
HOOKS_SRC = Path(__file__).resolve().parent.parent.parent / ".claude" / "hooks"
HOOKS_DST = Path(".claude") / "hooks"

MAX_RETRIES = 3


class TaskOrchestrator:
    """Executes the full Plan -> Implement -> Review pipeline.

    Args:
        config: Agent configuration.
        ctx_manager: Context manager for CONTEXT.json.
        console: Rich console for output.
    """

    def __init__(
        self,
        config: TrioConfig,
        ctx_manager: ContextManager,
        console: Console,
        *,
        no_commit: bool = False,
    ) -> None:
        self.config = config
        self.ctx_mgr = ctx_manager
        self.console = console
        self.no_commit = no_commit

    def execute(self, description: str) -> bool:
        """Run the full orchestration pipeline.

        Args:
            description: User's task description.

        Returns:
            True if the task was approved, False otherwise.
        """
        TRIO_DIR.mkdir(parents=True, exist_ok=True)

        for attempt in range(1, MAX_RETRIES + 1):
            if attempt > 1:
                self.console.print(
                    f"\n[yellow]Retry {attempt}/{MAX_RETRIES} — "
                    f"incorporating review feedback...[/yellow]\n"
                )

            # Phase 1: Plan
            plan_text = self._phase_plan(description)
            if plan_text is None:
                return False

            # Phase 2: Implement
            impl_output = self._phase_implement(plan_text)
            if impl_output is None:
                return False

            # Phase 3: Review
            verdict, review_text = self._phase_review(plan_text)

            if verdict == "approved":
                self._on_approved(description)
                return True

            # Rejected — append feedback to description for next attempt
            self.console.print(
                Panel(
                    review_text[:500],
                    title="[bold red]Review: REJECTED[/bold red]",
                )
            )
            description = (
                f"{description}\n\n"
                f"## Previous Review Feedback (attempt {attempt})\n"
                f"{review_text}"
            )
            self._update_phase(Phase.REJECTED)
            self._update_phase(Phase.PLANNING)

        self.console.print(
            f"[red]Task failed after {MAX_RETRIES} attempts.[/red]"
        )
        return False

    # ------------------------------------------------------------------
    # Pipeline phases
    # ------------------------------------------------------------------

    def _phase_plan(self, description: str) -> str | None:
        """Execute the planning phase.

        Returns:
            Plan text, or None on failure.
        """
        self.console.print(
            "\n[bold magenta]Phase 1: Planning[/bold magenta]"
        )
        self._update_phase(Phase.PLANNING)

        ctx = self.ctx_mgr.load()
        prompt = build_plan_prompt(description, ctx)

        try:
            plan_text = invoke_architect(prompt, self.config.architect)
        except AgentError as exc:
            self.console.print(f"[red]Architect failed:[/red] {exc}")
            return None

        # Save plan artifact
        PLAN_FILE.write_text(plan_text, encoding="utf-8")
        self.console.print(f"  [green]Plan saved to {PLAN_FILE}[/green]")

        self.ctx_mgr.add_reasoning_log(
            agent=AgentRole.ARCHITECT,
            action="plan_generated",
            summary=f"Generated plan for: {description[:80]}",
        )

        self._update_phase(Phase.IMPLEMENTATION)
        return plan_text

    def _phase_implement(self, plan_text: str) -> str | None:
        """Execute the implementation phase.

        Returns:
            Implementation output, or None on failure.
        """
        self.console.print(
            "\n[bold green]Phase 2: Implementation[/bold green]"
        )

        self._install_hooks()

        ctx = self.ctx_mgr.load()
        prompt = build_implement_prompt(plan_text, ctx)

        try:
            impl_output = invoke_implementer(prompt, self.config.implementer)
        except AgentError as exc:
            self.console.print(f"[red]Implementer failed:[/red] {exc}")
            return None

        # Save implementation output
        IMPL_OUTPUT_FILE.write_text(impl_output, encoding="utf-8")
        self.console.print(
            f"  [green]Implementation output saved to {IMPL_OUTPUT_FILE}[/green]"
        )

        self.ctx_mgr.add_reasoning_log(
            agent=AgentRole.IMPLEMENTER,
            action="implementation_completed",
            summary="Implementation phase completed",
        )

        self._update_phase(Phase.REVIEW)
        return impl_output

    def _phase_review(self, plan_text: str) -> tuple[str, str]:
        """Execute the review phase.

        Returns:
            Tuple of (verdict, review_text).
            verdict is "approved" or "rejected".
        """
        self.console.print(
            "\n[bold yellow]Phase 3: Review[/bold yellow]"
        )

        diff_text = get_git_diff()
        if not diff_text:
            self.console.print(
                "  [dim]No git diff detected, using implementation output.[/dim]"
            )
            diff_text = IMPL_OUTPUT_FILE.read_text(encoding="utf-8") if IMPL_OUTPUT_FILE.exists() else "(no changes)"

        ctx = self.ctx_mgr.load()
        prompt = build_review_prompt(plan_text, diff_text, ctx)

        try:
            review_text = invoke_auditor(prompt, self.config.auditor)
        except AgentError as exc:
            self.console.print(f"[red]Auditor failed:[/red] {exc}")
            return "rejected", str(exc)

        # Save review output
        REVIEW_FILE.write_text(review_text, encoding="utf-8")

        # Parse verdict
        verdict = self._parse_verdict(review_text)

        self.ctx_mgr.add_reasoning_log(
            agent=AgentRole.AUDITOR,
            action="review_completed",
            summary=f"Review verdict: {verdict}",
        )

        return verdict, review_text

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _on_approved(self, description: str) -> None:
        """Handle approved verdict: update phase, optionally commit & push."""
        self._update_phase(Phase.APPROVED)
        self.console.print(
            Panel(
                "[bold green]APPROVED[/bold green]",
                title="Review Result",
            )
        )

        if not self.no_commit and self.config.auto_commit:
            commit_msg = f"feat: {description[:72]}\n\nAutomated by context-trio orchestrator."
            try:
                git_commit_and_push(
                    commit_msg, push=self.config.auto_push
                )
                self.console.print("[green]Changes committed and pushed.[/green]")
            except Exception as exc:
                self.console.print(
                    f"[yellow]Git commit/push failed:[/yellow] {exc}"
                )

    def _update_phase(self, target: Phase) -> None:
        """Safely transition to a new phase."""
        ctx = self.ctx_mgr.load()
        current = ctx.global_phase

        # Map the required agent for each transition
        agent_map = {
            Phase.PLANNING: AgentRole.ARCHITECT,
            Phase.IMPLEMENTATION: AgentRole.ARCHITECT,
            Phase.REVIEW: AgentRole.IMPLEMENTER,
            Phase.APPROVED: AgentRole.AUDITOR,
            Phase.REJECTED: AgentRole.AUDITOR,
        }
        agent = agent_map.get(target, AgentRole.ARCHITECT)

        try:
            self.ctx_mgr.update_phase(target, agent)
        except Exception:
            # If transition is invalid (e.g. already in target phase), skip
            pass

    def _install_hooks(self) -> None:
        """Copy hook scripts to .claude/hooks/ if they exist."""
        if not HOOKS_SRC.is_dir():
            return

        HOOKS_DST.mkdir(parents=True, exist_ok=True)
        for script in HOOKS_SRC.glob("*.sh"):
            dst = HOOKS_DST / script.name
            if not dst.exists():
                shutil.copy2(script, dst)

    @staticmethod
    def _parse_verdict(review_text: str) -> str:
        """Extract approved/rejected verdict from review output.

        Looks for "VERDICT: APPROVED" or "VERDICT: REJECTED" patterns,
        or falls back to keyword detection.

        Args:
            review_text: The auditor's review output.

        Returns:
            "approved" or "rejected".
        """
        upper = review_text.upper()

        # Check for explicit verdict line
        for line in upper.split("\n"):
            line = line.strip()
            if line.startswith("VERDICT:"):
                if "APPROVED" in line:
                    return "approved"
                if "REJECTED" in line:
                    return "rejected"

        # Fallback: keyword detection
        if "APPROVED" in upper and "REJECTED" not in upper:
            return "approved"
        if "REJECTED" in upper:
            return "rejected"

        # Default to approved if ambiguous
        return "approved"
