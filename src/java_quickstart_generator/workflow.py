"""Minimal orchestration for generating ordered guide modules."""

from collections.abc import Sequence
from pathlib import Path

from java_quickstart_generator.course_spec import load_course_spec
from java_quickstart_generator.models import (
    GenerationOutcome,
    GeneratorConfig,
    ModulePart,
)
from java_quickstart_generator.roles import (
    BuildsSectionPrompt,
    RunsAgent,
    WritesArtifact,
)


def generate_yaml_course(
    section_ids: Sequence[str],
    config: GeneratorConfig,
    prompt_builder: BuildsSectionPrompt,
    agent: RunsAgent,
    writer: WritesArtifact,
) -> list[GenerationOutcome]:
    """Generate one turn per YAML section in a single course thread."""

    spec = load_course_spec(config.guide_spec)
    by_id = {section.id: section for section in spec.sections}
    if len(section_ids) != len(set(section_ids)):
        raise ValueError("Requested section IDs must not repeat.")
    for section_id in section_ids:
        if section_id not in by_id:
            raise ValueError(f"Unknown section ID: {section_id}")
    sections = [by_id[section_id] for section_id in section_ids] if section_ids else spec.sections

    # Preflight the complete run before spending a Codex turn. The writer still
    # uses exclusive creation to protect against files created after this check.
    drafts_root = config.drafts_directory.resolve()
    planned_targets: dict[Path, str] = {}
    for section in sections:
        target = config.drafts_directory / section.id / "01-section.md"
        resolved_target = target.resolve()
        if not resolved_target.is_relative_to(drafts_root):
            raise ValueError(f"Artifact path escapes drafts directory: {target}")
        previous_section = planned_targets.get(resolved_target)
        if previous_section is not None:
            raise ValueError(
                f"Sections {previous_section} and {section.id} share draft destination: {target}"
            )
        planned_targets[resolved_target] = section.id
        for ancestor in target.parents:
            if ancestor.is_symlink() and not ancestor.exists():
                raise ValueError(f"Broken directory symlink blocks draft: {ancestor}")
            if ancestor.exists() and not ancestor.is_dir():
                raise ValueError(f"File blocks draft directory: {ancestor}")
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"Draft already exists: {target}")

    outcomes: list[GenerationOutcome] = []
    thread_id: str | None = None
    for section in sections:
        prompt = prompt_builder.build_section_prompt(section, spec, thread_id)
        response = agent.run_agent(prompt, thread_id)
        if not response.content.strip():
            raise ValueError("Agent returned an empty response.")
        if not response.thread_id.strip():
            raise ValueError("Agent returned no Codex thread ID.")
        if thread_id is not None and response.thread_id != thread_id:
            raise ValueError("Agent returned a different Codex thread ID during continuation.")
        part = ModulePart(section.id, spec.source_path, section.title)
        artifact_path = writer.write_artifact(part, response, config)
        outcomes.append(GenerationOutcome(part, artifact_path, response.thread_id))
        thread_id = response.thread_id
    return outcomes
