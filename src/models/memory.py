from dataclasses import dataclass


@dataclass
class Memory:
    total: int

    used: int = 0
    max_used: int = 0

    @property
    def available(self) -> int:
        """Memoria disponible."""
        return self.total - self.used

    def can_allocate(self, amount: int) -> bool:
        """Comprueba si hay memoria suficiente."""
        return amount > 0 and amount <= self.available

    def allocate(self, amount: int) -> bool:
        """Intenta asignar memoria."""
        if not self.can_allocate(amount):
            return False

        self.used += amount

        if self.used > self.max_used:
            self.max_used = self.used

        return True

    def release(self, amount: int) -> bool:
        """Libera memoria."""
        if amount <= 0 or amount > self.used:
            return False

        self.used -= amount
        return True