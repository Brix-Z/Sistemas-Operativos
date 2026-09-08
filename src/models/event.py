from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Event:
    event_type: str
    description: str

    pid: Optional[int] = None
    resource_id: Optional[str] = None

    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def format(self) -> str:
        """Convierte el evento en una línea para el log."""
        time = self.timestamp.strftime("%Y-%m-%d %H:%M:%S")

        return (
            f"[{time}] "
            f"{self.event_type}: "
            f"{self.description}"
        )