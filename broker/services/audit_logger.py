from dataclasses import dataclass, field
from typing import Any


@dataclass
class AuditLogger:
    entries: list[dict[str, Any]] = field(default_factory=list)

    def record(self, entry: dict[str, Any]) -> None:
        self.entries.append(entry)
