from dataclasses import dataclass
from typing import Optional


@dataclass
class SimulatedFile:
    file_id: str
    name: str
    size: int = 0

    created: bool = True
    in_use: bool = False
    owner: Optional[int] = None

    def open(self, pid: int) -> bool:
        """Intenta poner el archivo en uso."""
        if self.in_use:
            return False

        self.in_use = True
        self.owner = pid

        return True

    def close(self, pid: int) -> bool:
        """Libera el archivo."""
        if not self.in_use or self.owner != pid:
            return False

        self.in_use = False
        self.owner = None

        return True