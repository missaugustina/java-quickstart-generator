"""Placeholders for the three concrete PoC roles.

Implementation is intentionally deferred. These names establish the expected
boundaries without committing the PoC to a larger framework.
"""

from pathlib import Path

from java_quickstart_generator.models import (
    AgentResponse,
    GenerationRequest,
    GeneratorConfig,
    ModulePart,
)


class YamlPromptBuilder:
    """Build prompts from the guide specification and the current request."""

    def build_prompt(
        self,
        request: GenerationRequest,
        config: GeneratorConfig,
    ) -> str:
        raise NotImplementedError


class CodexAgent:
    """Run prompts through the OpenAI Codex SDK."""

    def run_agent(self, prompt: str, thread_id: str | None) -> AgentResponse:
        raise NotImplementedError


class MarkdownWriter:
    """Write one generated module part as Markdown."""

    def write_artifact(
        self,
        part: ModulePart,
        response: AgentResponse,
        config: GeneratorConfig,
    ) -> Path:
        raise NotImplementedError
