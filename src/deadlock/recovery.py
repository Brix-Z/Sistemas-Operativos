from dataclasses import dataclass
from typing import List

from src.deadlock.deadlock_detector import DeadlockReport
from src.managers.process_manager import ProcessManager
from src.managers.resource_manager import ResourceManager
from src.managers.memory_manager import MemoryManager
from src.models.process import ProcessState


@dataclass
class RecoveryDecision:
    victim_pid: int
    reason: str
    released_resources: List[str]


class DeadlockRecovery:
    """
    Estrategia de recuperación por terminación forzada (preemption).

    Se elige el proceso que retiene la menor cantidad de recursos entre 
    los involucrados en el ciclo, para minimizar el trabajo perdido. 
    En caso de empate se elige el PID más alto (el proceso que ingresó
    más recientemente al sistema). La regla no depende de nombres ni 
    PIDs fijos: se recalcula sobre los procesos reales que forman el 
    ciclo detectado.
    """

    def __init__(
        self,
        process_manager: ProcessManager,
        resource_manager: ResourceManager,
        memory_manager: MemoryManager,
    ):
        self.process_manager = process_manager
        self.resource_manager = resource_manager
        self.memory_manager = memory_manager

    def choose_victim(self, report: DeadlockReport) -> int:
        def cost(pid: int):
            process = self.process_manager.get_process(pid)
            return (len(process.held_resources), -pid)

        return min(report.involved_pids, key=cost)

    def apply(self, report: DeadlockReport) -> RecoveryDecision:
        victim_pid = self.choose_victim(report)
        process = self.process_manager.get_process(victim_pid)

        held_count = len(process.held_resources)

        released = self.resource_manager.release_all(victim_pid)

        for resource_id in released:
            process.release_resource(resource_id)

        self.memory_manager.release_all(victim_pid)

        process.pending_actions.clear()
        process.set_state(ProcessState.TERMINATED)

        reason = (
            f"PID {victim_pid} fue seleccionado por retener la menor "
            f"cantidad de recursos ({held_count}) entre los procesos "
            f"en interbloqueo {report.involved_pids}."
        )

        return RecoveryDecision(
            victim_pid=victim_pid,
            reason=reason,
            released_resources=released,
        )
