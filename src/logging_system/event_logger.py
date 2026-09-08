from datetime import datetime
from pathlib import Path
from typing import List

from src.models.event import Event


class EventLogger:
    def __init__(
        self,
        logs_directory: str = "logs"
    ):
        self.logs_directory = Path(
            logs_directory
        )

        self.logs_directory.mkdir(
            parents=True,
            exist_ok=True
        )

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )

        candidate = (
            self.logs_directory
            / f"simulation_{timestamp}.log"
        )

        # Garantiza un archivo distinto por instancia incluso si dos
        # simulaciones se inician dentro del mismo microsegundo.
        suffix = 1
        while candidate.exists():
            candidate = (
                self.logs_directory
                / f"simulation_{timestamp}_{suffix}.log"
            )
            suffix += 1

        self.log_file = candidate

        self.events: List[Event] = []

    def log(self, event: Event) -> None:
        self.events.append(event)

        formatted = event.format()

        print(formatted)

        with open(
            self.log_file,
            "a",
            encoding="utf-8"
        ) as file:
            file.write(formatted + "\n")

    def get_events(self) -> List[Event]:
        return list(self.events)

    def get_last_event(self):
        if not self.events:
            return None

        return self.events[-1]

    def clear(self) -> None:
        self.events.clear()