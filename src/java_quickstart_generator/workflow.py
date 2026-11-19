"""Minimal orchestration for generating one guide part."""

# PSEUDOCODE FOR GENERATED IMPLEMENTATION
#
# generate_part is the primitive operation for one agent turn.
# generate_module discovers ordered prompt files and calls generate_part once
# for each file while carrying the returned Codex thread ID forward.

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

    # PSEUDOCODE
    # prompt = prompt_builder.build_prompt(request, config)
    # response = agent.run_agent(prompt, request.thread_id)
    # artifact_path = writer.write_artifact(request.part, response, config)
    #
    # RETURN GenerationOutcome
    #     part = request.part
    #     artifact_path = artifact_path
    #     thread_id = response.thread_id
    prompt = prompt_builder.build_prompt(request, config)
    response = agent.run_agent(prompt, request.thread_id)
    return writer.write_artifact(request.part, response, config)


# GENERATED CODE WILL ADD generate_module WITH THIS PSEUDOCODE:
#
# FUNCTION generate_module(
#     module_id,
#     config,
#     prompt_builder,
#     agent,
#     writer
# ) -> List of GenerationOutcome
#
#     module_prompt_directory = config.prompts_directory / module_id
#
#     IF module_prompt_directory does not exist
#         RAISE configuration error
#
#     prompt_files = Markdown files in module_prompt_directory
#     sort prompt_files by filename
#
#     IF prompt_files is empty
#         RAISE configuration error
#
#     outcomes = empty list
#     thread_id = absent
#
#     FOR each prompt_file in prompt_files
#         part = ModulePart
#             module_id = module_id
#             prompt_path = prompt_file
#             title = title derived from prompt filename
#
#         request = GenerationRequest
#             part = part
#             instruction = read prompt_file as UTF-8
#             thread_id = thread_id
#
#         outcome = generate_part(...)
#         append outcome to outcomes
#         thread_id = outcome.thread_id
#
#     RETURN outcomes
#
# INVARIANTS
#     First part starts a new Codex thread.
#     Every later part resumes the returned thread.
#     Prompt filename order is execution order.
#     One successful part produces one draft.
#     Any exception stops later parts from running.
#     Successfully written earlier drafts remain available for review.
