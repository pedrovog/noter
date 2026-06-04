import os

DEFAULT_MODEL = os.environ.get("NOTER_MODEL", "claude-sonnet-4-6")

INBOX_SUBFOLDER = os.environ.get("NOTER_INBOX", "inbox")

# Per-agent overrides — fall back to DEFAULT_MODEL if not set
PLANNER_MODEL = os.environ.get("NOTER_PLANNER_MODEL", DEFAULT_MODEL)
SYNTHESIZER_MODEL = os.environ.get("NOTER_SYNTHESIZER_MODEL", DEFAULT_MODEL)
WRITER_MODEL = os.environ.get("NOTER_WRITER_MODEL", DEFAULT_MODEL)
LINKER_MODEL = os.environ.get("NOTER_LINKER_MODEL", DEFAULT_MODEL)
