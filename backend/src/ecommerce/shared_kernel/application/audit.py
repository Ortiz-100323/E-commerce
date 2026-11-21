from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

type JsonValue = str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
type JsonObject = Mapping[str, JsonValue]


@dataclass(frozen=True, kw_only=True)
class AuditEntry:
    occurred_at: datetime
    actor: str
    event: str
    entity: str
    entity_id: str
    sku: str | None
    before: JsonObject | None
    after: JsonObject | None
    context: JsonObject = field(default_factory=dict)


class ActorRequired(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Changes can only be committed by a unit of work opened with an actor.")


class AuditLog(Protocol):
    async def entries_for(self, entity: str, entity_id: str) -> list[AuditEntry]: ...
