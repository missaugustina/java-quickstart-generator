"""Concrete adapters for prompt building, agent execution, and draft writing."""

from pathlib import Path

from openai_codex import Codex, Sandbox

from quickstart_generator.course_spec import CourseSection, CourseSpec
from quickstart_generator.models import (
    AgentResponse,
    GeneratorConfig,
    ModulePart,
)
from quickstart_generator.prompt_template import PromptTemplate, load_prompt_template


class GenerationError(RuntimeError):
    """Report an expected failure while the SDK runs a generation turn."""


class GuidePromptBuilder:
    """Render section prompts using a loaded Markdown template."""

    def __init__(self, template: PromptTemplate | None = None) -> None:
        self.template = template if template is not None else load_prompt_template()

    def build_section_prompt(
        self, section: CourseSection, spec: CourseSpec, thread_id: str | None
    ) -> str:
        return self.template.render(section, spec, thread_id)


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
    """Write one generated section as Markdown."""

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

        artifact_name = part.output_filename
        if (
            not artifact_name.strip()
            or artifact_name in {".", ".."}
            or "/" in artifact_name
            or "\\" in artifact_name
            or "\x00" in artifact_name
            or Path(artifact_name).suffix != ".md"
        ):
            raise ValueError(f"Invalid output filename: {artifact_name!r}")

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
