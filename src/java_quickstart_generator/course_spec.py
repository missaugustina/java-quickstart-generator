"""Load and validate the section structure of a YAML course specification."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml


class _UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects ambiguous mapping keys."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        seen: set[Any] = set()
        for key_node, _ in node.value:
            if key_node.tag == "tag:yaml.org,2002:merge":
                raise yaml.constructor.ConstructorError(
                    None, None, "YAML merge keys (<<) are not supported", key_node.start_mark
                )
            key = cast(str, self.construct_object(key_node, deep=deep))  # pyright: ignore[reportUnknownMemberType]
            try:
                duplicate = key in seen
            except TypeError as error:
                raise yaml.constructor.ConstructorError(
                    None, None, "YAML mapping key is not hashable", key_node.start_mark
                ) from error
            if duplicate:
                raise yaml.constructor.ConstructorError(
                    None, None, f"Duplicate YAML key: {key}", key_node.start_mark
                )
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


@dataclass(frozen=True, slots=True)
class CourseSection:
    id: str
    title: str
    map_location: str
    purpose: str
    topics: tuple[str, ...]
    assignment_connection: str
    activity: str
    layout: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SectionBlock:
    order: int
    name: str
    instruction: str


@dataclass(frozen=True, slots=True)
class CourseSpec:
    source_path: Path
    source_text: str
    sections: tuple[CourseSection, ...]
    required_blocks: tuple[SectionBlock, ...]


def _mapping(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{location} must be a mapping")
    return cast(dict[str, Any], value)


def _text(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{location} must be nonempty text")
    return value.strip()


def _text_list(value: Any, location: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{location} must be a nonempty list")
    return tuple(
        _text(item, f"{location}[{index}]") for index, item in enumerate(cast(list[Any], value))
    )


def load_course_spec(path: Path) -> CourseSpec:
    """Validate the complete course structure without contacting Codex."""

    if not path.is_file():
        raise ValueError(f"Course specification is not a file: {path}")
    source_text = path.read_text(encoding="utf-8")
    if not source_text.strip():
        raise ValueError(f"Course specification is empty: {path}")
    try:
        root = _mapping(yaml.load(source_text, Loader=_UniqueKeyLoader), str(path))
    except yaml.YAMLError as error:
        raise ValueError(f"Invalid YAML in {path}: {error}") from error

    structure = _mapping(root.get("guide_structure"), "guide_structure")
    raw_sections = structure.get("sections")
    if not isinstance(raw_sections, list) or not raw_sections:
        raise ValueError("guide_structure.sections must be a nonempty list")

    sections: list[CourseSection] = []
    seen_ids: set[str] = set()
    seen_folded_ids: set[str] = set()
    for index, raw_section in enumerate(cast(list[Any], raw_sections)):
        section = _mapping(raw_section, f"guide_structure.sections[{index}]")
        section_id = _text(section.get("id"), f"section[{index}].id")
        if (
            not section_id.isascii()
            or not all(character.isalnum() or character in "_-" for character in section_id)
            or section_id in {".", ".."}
        ):
            raise ValueError(f"section[{index}].id has unsafe characters: {section_id}")
        if section_id in seen_ids:
            raise ValueError(f"Duplicate section id: {section_id}")
        if section_id.lower() in seen_folded_ids:
            raise ValueError(f"Section IDs must be unique regardless of case: {section_id}")
        seen_ids.add(section_id)
        seen_folded_ids.add(section_id.lower())
        where = f"section {section_id}"
        sections.append(
            CourseSection(
                id=section_id,
                title=_text(section.get("title"), f"{where}.title"),
                map_location=_text(section.get("map_location"), f"{where}.map_location"),
                purpose=_text(section.get("purpose"), f"{where}.purpose"),
                topics=_text_list(section.get("topics"), f"{where}.topics"),
                assignment_connection=_text(
                    section.get("assignment_connection"), f"{where}.assignment_connection"
                ),
                activity=_text(section.get("activity"), f"{where}.activity"),
                layout=_text_list(section.get("layout"), f"{where}.layout"),
            )
        )

    template = _mapping(root.get("section_template"), "section_template")
    raw_blocks = template.get("required_blocks")
    if not isinstance(raw_blocks, list) or not raw_blocks:
        raise ValueError("section_template.required_blocks must be a nonempty list")
    blocks: list[SectionBlock] = []
    seen_orders: set[int] = set()
    for index, raw_block in enumerate(cast(list[Any], raw_blocks)):
        block = _mapping(raw_block, f"section_template.required_blocks[{index}]")
        order = block.get("order")
        if not isinstance(order, int) or isinstance(order, bool) or order < 1:
            raise ValueError(f"section_template.required_blocks[{index}].order must be positive")
        if order in seen_orders:
            raise ValueError(f"Duplicate section template order: {order}")
        seen_orders.add(order)
        blocks.append(
            SectionBlock(
                order=order,
                name=_text(block.get("name"), f"section_template block {order}.name"),
                instruction=_text(
                    block.get("instruction"), f"section_template block {order}.instruction"
                ),
            )
        )

    return CourseSpec(
        source_path=path,
        source_text=source_text,
        sections=tuple(sections),
        required_blocks=tuple(sorted(blocks, key=lambda block: block.order)),
    )
