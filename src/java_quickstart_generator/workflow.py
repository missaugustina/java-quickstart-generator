"""Minimal orchestration for generating ordered guide modules."""

from collections.abc import Sequence
from pathlib import Path

from java_quickstart_generator.models import (
    GenerationOutcome,
    GenerationRequest,
    GeneratorConfig,
    ModulePart,
)
from java_quickstart_generator.roles import BuildsPrompt, RunsAgent, WritesArtifact


def _resolve_module_prompt_directory(module_id: str, prompts_directory: Path) -> Path:
    """Return a module directory only when it stays beneath the prompts root."""

    module_path = Path(module_id)
    if module_path.is_absolute():
        raise ValueError("Module ID must be a relative path.")
    if ".." in module_path.parts:
        raise ValueError("Module ID must not contain parent-directory traversal.")

    prompts_root = prompts_directory.resolve()
    module_prompt_directory = (prompts_root / module_path).resolve()
    if module_prompt_directory == prompts_root or not module_prompt_directory.is_relative_to(
        prompts_root
    ):
        raise ValueError("Module prompt directory must remain inside the prompts directory.")

    return module_prompt_directory


def generate_part(
    request: GenerationRequest,
    config: GeneratorConfig,
    prompt_builder: BuildsPrompt,
    agent: RunsAgent,
    writer: WritesArtifact,
) -> GenerationOutcome:
    """Generate and save one part while preserving the agent thread ID."""

    prompt = prompt_builder.build_prompt(request, config)
    response = agent.run_agent(prompt, request.thread_id)

    if not response.content.strip():
        raise ValueError("Agent returned an empty response.")
    if not response.thread_id.strip():
        raise ValueError("Agent returned no Codex thread ID.")
    if request.thread_id is not None and response.thread_id != request.thread_id:
        raise ValueError("Agent returned a different Codex thread ID during continuation.")

    artifact_path = writer.write_artifact(request.part, response, config)
    return GenerationOutcome(
        part=request.part,
        artifact_path=artifact_path,
        thread_id=response.thread_id,
    )


def generate_module(
    module_id: str,
    config: GeneratorConfig,
    prompt_builder: BuildsPrompt,
    agent: RunsAgent,
    writer: WritesArtifact,
    *,
    thread_id: str | None = None,
) -> list[GenerationOutcome]:
    """Generate a module from its ordered Markdown prompt files."""

    if not module_id.strip():
        raise ValueError("Module ID must not be empty.")

    module_prompt_directory = _resolve_module_prompt_directory(
        module_id,
        config.prompts_directory,
    )
    if not module_prompt_directory.exists():
        raise FileNotFoundError(f"Module prompt directory not found: {module_prompt_directory}")
    if not module_prompt_directory.is_dir():
        raise NotADirectoryError(
            f"Module prompt path is not a directory: {module_prompt_directory}"
        )

    prompt_files: list[Path] = []
    for path in module_prompt_directory.iterdir():
        if path.suffix.lower() != ".md":
            continue
        if path.is_symlink():
            raise ValueError(f"Markdown prompt must not be a symbolic link: {path}")
        if path.is_file():
            prompt_path = path.resolve()
            if not prompt_path.is_relative_to(module_prompt_directory):
                raise ValueError(f"Markdown prompt must remain inside its module directory: {path}")
            prompt_files.append(prompt_path)

    prompt_files.sort(key=lambda path: path.name)
    if not prompt_files:
        raise ValueError(f"Module contains no Markdown prompt files: {module_prompt_directory}")

    outcomes: list[GenerationOutcome] = []
    for prompt_file in prompt_files:
        instruction = prompt_file.read_text(encoding="utf-8")
        if not instruction.strip():
            raise ValueError(f"Prompt file is empty: {prompt_file}")

        part = ModulePart(
            module_id=module_id,
            prompt_path=prompt_file,
            title=prompt_file.stem.replace("-", " ").replace("_", " ").strip().title(),
        )
        request = GenerationRequest(
            part=part,
            instruction=instruction,
            thread_id=thread_id,
        )
        outcome = generate_part(request, config, prompt_builder, agent, writer)
        outcomes.append(outcome)
        thread_id = outcome.thread_id

    return outcomes


def generate_course(
    module_ids: Sequence[str],
    config: GeneratorConfig,
    prompt_builder: BuildsPrompt,
    agent: RunsAgent,
    writer: WritesArtifact,
) -> list[GenerationOutcome]:
    """Generate ordered modules in one continuous Codex thread."""

    if not module_ids:
        raise ValueError("Course generation requires at least one module ID.")

    outcomes: list[GenerationOutcome] = []
    thread_id: str | None = None
    for module_id in module_ids:
        module_outcomes = generate_module(
            module_id,
            config,
            prompt_builder,
            agent,
            writer,
            thread_id=thread_id,
        )
        outcomes.extend(module_outcomes)
        thread_id = module_outcomes[-1].thread_id

    return outcomes
