"""Command-line argument parsing for the guide generator."""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from openai_codex import CodexError

from java_quickstart_generator.adapters import (
    CodexAgent,
    GenerationError,
    GuidePromptBuilder,
    MarkdownWriter,
)
from java_quickstart_generator.models import GeneratorConfig
from java_quickstart_generator.prompt_template import load_prompt_template
from java_quickstart_generator.workflow import generate_yaml_course

DEFAULT_GUIDE_SPEC = Path("prompts/guide_spec.yaml")
DEFAULT_DRAFTS_DIRECTORY = Path("drafts")


@dataclass(frozen=True, slots=True)
class CliArguments:
    """Typed values produced by command-line parsing."""

    module_ids: tuple[str, ...]
    config: GeneratorConfig
    model: str | None


def non_empty_value(value: str) -> str:
    """Return a trimmed CLI value or report a normal argument error."""

    trimmed_value = value.strip()
    if not trimmed_value:
        raise argparse.ArgumentTypeError("value must not be empty")
    return trimmed_value


def build_parser() -> argparse.ArgumentParser:
    """Create the parser without reading arguments or running generation."""

    parser = argparse.ArgumentParser(
        prog="java-quickstart-generator",
        description=(
            "Generate one or more Java Quickstart modules from a YAML course specification "
            "using one Codex thread for the complete course run."
        ),
    )
    parser.add_argument(
        "module_ids",
        nargs="*",
        type=non_empty_value,
        metavar="SEC_ID",
        help="section IDs in requested order; omit to generate all sections in YAML order",
    )
    parser.add_argument(
        "--course-spec",
        type=Path,
        default=DEFAULT_GUIDE_SPEC,
        metavar="PATH",
        help=f"guide specification path (default: {DEFAULT_GUIDE_SPEC})",
    )
    parser.add_argument(
        "--prompt-template",
        type=Path,
        default=None,
        metavar="PATH",
        help="custom Markdown prompt template (default: bundled course template)",
    )
    parser.add_argument(
        "--drafts-directory",
        type=Path,
        default=DEFAULT_DRAFTS_DIRECTORY,
        metavar="PATH",
        help=f"destination root for generated drafts (default: {DEFAULT_DRAFTS_DIRECTORY})",
    )
    parser.add_argument(
        "--model",
        type=non_empty_value,
        default=None,
        metavar="MODEL",
        help="Codex model override (default: the user's configured Codex model)",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> CliArguments:
    """Parse CLI values into typed application inputs without side effects."""

    namespace = build_parser().parse_args(argv)
    config = GeneratorConfig(
        guide_spec=cast(Path, namespace.course_spec),
        prompt_template=cast(Path | None, namespace.prompt_template),
        drafts_directory=cast(Path, namespace.drafts_directory),
    )
    return CliArguments(
        module_ids=tuple(cast(list[str], namespace.module_ids)),
        config=config,
        model=cast(str | None, namespace.model),
    )


def run_generation(arguments: CliArguments) -> int:
    """Compose concrete adapters and generate the requested course modules."""

    module_label = ", ".join(arguments.module_ids) or "all sections"
    try:
        outcomes = generate_yaml_course(
            section_ids=arguments.module_ids,
            config=arguments.config,
            prompt_builder=GuidePromptBuilder(
                load_prompt_template(arguments.config.prompt_template)
            ),
            agent=CodexAgent(model=arguments.model),
            writer=MarkdownWriter(),
        )
    except (OSError, ValueError, CodexError, GenerationError) as error:
        # This local PoC prints exception text for diagnosis. Sanitize it before broader use
        # because future SDK messages could contain sensitive details.
        print(
            f"Could not generate course modules {module_label}: {error}",
            file=sys.stderr,
        )
        return 1

    print(f"Generated {len(outcomes)} draft(s) for course modules {module_label}:")
    for outcome in outcomes:
        print(f"  {outcome.artifact_path}")
    print(f"Codex thread: {outcomes[-1].thread_id}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run the command."""

    return run_generation(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
