"""Pseudocode for adapter tests; executable tests will be generated later."""

# PSEUDOCODE
#
# TEST initial prompt includes full guide context
#     request has no thread ID
#     build prompt
#     ASSERT complete guide specification is included
#     ASSERT module identity, part prompt, and output boundary are included
#
# TEST continuation prompt is focused
#     request has a thread ID
#     build prompt
#     ASSERT invariant continuation capsule is included
#     ASSERT current module and part are included
#     ASSERT full guide specification is not repeated
#
# TEST writer creates module draft
#     write response into temporary drafts directory
#     ASSERT module directory and expected file exist
#     ASSERT response content and UTF-8 characters are preserved
#
# TEST writer refuses overwrite
#     create existing draft
#     attempt to write the same part
#     EXPECT file-exists error
#     ASSERT existing content is unchanged
#
# DO NOT TEST
#     OpenAI Codex SDK internals
#     live model wording
#     network behavior
#     exact SDK error messages
