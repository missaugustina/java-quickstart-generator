"""Minimal orchestration for generating one guide part."""

from pathlib import Path

from java_quickstart_generator.models import GenerationRequest, GeneratorConfig
from java_quickstart_generator.roles import BuildsPrompt, RunsAgent, WritesArtifact


def generate_part(
    request: GenerationRequest,
    config: GeneratorConfig,
    prompt_builder: BuildsPrompt,
    agent: RunsAgent,
    writer: WritesArtifact,
) -> Path:
    """Generate and save one part while preserving the agent thread ID."""

    prompt = prompt_builder.build_prompt(request, config)
    response = agent.run_agent(prompt, request.thread_id)
    return writer.write_artifact(request.part, response, config)
