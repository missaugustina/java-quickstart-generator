"""Behavioral contracts for replaceable parts of the PoC.

These protocols play the role of small MooseX-style roles: each describes one
behavior without forcing the workflow to inherit from a large base class.
"""

from pathlib import Path
from typing import Protocol

from java_quickstart_generator.models import (
    AgentResponse,
    GenerationRequest,
    GeneratorConfig,
    ModulePart,
)


class BuildsPrompt(Protocol):
    """Build a focused agent prompt for one module part."""

    def build_prompt(
        self,
        request: GenerationRequest,
        config: GeneratorConfig,
    ) -> str: ...


class RunsAgent(Protocol):
    """Run or continue one Codex thread."""

    def run_agent(self, prompt: str, thread_id: str | None) -> AgentResponse: ...


class WritesArtifact(Protocol):
    """Write generated content to its project artifact."""

    def write_artifact(
        self,
        part: ModulePart,
        response: AgentResponse,
        config: GeneratorConfig,
    ) -> Path: ...
