"""Generate a Java quickstart guide one focused part at a time."""

# PSEUDOCODE FOR GENERATED IMPLEMENTATION
#
# PUBLIC EXPORTS
#     GeneratorConfig
#     ModulePart
#     GenerationRequest
#     AgentResponse
#     GenerationOutcome
#     generate_part
#     generate_module
#
# DO NOT EXPORT
#     GuidePromptBuilder
#     CodexAgent
#     MarkdownWriter
#
# Models and workflow functions form the reusable application surface.
# Concrete adapters remain implementation details for the PoC.

from java_quickstart_generator.models import (
    AgentResponse,
    GenerationRequest,
    GeneratorConfig,
    ModulePart,
)

__all__ = [
    "AgentResponse",
    "GenerationRequest",
    "GeneratorConfig",
    "ModulePart",
]
