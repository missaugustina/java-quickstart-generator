"""Load Markdown prompt blocks and substitute course values once."""

from collections import Counter
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from string import Template

from quickstart_generator.course_spec import CourseSection, CourseSpec

_HEADINGS = ("# Initial turn", "# Continuation turn", "# Current section")
_SECTION_FIELDS = {
    "section_id",
    "section_title",
    "source_filename",
    "map_location",
    "purpose",
    "topics",
    "assignment_connection",
    "activity",
    "layout",
    "required_blocks",
}


def _validate_block(text: str, expected: set[str], location: str) -> None:
    if not text.strip():
        raise ValueError(f"{location}: block must not be empty")
    template = Template(text)
    if not template.is_valid():
        raise ValueError(f"{location}: malformed placeholder; use $$ for a literal dollar sign")
    counts: Counter[str] = Counter()
    for match in template.pattern.finditer(text):
        identifier = match.group("named") or match.group("braced")
        if identifier:
            counts[identifier] += 1
    if set(counts) - expected:
        # Do not echo arbitrary input values in diagnostic messages.
        raise ValueError(f"{location}: unknown or misplaced placeholder")
    missing = expected - set(counts)
    if missing:
        raise ValueError(f"{location}: missing required placeholders: {', '.join(sorted(missing))}")
    if any(count != 1 for count in counts.values()):
        raise ValueError(f"{location}: each placeholder must appear exactly once")


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    """Editable Markdown blocks used for one generation turn."""

    initial: str
    continuation: str
    current_section: str

    def __post_init__(self) -> None:
        # Validate direct construction too: callers can inject this value into a
        # builder without going through the file loader.
        self.validate()

    def validate(self, source: str = "Prompt template") -> None:
        """Validate every block, including ones unused by the next turn."""

        for heading, block, expected in (
            (_HEADINGS[0], self.initial, {"course_spec"}),
            (_HEADINGS[1], self.continuation, set[str]()),
            (_HEADINGS[2], self.current_section, _SECTION_FIELDS),
        ):
            _validate_block(block, expected, f"{source}: {heading}")

    def render(self, section: CourseSection, spec: CourseSpec, thread_id: str | None) -> str:
        """Substitute each selected block once, leaving inserted text literal."""

        values = {
            "course_spec": spec.source_text.strip(),
            "section_id": section.id,
            "section_title": section.title,
            "source_filename": spec.source_path.name,
            "map_location": section.map_location,
            "purpose": section.purpose,
            "topics": "\n".join(f"- {topic}" for topic in section.topics),
            "assignment_connection": section.assignment_connection,
            "activity": section.activity,
            "layout": "\n".join(f"- {item}" for item in section.layout),
            "required_blocks": "\n".join(
                f"{block.order}. {block.name}: {block.instruction}"
                for block in spec.required_blocks
            ),
        }
        turn = self.initial if thread_id is None else self.continuation
        # Never substitute the combined result: YAML values may themselves contain
        # dollars or placeholder-looking text that must remain unchanged.
        return "\n\n".join(
            Template(block).substitute(values) for block in (turn, self.current_section)
        )


def load_prompt_template(path: Path | None = None) -> PromptTemplate:
    """Read UTF-8 Markdown with the three reserved headings in order."""

    try:
        source = (
            path
            if path is not None
            else files("quickstart_generator").joinpath("templates/course_prompt.md")
        )
        text = source.read_text(encoding="utf-8")
    except UnicodeError as error:
        raise ValueError(f"{path}: template must be valid UTF-8") from error
    except OSError as error:
        raise ValueError(f"{path}: could not read template file") from error
    if not text.strip():
        raise ValueError(f"{path}: template must not be empty")
    lines = text.splitlines()
    positions = [index for index, line in enumerate(lines) if line in _HEADINGS]
    if [lines[index] for index in positions] != list(_HEADINGS):
        raise ValueError(f"{path}: expected each reserved prompt heading once, in order")
    if any(line.strip() for line in lines[: positions[0]]):
        raise ValueError(f"{path}: content must begin with # Initial turn")
    first, second, third = positions
    try:
        template = PromptTemplate(
            initial="\n".join(lines[first + 1 : second]).strip(),
            continuation="\n".join(lines[second + 1 : third]).strip(),
            current_section="\n".join(lines[third + 1 :]).strip(),
        )
    except ValueError as error:
        raise ValueError(f"{path}: {error}") from error
    return template
