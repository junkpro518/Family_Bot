"""تسجيل وتحقق من هوية المالك (single-user)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class OwnerStorage:
    def __init__(self, owner_file: Path) -> None:
        self._file = owner_file

    def get_owner_chat_id(self) -> int | None:
        if not self._file.exists():
            return None
        try:
            data = json.loads(self._file.read_text(encoding="utf-8"))
            chat_id = data.get("chat_id")
            return int(chat_id) if chat_id is not None else None
        except (json.JSONDecodeError, ValueError, OSError):
            logger.exception("Failed to read owner file")
            return None

    def set_owner_chat_id(self, chat_id: int) -> None:
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(
            json.dumps({"chat_id": chat_id}, ensure_ascii=False),
            encoding="utf-8",
        )

    def is_owner(self, chat_id: int) -> bool:
        owner = self.get_owner_chat_id()
        return owner is not None and owner == chat_id

    def has_owner(self) -> bool:
        return self.get_owner_chat_id() is not None
