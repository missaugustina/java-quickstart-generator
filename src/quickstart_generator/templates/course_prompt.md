# Initial turn

## Initial generation contract

Generate only the current section as polished Markdown. Treat the course specification as
the authoritative source for audience, structure, terminology, and design constraints.

## Complete guide specification

$course_spec

# Continuation turn

## Continuation contract

Continue in this same Codex thread. Maintain terminology, map IDs, and structure established
in earlier sections. Apply the required section blocks below. Generate only the current
section as polished Markdown; do not generate, summarize, or revise other sections.

# Current section

## Current course section

Section ID: $section_id
Title: $section_title
Source file: $source_filename
Map location: $map_location
Purpose: $purpose

### Topics
$topics

### Assignment connection
$assignment_connection

### Activity
$activity

### Layout
$layout

### Required section blocks
$required_blocks

## Output boundary

- Return only this section, without a preface or a code fence around the response.
- Do not generate, summarize, or revise other sections.
