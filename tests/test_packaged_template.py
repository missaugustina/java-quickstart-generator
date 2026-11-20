"""Verify a built wheel contains a usable default without a repository checkout."""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def test_installed_wheel_loads_default_outside_repository(tmp_path: Path) -> None:
    project = Path(__file__).parents[1]
    uv = shutil.which("uv")
    assert uv is not None
    distribution = tmp_path / "dist"
    subprocess.run(
        [uv, "build", "--offline", "--out-dir", str(distribution)],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next(distribution.glob("*.whl"))
    installed = tmp_path / "installed"
    subprocess.run(
        [uv, "pip", "install", "--offline", "--no-deps", "--target", str(installed), str(wheel)],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    script = """
from pathlib import Path
import java_quickstart_generator
from java_quickstart_generator.course_spec import CourseSection, CourseSpec
from java_quickstart_generator.adapters import GuidePromptBuilder
assert Path(java_quickstart_generator.__file__).is_relative_to(Path('installed').resolve())
section = CourseSection(
    'SEC-01', 'Title', 'MAP-1', 'Purpose', ('Topic',), 'Apply', 'Trace', ('Layout',)
)
spec = CourseSpec(Path('course.yaml'), 'COURSE_CONTEXT_MARKER', (section,), ())
builder = GuidePromptBuilder()
assert 'COURSE_CONTEXT_MARKER' in builder.build_section_prompt(section, spec, None)
assert 'COURSE_CONTEXT_MARKER' not in builder.build_section_prompt(section, spec, 'same-thread')
"""
    environment = dict(os.environ, PYTHONPATH=str(installed))
    subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
