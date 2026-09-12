"""JSON persistence for scores, preferences and player identity.

The save file is versioned so future phases can migrate old data, and every
read and write is defensive: a missing, malformed or unwritable file leaves
the game running with defaults instead of failing to start.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from config.constants import MAX_SAVED_SCORES, SAVE_FILE, SAVE_VERSION
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SaveData:
    """Everything Space Jumper persists between sessions."""

    version: int = SAVE_VERSION
    high_score: int = 0
    last_username: str = ""
    settings: dict[str, object] = field(default_factory=dict)
    scores: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: object) -> SaveData:
        """Build save data from parsed JSON, discarding anything invalid."""
        if not isinstance(payload, dict):
            logger.error("save payload is not a mapping, starting from defaults")
            return cls()

        version = payload.get("version", SAVE_VERSION)
        if not isinstance(version, int) or isinstance(version, bool):
            logger.warning("invalid save version %r, assuming %d", version, SAVE_VERSION)
            version = SAVE_VERSION
        elif version > SAVE_VERSION:
            logger.warning(
                "save file version %d is newer than %d; unknown data is ignored",
                version,
                SAVE_VERSION,
            )
        elif version < SAVE_VERSION:
            logger.info("migrating save file from version %d", version)

        last_username = payload.get("last_username", "")
        if not isinstance(last_username, str):
            logger.warning("invalid username %r, ignoring", last_username)
            last_username = ""

        settings = payload.get("settings", {})
        if not isinstance(settings, dict):
            logger.warning("invalid settings %r, ignoring", settings)
            settings = {}

        return cls(
            version=version,
            high_score=_as_score(payload.get("high_score"), "high_score"),
            last_username=last_username,
            settings=dict(settings),
            scores=_as_scores(payload.get("scores")),
        )

    def to_payload(self) -> dict[str, object]:
        """Return a JSON-serializable representation of this data."""
        return {
            "version": SAVE_VERSION,
            "high_score": self.high_score,
            "last_username": self.last_username,
            "settings": dict(self.settings),
            "scores": list(self.scores),
        }


def _as_score(value: object, field_name: str) -> int:
    """Return *value* as a non-negative score, or 0 when it is invalid."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        logger.warning("invalid %s %r, using 0", field_name, value)
        return 0
    return value


def _as_scores(value: object) -> list[dict[str, Any]]:
    """Return only the well-formed scoreboard entries in *value*."""
    if not isinstance(value, list):
        logger.warning("invalid score list %r, ignoring", value)
        return []

    entries: list[dict[str, Any]] = []
    for entry in value:
        if not isinstance(entry, dict):
            logger.warning("dropping malformed score entry %r", entry)
            continue
        username = entry.get("username")
        score = entry.get("score")
        jumps = entry.get("jumps", 0)
        if not isinstance(username, str) or not isinstance(score, int) or isinstance(score, bool):
            logger.warning("dropping malformed score entry %r", entry)
            continue
        if not isinstance(jumps, int) or isinstance(jumps, bool):
            jumps = 0
        entries.append({"username": username, "score": score, "jumps": jumps})
    return entries


class SaveManager:
    """Loads and stores :class:`SaveData` as JSON."""

    def __init__(self, path: str = SAVE_FILE) -> None:
        self.path = path
        self.data = SaveData()
        self.readable = True

    # ------------------------------------------------------------------
    # Disk access
    # ------------------------------------------------------------------

    def load(self) -> SaveData:
        """Read the save file, falling back to defaults when it is unusable."""
        if not os.path.exists(self.path):
            logger.info("no save file at %s, starting fresh", self.path)
            self.data = SaveData()
            return self.data

        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError) as exc:
            # The damaged file is deliberately left on disk for inspection and
            # is only overwritten once the player earns a new score.
            logger.error("could not read save file %s (%s)", self.path, exc)
            self.data = SaveData()
            self.readable = False
            return self.data

        self.data = SaveData.from_payload(payload)
        logger.info("loaded save file version %d", self.data.version)
        return self.data

    def save(self) -> bool:
        """Write the save file atomically.  Returns False on failure."""
        self.data.version = SAVE_VERSION
        temporary_path = f"{self.path}.tmp"
        try:
            directory = os.path.dirname(self.path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(temporary_path, "w", encoding="utf-8") as handle:
                json.dump(self.data.to_payload(), handle, indent=2)
            os.replace(temporary_path, self.path)
        except (OSError, TypeError) as exc:
            logger.error("could not write save file %s (%s)", self.path, exc)
            return False
        return True

    # ------------------------------------------------------------------
    # Data updates
    # ------------------------------------------------------------------

    @property
    def high_score(self) -> int:
        """Return the best score ever recorded."""
        return self.data.high_score

    @property
    def scores(self) -> list[dict[str, Any]]:
        """Return the saved scoreboard, best first."""
        return self.data.scores

    def record_score(self, username: str, score: int, jumps: int) -> bool:
        """Store a finished round and report whether it set a new record."""
        self.data.scores.append(
            {"username": username, "score": score, "jumps": jumps}
        )
        self.data.scores.sort(key=lambda entry: entry["score"], reverse=True)
        del self.data.scores[MAX_SAVED_SCORES:]

        is_record = score > self.data.high_score
        if is_record:
            self.data.high_score = score
        self.save()
        return is_record

    def update_settings(self, settings: dict[str, object]) -> None:
        """Replace the persisted preference block."""
        self.data.settings = dict(settings)
        self.save()

    def update_username(self, username: str) -> None:
        """Remember the player name for the next session."""
        self.data.last_username = username
        self.save()
