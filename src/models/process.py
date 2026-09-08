from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any


class ProcessState(Enum):
    READY = "READY"
    WAITING = "WAITING"
    BLOCKED = "BLOCKED"
    TERMINATED = "TERMINATED"


@dataclass
class Process:
    pid: int
    name: str
    memory_required: int

    required_resources: List[str] = field(default_factory=list)
    held_resources: List[str] = field(default_factory=list)

    state: ProcessState = ProcessState.READY

    pending_actions: List[Dict[str, Any]] = field(default_factory=list)

    def request_resource(self, resource_id: str) -> None:
        """Registra un recurso que el proceso necesita."""
        if resource_id not in self.required_resources:
            self.required_resources.append(resource_id)

    def add_held_resource(self, resource_id: str) -> None:
        """Registra un recurso actualmente poseído."""
        if resource_id not in self.held_resources:
            self.held_resources.append(resource_id)

    def release_resource(self, resource_id: str) -> None:
        """Libera un recurso que el proceso posee."""
        if resource_id in self.held_resources:
            self.held_resources.remove(resource_id)

    def set_state(self, state: ProcessState) -> None:
        """Cambia el estado del proceso."""
        self.state = state

    def is_finished(self) -> bool:
        """Indica si el proceso terminó."""
        return self.state == ProcessState.TERMINATED