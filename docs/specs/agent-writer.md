# Writer Agent

Converts synthesized content into valid `.md` files for the Obsidian vault.

## Inputs

- `synth_notes: [dict]` — Synthesizer output
- `vault_path: str` — path to `00 - Inbox/` in the vault

## Output

`.md` files written to `00 - Inbox/`. Returns list of created paths.

## Generated Note Format

```markdown
---
type: permanent
created: YYYY-MM-DD
tags: [tag1, tag2]
sources:
  - url: https://...
    title: "Source Title"
---

# Note Title

## Core Concept

<introductory paragraph>

## Subtopics

### Subtopic 1

<content>

## Connections

<!-- filled by Linker -->

## Sources

- [Title](url)
```

## Responsibilities

- Generate frontmatter with `type: permanent`, `created: today`, `tags` inferred from the topic
- Name the file as `Note Title.md` (no special characters)
- Leave `## Connections` empty — the Linker will fill it later
- Do not overwrite an existing note with the same name — append suffix `(2)` if necessary

## Tag Logic

Ask Claude to infer 3–5 lowercase tags from the title and content.

## Tasks

- [ ] Implement note template as Python string
- [ ] File name sanitization logic
- [ ] No-overwrite logic (numeric suffix)
- [ ] Tag inference via Claude
- [ ] Write file to vault Inbox
- [ ] Return list of created paths
- [ ] Unit tests (filesystem in `tmp_path`, Claude mocked):
  - `test_correct_frontmatter`
  - `test_filename_sanitization`
  - `test_numeric_suffix_when_file_exists`
  - `test_required_sections_present`
  - `test_sources_listed_correctly`
