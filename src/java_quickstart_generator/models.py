"""Small, immutable values passed through the generation workflow."""

# PSEUDOCODE FOR GENERATED IMPLEMENTATION
#
# DATA GeneratorConfig
#     guide_spec: Path
#     prompts_directory: Path
#     drafts_directory: Path
#
# DATA ModulePart
#     module_id: String
#     prompt_path: Path
#     title: String
#
# DATA GenerationRequest
#     part: ModulePart
#     instruction: String
#     thread_id: Optional String
#
# DATA AgentResponse
#     content: String
#     thread_id: String
#
# DATA GenerationOutcome
#     part: ModulePart
#     artifact_path: Path
#     thread_id: String
#
# CONSTRAINTS
#     Keep models frozen and slot-based.
#     Models hold data and identity only.
#     Models do not read files, call Codex, or write artifacts.
#     Do not add Course, Guide, Workflow, Session, or plugin models yet.

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class GeneratorConfig:
    """Project paths shared by one generation run."""

    guide_spec: Path
    output_directory: Path


@dataclass(frozen=True, slots=True)
class ModulePart:
    """Identity and display information for one bounded guide part."""

    module_id: str
    part_id: str
    title: str


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """Input needed to generate one part in an existing or new agent thread."""

    part: ModulePart
    instruction: str
    thread_id: str | None = None


@dataclass(frozen=True, slots=True)
class AgentResponse:
    """Text and thread identity returned by the agent role."""

    content: str
    thread_id: str


# GENERATED CODE WILL ADD:
#
# @dataclass(frozen=True, slots=True)
# class GenerationOutcome:
#     part: ModulePart
#     artifact_path: Path
#     thread_id: str
