from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.command_parser import CommandParser


def test_parse_issue_command_without_bot_username():
    parser = CommandParser()

    command = parser.parse_comment("/issue")

    assert command is not None
    assert command.command == "issue"
    assert command.features is None
    assert command.focus_areas is None


def test_parse_issue_command_requires_bot_mention_when_configured():
    parser = CommandParser(bot_username="review-bot")

    assert parser.parse_comment("/issue") is None

    command = parser.parse_comment("@review-bot /issue")
    assert command is not None
    assert command.command == "issue"
