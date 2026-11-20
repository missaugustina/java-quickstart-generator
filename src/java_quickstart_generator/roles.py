"""Behavioral contracts for replaceable parts of the PoC.

These protocols play the role of small MooseX-style roles: each describes one
behavior without forcing the workflow to inherit from a large base class.
"""

from pathlib import Path
from typing import Protocol

from java_quickstart_generator.course_spec import CourseSection, CourseSpec
from java_quickstart_generator.models import (
    AgentResponse,
    GeneratorConfig,
    ModulePart,
)


class RunsAgent(Protocol):
    """Run one prompt in a new or existing agent thread."""

    def run_agent(self, prompt: str, thread_id: str | None) -> AgentResponse: ...


class BuildsSectionPrompt(Protocol):
    """Compose one section turn from a validated YAML specification."""

    def build_section_prompt(
        self, section: CourseSection, spec: CourseSpec, thread_id: str | None
    ) -> str: ...


class WritesArtifact(Protocol):
    """Persist one agent response as a reviewable project artifact."""

    def write_artifact(
        self,
        part: ModulePart,
        response: AgentResponse,
        config: GeneratorConfig,
    ) -> Path: ...
