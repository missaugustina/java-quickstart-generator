"""Small, immutable values passed through the generation workflow."""

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
