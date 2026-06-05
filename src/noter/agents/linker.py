import json
import logging
import re
from json import JSONDecodeError
from pathlib import Path

from noter.config import LINKER_MODEL
from noter.exceptions import LinkerError
from noter.llm import chat

logger = logging.getLogger(__name__)

_NON_WORD = re.compile(r"[^a-z0-9\s]")
_WIKILINK = re.compile(r"(\[\[[^\]]+\]\])")

_SYSTEM_PROMPT = """\
You are given the body of an Obsidian note and a list of vault note titles.
Identify which titles appear verbatim (case-insensitive) in the note body
AND are semantically relevant — not incidental mentions.
Respond with valid JSON only — no markdown, no explanation.
Schema: {"titles_to_link": ["Title A", "Title B"]}
If none should be linked, return: {"titles_to_link": []}
"""


def _tokenize(s: str) -> set[str]:
    return set(_NON_WORD.sub(" ", s.lower()).split())


def _build_index(vault_path: str) -> dict[str, str]:
    index: dict[str, str] = {}
    for md_path in Path(vault_path).rglob("*.md"):
        try:
            content = md_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if md_path.stem.startswith("_"):  # skip Obsidian metadata/README files
            continue
        match = re.search(r"^# (.+)$", content, re.MULTILINE)
        heading = match.group(1).strip() if match else None
        if heading and "{{" in heading:  # skip Obsidian template placeholders
            continue
        title = md_path.stem  # use filename so [[wikilinks]] always resolve in Obsidian
        if title in index:
            logger.warning("Duplicate vault title '%s' — keeping first found", title)
        else:
            index[title] = str(md_path.resolve())
    return index


def _parse_note(content: str) -> tuple[str, str]:
    match = re.match(r"^(---\n.*?\n---\n)", content, re.DOTALL)
    if match:
        fm = match.group(1)
        return fm, content[len(fm) :]
    return "", content


def _filter_candidates(body: str, index: dict[str, str], self_path: str) -> list[str]:
    body_tokens = _tokenize(body)
    return [
        title
        for title, path in index.items()
        if path != self_path and _tokenize(title) & body_tokens
    ]


def _detect_links(body: str, candidates: list[str], note_name: str = "") -> list[str]:
    if not candidates:
        return []
    title_list = "\n".join(f"- {t}" for t in candidates)
    user_message = f"Note body:\n{body}\n\nCandidate vault titles:\n{title_list}"

    for attempt in range(2):
        raw = chat(
            system=_SYSTEM_PROMPT,
            user=user_message,
            model=LINKER_MODEL,
            max_tokens=512,
        ).strip()
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1:
            raw = raw[start : end + 1]
        try:
            data = json.loads(raw)
            titles = data.get("titles_to_link", [])
            if isinstance(titles, list) and all(isinstance(t, str) for t in titles):
                return [t for t in titles if t in candidates]
            raise ValueError(f"unexpected format: {data}")
        except (JSONDecodeError, ValueError) as exc:
            if attempt == 1:
                logger.warning(
                    "Linker: LLM returned invalid JSON for note %r after 2 attempts: %s",
                    note_name,
                    exc,
                )
                return []
    return []


def _inject_links(body: str, titles: list[str]) -> tuple[str, int]:
    count = 0
    for title in titles:
        parts = _WIKILINK.split(body)
        pattern = re.compile(r"\b" + re.escape(title) + r"\b", re.IGNORECASE)
        injected = False
        new_parts = []
        for part in parts:
            if injected or part.startswith("[["):
                new_parts.append(part)
            else:
                new_part, n = pattern.subn(f"[[{title}]]", part, count=1)
                if n > 0:
                    injected = True
                    count += 1
                new_parts.append(new_part)
        body = "".join(new_parts)
    return body, count


def _fill_connections(body: str, titles: list[str]) -> str:
    if not titles:
        return body
    bullets = "\n".join(f"- [[{t}]]" for t in titles)
    return body.replace("<!-- filled by Linker -->", bullets, 1)


def run(note_paths: list[str], vault_path: str) -> int:
    """Inject [[wikilinks]] into notes based on existing vault titles.

    Returns the total number of links injected across all notes.

    Raises:
        LinkerError: if vault index cannot be built or files cannot be written.
    """
    try:
        index = _build_index(vault_path)
    except OSError as exc:
        raise LinkerError(f"Failed to build vault index: {exc}") from exc

    logger.debug("Linker: indexed %d vault note(s)", len(index))
    total = 0

    for note_path_str in note_paths:
        note_path = Path(note_path_str)
        try:
            content = note_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise LinkerError(f"Failed to read note '{note_path}': {exc}") from exc

        frontmatter, body = _parse_note(content)
        candidates = _filter_candidates(body, index, str(note_path.resolve()))
        logger.debug("Linker: note %s has %d candidate(s)", note_path.name, len(candidates))
        titles_to_link = _detect_links(body, candidates, note_name=note_path.name)

        if not titles_to_link:
            continue

        updated_body, count = _inject_links(body, titles_to_link)
        updated_body = _fill_connections(updated_body, titles_to_link)
        logger.debug("Linker: %s → %d link(s): %s", note_path.name, count, titles_to_link)

        try:
            note_path.write_text(frontmatter + updated_body, encoding="utf-8")
        except OSError as exc:
            raise LinkerError(f"Failed to write note '{note_path}': {exc}") from exc

        total += count

    return total
