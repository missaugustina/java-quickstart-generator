"""Concrete adapters for prompt building, agent execution, and draft writing."""

from pathlib import Path

from openai_codex import Codex, Sandbox

from java_quickstart_generator.models import (
    AgentResponse,
    GenerationRequest,
    GeneratorConfig,
    ModulePart,
)


class GenerationError(RuntimeError):
    """Report an expected failure while the SDK runs a generation turn."""


class GuidePromptBuilder:
    """Build prompts from the guide specification and the current request."""

    def build_prompt(
        self,
        request: GenerationRequest,
        config: GeneratorConfig,
    ) -> str:
        instruction = request.instruction.strip()
        if not instruction:
            raise ValueError("Part instruction must not be empty.")

        part_prompt = f"""## Current module part

Module ID: {request.part.module_id}
Part title: {request.part.title}
Prompt file: {request.part.prompt_path.name}

## Part instruction

{instruction}

## Output boundary

- Return only the requested part as polished Markdown.
- Do not generate, summarize, or revise other guide parts.
- Do not include analysis, a preface, or a code fence around the entire response.
- Maintain terminology and structural continuity with the guide context.
"""

        if request.thread_id is not None:
            return f"""# Continuation contract

Continue the same Java Quickstart guide using the context already established in this thread.

- Preserve established territory-map IDs and approved terminology.
- Keep standard Java concepts distinct from Veeva-specific behavior.
- Give every visual a one-to-one text-based logical equivalent.
- Maintain continuity with previously generated parts.
- Generate only the requested part.

{part_prompt}"""

        if not config.guide_spec.exists():
            raise FileNotFoundError(f"Guide specification not found: {config.guide_spec}")
        if not config.guide_spec.is_file():
            raise ValueError(f"Guide specification is not a file: {config.guide_spec}")

        guide_spec = config.guide_spec.read_text(encoding="utf-8").strip()
        if not guide_spec:
            raise ValueError(f"Guide specification is empty: {config.guide_spec}")

        return f"""# Initial generation contract

Create one bounded part of the Java Quickstart guide. Treat the complete guide specification
below as the authoritative source for audience, structure, terminology, and design constraints.

## Complete guide specification

{guide_spec}

{part_prompt}"""


class CodexAgent:
    """Run prompts through the OpenAI Codex SDK."""

    def __init__(self, model: str | None = None) -> None:
        if model is not None and not model.strip():
            raise ValueError("Model must not be empty when provided.")
        self.model = model

    def run_agent(self, prompt: str, thread_id: str | None) -> AgentResponse:
        if not prompt.strip():
            raise ValueError("Agent prompt must not be empty.")

        with Codex() as codex:
            if thread_id is None:
                thread = codex.thread_start(
                    model=self.model,
                    sandbox=Sandbox.read_only,
                )
            else:
                thread = codex.thread_resume(thread_id)
                if not thread.id or not thread.id.strip():
                    raise ValueError("Codex resumed a thread with no thread ID.")
                if thread.id != thread_id:
                    raise ValueError("Codex resumed a different Codex thread ID.")

            try:
                result = thread.run(prompt)
            except RuntimeError as error:
                detail = str(error).strip()
                message = "Codex turn failed." if not detail else f"Codex turn failed: {detail}"
                raise GenerationError(message) from error
            if result.final_response is None or not result.final_response.strip():
                raise ValueError("Codex returned an empty final response.")
            if not thread.id or not thread.id.strip():
                raise ValueError("Codex returned no thread ID.")

            return AgentResponse(
                content=result.final_response,
                thread_id=thread.id,
            )


class MarkdownWriter:
    """Write one generated module part as Markdown."""

    def write_artifact(
        self,
        part: ModulePart,
        response: AgentResponse,
        config: GeneratorConfig,
    ) -> Path:
        if not response.content.strip():
            raise ValueError("Artifact content must not be empty.")
        if not part.module_id.strip():
            raise ValueError("Module ID must not be empty.")

        artifact_name = part.prompt_path.name
        if not artifact_name or artifact_name in {".", ".."}:
            raise ValueError(f"Prompt path has no valid filename: {part.prompt_path}")

        artifact_path = config.drafts_directory / part.module_id / artifact_name
        drafts_root = config.drafts_directory.resolve()
        resolved_artifact_path = artifact_path.resolve()
        if not resolved_artifact_path.is_relative_to(drafts_root):
            raise ValueError(f"Artifact path escapes drafts directory: {artifact_path}")

        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_created = False
        try:
            with artifact_path.open("x", encoding="utf-8") as artifact_file:
                artifact_created = True
                artifact_file.write(response.content)
        except FileExistsError:
            raise
        except Exception:
            if artifact_created:
                artifact_path.unlink(missing_ok=True)
            raise

        return artifact_path
