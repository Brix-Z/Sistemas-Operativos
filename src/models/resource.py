from dataclasses import dataclass
from typing import Optional


@dataclass
class Resource:
    resource_id: str
    name: str
    resource_type: str = "exclusive"
    quantity: int = 1

    allocated: int = 0
    owner: Optional[int] = None

    @property
    def available(self) -> int:
        """Cantidad de unidades disponibles."""
        return self.quantity - self.allocated

    @property
    def is_available(self) -> bool:
        """Indica si existe al menos una unidad disponible."""
        return self.available > 0

    def allocate(self, pid: int) -> bool:
        """
        Intenta asignar una unidad del recurso a un proceso.
        Devuelve True si la asignación fue posible.
        """
        if not self.is_available:
            return False

        self.allocated += 1

        # Para recursos exclusivos de una sola unidad,
        # registramos directamente al propietario.
        if self.quantity == 1:
            self.owner = pid

        return True

    def release(self, pid: int) -> bool:
        """Libera una unidad del recurso."""
        if self.allocated <= 0:
            return False

        if self.quantity == 1 and self.owner != pid:
            return False

        self.allocated -= 1

        if self.quantity == 1:
            self.owner = None

        return True