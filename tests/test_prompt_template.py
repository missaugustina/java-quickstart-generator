"""Offline checks for literal, single-pass Markdown template rendering."""

from dataclasses import replace
from pathlib import Path

import pytest

from quickstart_generator.course_spec import CourseSection, CourseSpec, SectionBlock
from quickstart_generator.prompt_template import PromptTemplate, load_prompt_template


def course() -> tuple[CourseSection, CourseSpec]:
    section = CourseSection(
        "SEC-01",
        "Title",
        "MAP-1",
        "$section_id and ${unknown}",
        ("One", "Two"),
        "Apply",
        "Trace",
        ("Example",),
    )
    spec = CourseSpec(
        Path("private/course.yaml"),
        "context: $purpose {literal}",
        (section,),
        (SectionBlock(1, "Location", "Find it"),),
    )
    return section, spec


def test_load_and_render_bundled_template() -> None:
    path = Path(__file__).parents[1] / "src/quickstart_generator/templates/course_prompt.md"
    template = load_prompt_template(path)
    section, spec = course()
    first = template.render(section, spec, None)
    later = template.render(section, spec, "thread")
    assert spec.source_text in first
    assert spec.source_text not in later
    for prompt in (first, later):
        assert "$section_id and ${unknown}" in prompt
        assert "Source file: course.yaml" in prompt
        assert "private/" not in prompt
        assert "- One\n- Two" in prompt
        assert "1. Location: Find it" in prompt
        assert prompt.count("## Current course section") == 1


def test_custom_text_and_literal_dollars() -> None:
    section, spec = course()
    template = replace(load_prompt_template(), initial="Custom $$ instructions\n$course_spec")
    rendered = template.render(section, spec, None)
    assert rendered.startswith("Custom $ instructions\n" + spec.source_text)
    assert "$section_id and ${unknown}" in rendered


def test_unknown_template_placeholder_is_not_silently_retained() -> None:
    with pytest.raises(ValueError, match="unknown or misplaced"):
        replace(load_prompt_template(), initial="$unknown")


def test_direct_construction_cannot_bypass_continuation_validation() -> None:
    template = load_prompt_template()
    with pytest.raises(ValueError, match="Continuation turn: malformed placeholder"):
        PromptTemplate(template.initial, "Bad $", template.current_section)


def test_loader_rejects_missing_headings(tmp_path: Path) -> None:
    path = tmp_path / "bad.md"
    path.write_text("# Initial turn\nOnly one block", encoding="utf-8")
    with pytest.raises(ValueError, match="reserved prompt heading"):
        load_prompt_template(path)


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("$course_spec", "", "missing required"),
        ("$course_spec", "$course_spec ${course_spec}", "exactly once"),
        ("$topics", "$unknown", "unknown or misplaced"),
        ("$topics", "${topics", "malformed placeholder"),
        ("$topics", "$", "malformed placeholder"),
        ("$topics", "$course_spec", "unknown or misplaced"),
        ("# Continuation turn", "# Continuation turn\n$course_spec", "unknown or misplaced"),
        ("# Continuation turn", "# Continuation turn\n$section_id", "unknown or misplaced"),
        ("# Current section", "# Current section\n# Current section", "reserved prompt heading"),
        ("# Initial turn", "# Changed heading", "reserved prompt heading"),
    ],
)
def test_invalid_template_fails_during_loading(
    tmp_path: Path, old: str, new: str, message: str
) -> None:
    bundled = Path(__file__).parents[1] / "src/quickstart_generator/templates/course_prompt.md"
    path = tmp_path / "custom.md"
    path.write_text(bundled.read_text().replace(old, new), encoding="utf-8")
    with pytest.raises(ValueError, match=message) as error:
        load_prompt_template(path)
    assert str(path) in str(error.value)


@pytest.mark.parametrize("content", [b"", b"  \n", b"\xff"])
def test_loader_rejects_empty_or_non_utf8(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "custom.md"
    path.write_bytes(content)
    with pytest.raises(ValueError, match="empty|UTF-8"):
        load_prompt_template(path)


def test_loader_rejects_unreadable_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="could not read"):
        load_prompt_template(tmp_path / "missing.md")


def test_empty_continuation_rejected_before_render(tmp_path: Path) -> None:
    bundled = Path(__file__).parents[1] / "src/quickstart_generator/templates/course_prompt.md"
    text = bundled.read_text()
    initial = text.split("# Continuation turn")[0]
    current = text.split("# Current section")[1]
    path = tmp_path / "custom.md"
    path.write_text(initial + "# Continuation turn\n\n# Current section" + current)
    with pytest.raises(ValueError, match="Continuation turn: block must not be empty"):
        load_prompt_template(path)


def test_braced_placeholders_and_escaped_dollars_are_valid(tmp_path: Path) -> None:
    bundled = Path(__file__).parents[1] / "src/quickstart_generator/templates/course_prompt.md"
    path = tmp_path / "custom.md"
    path.write_text(bundled.read_text().replace("$topics", "${topics}") + "\nPrice: $$5\n")
    section, spec = course()
    assert "Price: $5" in load_prompt_template(path).render(section, spec, None)
