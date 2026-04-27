"""تعامل مع Notion API لإدارة بيانات الأقارب."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from notion_client import Client

from bot.messages import (
    NOTION_DONE_PROPERTY,
    NOTION_NAME_PROPERTY,
    NOTION_PENDING_PROPERTY,
    NOTION_SCHEDULE_PROPERTY,
    NOTION_TARGET_PROPERTY,
    NOTION_WEEKDAY_PROPERTIES,
    WEEKDAY_NAMES_AR_BY_NOTION,
)

logger = logging.getLogger(__name__)


@dataclass
class Relative:
    page_id: str
    name: str
    allowed_weekdays: set[int]
    count_target: int
    count_done: int
    schedule_days: list[int] = field(default_factory=list)
    pending_since: datetime | None = None


class NotionClient:
    def __init__(self, token: str, database_id: str) -> None:
        self._client = Client(auth=token)
        self._database_id = database_id
        db = self._client.databases.retrieve(database_id=database_id)
        sources = db.get("data_sources") or []
        if not sources:
            raise RuntimeError(
                f"Notion database {database_id} has no data sources"
            )
        self._data_source_id: str = sources[0]["id"]

    def ensure_schema(self) -> list[str]:
        """Verify required properties exist. Returns list of missing properties."""
        ds = self._client.data_sources.retrieve(data_source_id=self._data_source_id)
        existing = set(ds.get("properties", {}).keys())
        required = {
            NOTION_NAME_PROPERTY,
            NOTION_TARGET_PROPERTY,
            NOTION_DONE_PROPERTY,
            NOTION_SCHEDULE_PROPERTY,
            NOTION_PENDING_PROPERTY,
            *NOTION_WEEKDAY_PROPERTIES,
        }
        missing = sorted(required - existing)
        return missing

    def add_missing_properties(self, missing: list[str]) -> None:
        """Try to add missing schema properties. Requires schema-edit permission."""
        new_props: dict[str, Any] = {}
        for prop in missing:
            if prop == NOTION_SCHEDULE_PROPERTY:
                new_props[prop] = {"rich_text": {}}
            elif prop == NOTION_PENDING_PROPERTY:
                new_props[prop] = {"date": {}}
            elif prop in NOTION_WEEKDAY_PROPERTIES:
                new_props[prop] = {"checkbox": {}}
            elif prop in {NOTION_TARGET_PROPERTY, NOTION_DONE_PROPERTY}:
                new_props[prop] = {"number": {"format": "number"}}
            elif prop == NOTION_NAME_PROPERTY:
                logger.warning("Cannot auto-add title property; please ensure it exists.")
                continue
        if new_props:
            self._client.data_sources.update(
                data_source_id=self._data_source_id, properties=new_props
            )

    def get_all_relatives(self) -> list[Relative]:
        """Fetch all relatives from the Notion database."""
        results: list[Relative] = []
        cursor: str | None = None
        while True:
            kwargs: dict[str, Any] = {
                "data_source_id": self._data_source_id,
                "page_size": 100,
            }
            if cursor:
                kwargs["start_cursor"] = cursor
            response = self._client.data_sources.query(**kwargs)
            for page in response.get("results", []):
                relative = self._parse_page(page)
                if relative is not None:
                    results.append(relative)
            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")
        return results

    def get_relative(self, page_id: str) -> Relative | None:
        page = self._client.pages.retrieve(page_id=page_id)
        return self._parse_page(page)

    def _parse_page(self, page: dict[str, Any]) -> Relative | None:
        props = page.get("properties", {})
        name = _read_title(props.get(NOTION_NAME_PROPERTY))
        if not name:
            return None

        allowed_weekdays: set[int] = set()
        for prop_name in NOTION_WEEKDAY_PROPERTIES:
            if _read_checkbox(props.get(prop_name)):
                weekday = WEEKDAY_NAMES_AR_BY_NOTION.get(prop_name)
                if weekday is not None:
                    allowed_weekdays.add(weekday)

        count_target = _read_number(props.get(NOTION_TARGET_PROPERTY)) or 0
        count_done = _read_number(props.get(NOTION_DONE_PROPERTY)) or 0

        schedule_days = _parse_schedule(_read_rich_text(props.get(NOTION_SCHEDULE_PROPERTY)))
        pending_since = _read_date(props.get(NOTION_PENDING_PROPERTY))

        return Relative(
            page_id=page["id"],
            name=name,
            allowed_weekdays=allowed_weekdays,
            count_target=int(count_target),
            count_done=int(count_done),
            schedule_days=schedule_days,
            pending_since=pending_since,
        )

    def update_monthly_schedule(self, page_id: str, days: list[int]) -> None:
        days_str = ",".join(str(d) for d in sorted(days))
        self._client.pages.update(
            page_id=page_id,
            properties={
                NOTION_SCHEDULE_PROPERTY: {
                    "rich_text": [{"text": {"content": days_str}}] if days_str else []
                }
            },
        )

    def set_pending(self, page_id: str, timestamp: datetime) -> None:
        self._client.pages.update(
            page_id=page_id,
            properties={
                NOTION_PENDING_PROPERTY: {
                    "date": {"start": timestamp.isoformat()}
                }
            },
        )

    def clear_pending(self, page_id: str) -> None:
        self._client.pages.update(
            page_id=page_id,
            properties={NOTION_PENDING_PROPERTY: {"date": None}},
        )

    def set_done_count(self, page_id: str, value: int) -> None:
        self._client.pages.update(
            page_id=page_id,
            properties={NOTION_DONE_PROPERTY: {"number": value}},
        )

    def increment_done(self, page_id: str) -> int:
        """Atomically increment the done counter. Returns the new value."""
        relative = self.get_relative(page_id)
        new_value = (relative.count_done if relative else 0) + 1
        self.set_done_count(page_id, new_value)
        return new_value

    def reset_all_done_counts(self, page_ids: list[str]) -> None:
        """Reset all done counters and clear pending reminders (monthly reset)."""
        for page_id in page_ids:
            self.set_done_count(page_id, 0)
            self.clear_pending(page_id)

    def add_relative(
        self,
        name: str,
        allowed_weekdays: set[int],
        count_target: int,
    ) -> str:
        properties: dict[str, Any] = {
            NOTION_NAME_PROPERTY: {
                "title": [{"text": {"content": name}}]
            },
            NOTION_TARGET_PROPERTY: {"number": count_target},
            NOTION_DONE_PROPERTY: {"number": 0},
        }
        for prop_name in NOTION_WEEKDAY_PROPERTIES:
            weekday = WEEKDAY_NAMES_AR_BY_NOTION.get(prop_name)
            properties[prop_name] = {
                "checkbox": weekday in allowed_weekdays if weekday is not None else False
            }
        page = self._client.pages.create(
            parent={"data_source_id": self._data_source_id},
            properties=properties,
        )
        return page["id"]

    def update_relative_name(self, page_id: str, new_name: str) -> None:
        self._client.pages.update(
            page_id=page_id,
            properties={
                NOTION_NAME_PROPERTY: {"title": [{"text": {"content": new_name}}]}
            },
        )

    def update_relative_days(self, page_id: str, allowed_weekdays: set[int]) -> None:
        properties: dict[str, Any] = {}
        for prop_name in NOTION_WEEKDAY_PROPERTIES:
            weekday = WEEKDAY_NAMES_AR_BY_NOTION.get(prop_name)
            properties[prop_name] = {
                "checkbox": weekday in allowed_weekdays if weekday is not None else False
            }
        self._client.pages.update(page_id=page_id, properties=properties)

    def update_relative_target(self, page_id: str, count_target: int) -> None:
        self._client.pages.update(
            page_id=page_id,
            properties={NOTION_TARGET_PROPERTY: {"number": count_target}},
        )

    def delete_relative(self, page_id: str) -> None:
        self._client.pages.update(page_id=page_id, archived=True)


def _read_title(prop: dict[str, Any] | None) -> str:
    if not prop:
        return ""
    title_list = prop.get("title", [])
    return "".join(t.get("plain_text", "") for t in title_list).strip()


def _read_rich_text(prop: dict[str, Any] | None) -> str:
    if not prop:
        return ""
    rt_list = prop.get("rich_text", [])
    return "".join(t.get("plain_text", "") for t in rt_list).strip()


def _read_checkbox(prop: dict[str, Any] | None) -> bool:
    if not prop:
        return False
    return bool(prop.get("checkbox", False))


def _read_number(prop: dict[str, Any] | None) -> float | None:
    if not prop:
        return None
    return prop.get("number")


def _read_date(prop: dict[str, Any] | None) -> datetime | None:
    if not prop:
        return None
    date_obj = prop.get("date")
    if not date_obj:
        return None
    start = date_obj.get("start")
    if not start:
        return None
    try:
        return datetime.fromisoformat(start.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_schedule(raw: str) -> list[int]:
    if not raw:
        return []
    days: list[int] = []
    for piece in raw.split(","):
        piece = piece.strip()
        if not piece:
            continue
        try:
            days.append(int(piece))
        except ValueError:
            continue
    return sorted(days)
