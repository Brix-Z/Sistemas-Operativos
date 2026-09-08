from typing import Dict

from src.models.memory import Memory


class MemoryManager:
    def __init__(self, total_memory: int):
        if total_memory <= 0:
            raise ValueError("La memoria total debe ser mayor que 0.")

        self.memory = Memory(total=total_memory)

        # Memoria asignada a cada proceso.
        self.allocations: Dict[int, int] = {}

    @property
    def total(self) -> int:
        return self.memory.total

    @property
    def used(self) -> int:
        return self.memory.used

    @property
    def available(self) -> int:
        return self.memory.available

    @property
    def max_used(self) -> int:
        return self.memory.max_used

    def request_memory(self, pid: int, amount: int) -> bool:
        """
        Intenta asignar memoria a un proceso.
        """
        if amount <= 0:
            return False

        if not self.memory.allocate(amount):
            return False

        self.allocations[pid] = (
            self.allocations.get(pid, 0) + amount
        )

        return True

    def release_memory(self, pid: int, amount: int = None) -> bool:
        """
        Libera memoria perteneciente a un proceso.

        Si amount es None, libera toda la memoria del proceso.
        """
        allocated = self.allocations.get(pid, 0)

        if allocated <= 0:
            return False

        if amount is None:
            amount = allocated

        if amount <= 0 or amount > allocated:
            return False

        if not self.memory.release(amount):
            return False

        remaining = allocated - amount

        if remaining == 0:
            del self.allocations[pid]
        else:
            self.allocations[pid] = remaining

        return True

    def get_process_memory(self, pid: int) -> int:
        return self.allocations.get(pid, 0)

    def has_memory(self, amount: int) -> bool:
        return self.memory.can_allocate(amount)

    def release_all(self, pid: int) -> bool:
        return self.release_memory(pid)

    def status(self) -> dict:
        return {
            "total": self.total,
            "used": self.used,
            "available": self.available,
            "max_used": self.max_used,
        }