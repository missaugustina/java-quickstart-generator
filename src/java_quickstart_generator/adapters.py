"""Placeholders for the three concrete PoC roles.

Implementation is intentionally deferred. These names establish the expected
boundaries without committing the PoC to a larger framework.
"""

# PSEUDOCODE FOR GENERATED IMPLEMENTATION
#
# GuidePromptBuilder composes the stable guide specification with one focused
# module-part prompt. CodexAgent starts or resumes one SDK thread. MarkdownWriter
# persists one reviewable draft without overwriting existing work.

from pathlib import Path

from java_quickstart_generator.models import (
    AgentResponse,
    GenerationRequest,
    GeneratorConfig,
    ModulePart,
)


class GuidePromptBuilder:
    """Build prompts from the guide specification and the current request."""

    def build_prompt(
        self,
        request: GenerationRequest,
        config: GeneratorConfig,
    ) -> str:
        # PSEUDOCODE
        # part_prompt = read request.part.prompt_path as UTF-8
        #
        # IF request.thread_id is absent
        #     guide_spec = read config.guide_spec as UTF-8
        #
        #     RETURN concatenate:
        #         initial agent contract
        #         complete guide specification
        #         current module identity
        #         current part identity
        #         part prompt
        #         output boundary
        #         handoff requirement
        #
        # RETURN concatenate:
        #     invariant continuation capsule
        #     current module identity
        #     current part identity
        #     part prompt
        #     output boundary
        #     handoff requirement
        #
        # CONTINUATION CAPSULE
        #     Continue the same Java Quickstart guide.
        #     Preserve territory-map IDs and approved terminology.
        #     Keep standard Java distinct from Veeva-specific behavior.
        #     Keep every visual equivalent to a text structure.
        #     Generate only the requested part.
        raise NotImplementedError


class CodexAgent:
    """Run prompts through the OpenAI Codex SDK."""

    def run_agent(self, prompt: str, thread_id: str | None) -> AgentResponse:
        # PSEUDOCODE
        # open Codex SDK client
        #
        # IF thread_id exists
        #     thread = resume thread identified by thread_id
        # ELSE
        #     thread = start thread with read-only sandbox
        #     use the user's configured default model
        #
        # result = run prompt as one agent turn
        #
        # IF result has no final response
        #     RAISE generation error
        #
        # IF thread has no ID
        #     RAISE generation error
        #
        # RETURN AgentResponse
        #     content = result final response
        #     thread_id = thread ID
        raise NotImplementedError


class MarkdownWriter:
    """Write one generated module part as Markdown."""

    def write_artifact(
        self,
        part: ModulePart,
        response: AgentResponse,
        config: GeneratorConfig,
    ) -> Path:
        # PSEUDOCODE
        # module_directory = config.drafts_directory / part.module_id
        # artifact_path = module_directory / part.prompt_path.filename
        #
        # IF artifact_path already exists
        #     RAISE file-exists error
        #
        # create module_directory and missing parents
        # write response.content to artifact_path as UTF-8
        # RETURN artifact_path
        #
        # FAILURE POLICY
        #     Do not retry automatically.
        #     Do not overwrite an existing draft.
        #     Do not write an empty response.
        raise NotImplementedError
