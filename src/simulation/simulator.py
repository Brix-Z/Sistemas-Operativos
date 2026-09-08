from typing import Dict, Any, Optional, List

from src.models.process import ProcessState
from src.models.event import Event

from src.logging_system.event_logger import EventLogger
from src.managers.process_manager import ProcessManager
from src.managers.memory_manager import MemoryManager
from src.managers.resource_manager import ResourceManager
from src.managers.file_manager import FileManager

from src.simulation.scenario_loader import ScenarioLoader
from src.deadlock.deadlock_detector import DeadlockDetector, DeadlockReport
from src.deadlock.recovery import DeadlockRecovery
from src.visualization.graph_visualizer import GraphVisualizer


class Simulator:
    def __init__(self):
        self.scenario_data: Optional[Dict[str, Any]] = None

        self.process_manager = ProcessManager()
        self.memory_manager: Optional[MemoryManager] = None
        self.resource_manager = ResourceManager()
        self.file_manager = FileManager()

        self.deadlock_detector: Optional[DeadlockDetector] = None
        self.recovery_strategy: Optional[DeadlockRecovery] = None

        self.logger: Optional[EventLogger] = None
        self.events = []

        self.resource_requests = 0
        self.wait_count = 0
        self.step_counter = 0

        self.deadlocks_detected = 0
        self.deadlocks_resolved = 0
        self.resources_in_deadlocks = set()
        self.aborted_pids = set()
        self.pending_deadlocks: List[DeadlockReport] = []

        self.finished = False

    def load_scenario(self, file_path: str) -> None:
        data = ScenarioLoader.load(file_path)

        self.scenario_data = data

        # Reiniciar estructuras.
        self.process_manager = ProcessManager()
        self.resource_manager = ResourceManager()
        self.file_manager = FileManager()

        # Un archivo de log nuevo por cada escenario que se carga,
        # para que todos los eventos de una misma simulación queden
        # en un único archivo reconstruible.
        self.logger = EventLogger()
        self.events = []

        self.resource_requests = 0
        self.wait_count = 0
        self.step_counter = 0

        self.deadlocks_detected = 0
        self.deadlocks_resolved = 0
        self.resources_in_deadlocks = set()
        self.aborted_pids = set()
        self.pending_deadlocks = []

        self.finished = False

        # Memoria.
        memory_total = data["system"]["memory_total"]

        self.memory_manager = MemoryManager(
            total_memory=memory_total
        )

        # Recursos.
        for resource in ScenarioLoader.build_resources(data):
            self.resource_manager.add_resource(resource)

        self.deadlock_detector = DeadlockDetector(
            self.process_manager,
            self.resource_manager
        )

        self.recovery_strategy = DeadlockRecovery(
            self.process_manager,
            self.resource_manager,
            self.memory_manager
        )

        # Archivos.
        for simulated_file in ScenarioLoader.build_files(data):
            self.file_manager.add_file(simulated_file)

        # Procesos.
        for process in ScenarioLoader.build_processes(data):
            self.process_manager.add_process(process)

            self._log(
                event_type="PROCESS_CREATED",
                description=(
                    f"Proceso {process.pid} "
                    f"({process.name}) cargado."
                ),
                pid=process.pid
            )

        scenario_name = data["scenario"].get(
            "name",
            "Sin nombre"
        )

        self._log(
            event_type="SIMULATION_START",
            description=(
                f"Escenario cargado: {scenario_name}"
            )
        )

    def step(self) -> bool:
        """
        Ejecuta una acción pendiente por proceso.

        Retorna True si se realizó al menos una acción.
        """
        if self.finished:
            return False

        executed_something = False

        for process in self.process_manager.all_processes():

            if process.state == ProcessState.TERMINATED:
                continue

            if not process.pending_actions:
                self._terminate_process(process.pid)
                executed_something = True
                continue

            action = process.pending_actions[0]

            success = self._execute_action(
                process.pid,
                action
            )

            if success:
                process.pending_actions.pop(0)
                executed_something = True

        self.step_counter += 1

        self._reevaluate_waiting_processes()

        if not executed_something:
            executed_something = self._handle_stall()

        if not self.process_manager.has_active_processes():
            self.finished = True

            self._log(
                event_type="SIMULATION_END",
                description="La simulación ha terminado."
            )

        return executed_something

    def run(self, max_steps: int = 1000) -> None:
        """
        Ejecución automática: corre el escenario completo hasta el
        final. Cuando encuentra un interbloqueo lo detecta, lo
        registra (con el análisis de las cuatro condiciones) y de
        inmediato aplica la estrategia de recuperación para que la
        simulación pueda continuar sin intervención del usuario.

        En el modo paso a paso (ver `step`), la detección y la
        recuperación quedan separadas: `step` solo detecta y marca
        los procesos como BLOCKED, y es la interfaz quien decide
        cuándo invocar `resolve_pending_deadlocks`.
        """
        count = 0

        while not self.finished and count < max_steps:
            progress = self.step()

            count += 1

            if not progress:
                if self.pending_deadlocks:
                    self.resolve_pending_deadlocks()
                    continue

                self._log(
                    event_type="NO_PROGRESS",
                    description=(
                        "No hubo progreso y no se detectó ningún "
                        "interbloqueo resoluble. Deteniendo la "
                        "simulación."
                    )
                )

                break

        if count >= max_steps:
            self._log(
                event_type="MAX_STEPS",
                description=(
                    "Se alcanzó el máximo de pasos permitidos."
                )
            )

    def _execute_action(
        self,
        pid: int,
        action: Dict[str, Any]
    ) -> bool:

        action_type = action["type"]

        handlers = {
            "request_memory": self._request_memory,
            "release_memory": self._release_memory,
            "request_resource": self._request_resource,
            "release_resource": self._release_resource,
            "create_file": self._create_file,
            "read_file": self._read_file,
            "write_file": self._write_file,
            "move_file": self._move_file,
            "delete_file": self._delete_file,
            "terminate": self._terminate_action
        }

        handler = handlers.get(action_type)

        if handler is None:
            self._log(
                event_type="UNKNOWN_ACTION",
                description=(
                    f"Acción desconocida: {action_type}"
                ),
                pid=pid
            )

            return False

        return handler(pid, action)

    def _request_memory(
        self,
        pid: int,
        action: Dict[str, Any]
    ) -> bool:

        process = self.process_manager.get_process(pid)

        amount = action.get(
            "amount",
            process.memory_required
        )

        success = self.memory_manager.request_memory(
            pid,
            amount
        )

        if success:
            process.set_state(ProcessState.READY)

            self._log(
                event_type="MEMORY_ALLOCATED",
                description=(
                    f"PID {pid} recibió {amount} "
                    f"unidades de memoria."
                ),
                pid=pid
            )

            return True

        process.set_state(ProcessState.WAITING)

        self.wait_count += 1

        self._log(
            event_type="MEMORY_WAIT",
            description=(
                f"PID {pid} espera {amount} "
                f"unidades de memoria."
            ),
            pid=pid
        )

        return False

    def _release_memory(
        self,
        pid: int,
        action: Dict[str, Any]
    ) -> bool:

        amount = action.get("amount")

        success = self.memory_manager.release_memory(
            pid,
            amount
        )

        if success:
            self._log(
                event_type="MEMORY_RELEASED",
                description=(
                    f"PID {pid} liberó memoria."
                ),
                pid=pid
            )

        return success

    def _request_resource(
        self,
        pid: int,
        action: Dict[str, Any]
    ) -> bool:

        resource_id = action["resource"]

        self.resource_requests += 1

        success = self.resource_manager.request_resource(
            pid,
            resource_id
        )

        process = self.process_manager.get_process(pid)

        if success:
            process.add_held_resource(resource_id)
            process.set_state(ProcessState.READY)

            self._log(
                event_type="RESOURCE_ALLOCATED",
                description=(
                    f"Recurso '{resource_id}' "
                    f"asignado al PID {pid}."
                ),
                pid=pid,
                resource_id=resource_id
            )

            return True

        process.set_state(ProcessState.WAITING)

        self.wait_count += 1

        owner = self.resource_manager.get_resource_owner(
            resource_id
        )

        self._log(
            event_type="RESOURCE_WAIT",
            description=(
                f"PID {pid} espera el recurso "
                f"'{resource_id}'. "
                f"Propietario actual: {owner}."
            ),
            pid=pid,
            resource_id=resource_id
        )

        return False

    def _release_resource(
        self,
        pid: int,
        action: Dict[str, Any]
    ) -> bool:

        resource_id = action["resource"]

        success = self.resource_manager.release_resource(
            pid,
            resource_id
        )

        if not success:
            return False

        process = self.process_manager.get_process(pid)

        process.release_resource(resource_id)

        self._log(
            event_type="RESOURCE_RELEASED",
            description=(
                f"PID {pid} liberó el recurso "
                f"'{resource_id}'."
            ),
            pid=pid,
            resource_id=resource_id
        )

        return True

    def _log_file_error(
        self,
        pid: int,
        file_id: str,
        reason: str,
    ) -> None:
        self._log(
            event_type="FILE_OPERATION_REJECTED",
            description=(
                f"PID {pid}: operación inválida sobre el archivo "
                f"'{file_id}'. {reason}"
            ),
            pid=pid
        )

    def _create_file(
        self,
        pid: int,
        action: Dict[str, Any]
    ) -> bool:

        file_id = action["file"]
        name = action.get("name", file_id)
        size = action.get("size", 0)

        success = self.file_manager.create_file(
            file_id,
            name,
            size
        )

        if success:
            self._log(
                event_type="FILE_CREATED",
                description=(
                    f"PID {pid} creó el archivo "
                    f"'{file_id}'."
                ),
                pid=pid
            )
            return True

        if size < 0:
            reason = "El tamaño solicitado es negativo."
        elif self.file_manager.get_file(file_id) is not None:
            reason = "Ya existe un archivo con ese identificador."
        else:
            reason = "No se pudo crear el archivo."

        self._log_file_error(pid, file_id, reason)

        # Es un error permanente (no se resuelve reintentando), así
        # que la acción se descarta y el proceso continúa con la
        # siguiente, en vez de quedar reintentando indefinidamente.
        return True

    def _read_file(
        self,
        pid: int,
        action: Dict[str, Any]
    ) -> bool:

        file_id = action["file"]

        success = self.file_manager.read_file(
            pid,
            file_id
        )

        if success:
            self._log(
                event_type="FILE_READ",
                description=(
                    f"PID {pid} leyó el archivo "
                    f"'{file_id}'."
                ),
                pid=pid
            )
            return True

        file = self.file_manager.get_file(file_id)

        if file is None:
            reason = "El archivo no existe."
        elif file.in_use:
            reason = f"El archivo está en uso por el PID {file.owner}."
        else:
            reason = "No se pudo leer el archivo."

        self._log_file_error(pid, file_id, reason)

        return True

    def _write_file(
        self,
        pid: int,
        action: Dict[str, Any]
    ) -> bool:

        file_id = action["file"]
        new_size = action.get("new_size")

        success = self.file_manager.write_file(
            pid,
            file_id,
            new_size
        )

        if success:
            self._log(
                event_type="FILE_WRITE",
                description=(
                    f"PID {pid} escribió el archivo "
                    f"'{file_id}'."
                ),
                pid=pid
            )
            return True

        file = self.file_manager.get_file(file_id)

        if file is None:
            reason = "El archivo no existe."
        elif new_size is not None and new_size < 0:
            reason = "El nuevo tamaño solicitado es negativo."
        elif file.in_use:
            reason = f"El archivo está en uso por el PID {file.owner}."
        else:
            reason = "No se pudo escribir el archivo."

        self._log_file_error(pid, file_id, reason)

        return True

    def _move_file(
        self,
        pid: int,
        action: Dict[str, Any]
    ) -> bool:

        file_id = action["file"]
        new_name = action["new_name"]

        success = self.file_manager.move_file(
            pid,
            file_id,
            new_name
        )

        if success:
            self._log(
                event_type="FILE_MOVED",
                description=(
                    f"PID {pid} movió/renombró "
                    f"'{file_id}' a '{new_name}'."
                ),
                pid=pid
            )
            return True

        file = self.file_manager.get_file(file_id)

        if file is None:
            reason = "El archivo no existe."
        elif file.in_use:
            reason = f"El archivo está en uso por el PID {file.owner}."
        else:
            reason = "No se pudo mover/renombrar el archivo."

        self._log_file_error(pid, file_id, reason)

        return True

    def _delete_file(
        self,
        pid: int,
        action: Dict[str, Any]
    ) -> bool:

        file_id = action["file"]

        success = self.file_manager.delete_file(
            pid,
            file_id
        )

        if success:
            self._log(
                event_type="FILE_DELETED",
                description=(
                    f"PID {pid} eliminó "
                    f"'{file_id}'."
                ),
                pid=pid
            )
            return True

        file = self.file_manager.get_file(file_id)

        if file is None:
            reason = "El archivo no existe o ya fue eliminado."
        elif file.in_use:
            reason = f"El archivo está en uso por el PID {file.owner}."
        else:
            reason = "No se pudo eliminar el archivo."

        self._log_file_error(pid, file_id, reason)

        return True

    def _terminate_action(
        self,
        pid: int,
        action: Dict[str, Any]
    ) -> bool:

        self._terminate_process(pid)
        return True

    def _terminate_process(self, pid: int) -> None:
        process = self.process_manager.get_process(pid)

        if process is None:
            return

        if process.state == ProcessState.TERMINATED:
            return

        released_resources = (
            self.resource_manager.release_all(pid)
        )

        for resource_id in released_resources:
            process.release_resource(resource_id)

        self.memory_manager.release_all(pid)

        process.set_state(ProcessState.TERMINATED)

        self._log(
            event_type="PROCESS_TERMINATED",
            description=(
                f"PID {pid} terminó y liberó "
                f"sus recursos."
            ),
            pid=pid
        )

    def _handle_stall(self) -> bool:
        """
        Se invoca cuando ningún proceso pudo avanzar en el ciclo
        actual. Consulta al DeadlockDetector y, para cada interbloqueo
        que no se haya registrado todavía, lo marca (procesos ->
        BLOCKED) y registra el análisis de las cuatro condiciones en
        el log. NO aplica la estrategia de recuperación: eso queda
        como una acción explícita (`resolve_pending_deadlocks`) para
        que el modo paso a paso pueda mostrar la detección y la
        visualización del ciclo antes de resolverlo.

        Retorna True si se detectó al menos un interbloqueo NUEVO
        (cuenta como el "evento" de este paso) y False si no hay nada
        nuevo que reportar (incluye el caso de un estancamiento que no
        corresponde a un interbloqueo, p. ej. espera de memoria que
        nunca se liberará).
        """
        reports = self.deadlock_detector.detect_all()

        if not reports:
            self.pending_deadlocks = []
            return False

        already_pending = {
            frozenset(report.involved_pids)
            for report in self.pending_deadlocks
        }

        new_event = False

        for report in reports:
            pid_set = frozenset(report.involved_pids)

            if pid_set not in already_pending:
                self._register_deadlock(report)
                new_event = True

        self.pending_deadlocks = reports

        return new_event

    def resolve_pending_deadlocks(self) -> int:
        """
        Aplica la estrategia de recuperación a todos los interbloqueos
        detectados y pendientes de resolver. Retorna cuántos se
        resolvieron.
        """
        pending = self.pending_deadlocks
        self.pending_deadlocks = []

        for report in pending:
            self._resolve_deadlock(report)

        return len(pending)

    def visualize(
        self,
        file_name: str = "grafo_recursos.png",
        show: bool = False,
    ) -> str:
        """
        Genera una imagen del grafo de asignación/espera con los
        datos actuales del escenario. Si hay un interbloqueo
        pendiente o vigente, lo resalta en la imagen.
        """
        if self.pending_deadlocks:
            report = self.pending_deadlocks[0]
        else:
            reports = self.detect_deadlocks()
            report = reports[0] if reports else None

        visualizer = GraphVisualizer(
            self.process_manager,
            self.resource_manager,
        )

        return visualizer.render(
            file_name=file_name,
            report=report,
            show=show,
        )

    def detect_deadlocks(self) -> List[DeadlockReport]:
        """
        Ejecuta la detección bajo demanda (sin marcar ni resolver
        nada), para consultarla desde la interfaz en cualquier
        momento.
        """
        if self.deadlock_detector is None:
            return []

        return self.deadlock_detector.detect_all()

    def _register_deadlock(self, report: DeadlockReport) -> None:
        self.deadlocks_detected += 1
        self.resources_in_deadlocks.update(report.involved_resources)

        for pid in report.involved_pids:
            self.process_manager.set_state(pid, ProcessState.BLOCKED)

        present = [
            name
            for name, is_present in report.conditions.items()
            if is_present
        ]

        self._log(
            event_type="DEADLOCK_DETECTED",
            description=(
                f"Interbloqueo detectado. Procesos: "
                f"{report.involved_pids}. Recursos: "
                f"{report.involved_resources}. Condiciones "
                f"presentes: {', '.join(present)}."
            )
        )

        for condition_name, explanation in report.explanations.items():
            self._log(
                event_type="CONDITION_ANALYSIS",
                description=f"[{condition_name}] {explanation}"
            )

    def _resolve_deadlock(self, report: DeadlockReport) -> None:
        decision = self.recovery_strategy.apply(report)

        self.deadlocks_resolved += 1
        self.aborted_pids.add(decision.victim_pid)

        self._log(
            event_type="DEADLOCK_RECOVERY",
            description=(
                f"Estrategia de recuperación aplicada: terminación "
                f"forzada de PID {decision.victim_pid}. "
                f"{decision.reason} Recursos liberados: "
                f"{decision.released_resources}."
            ),
            pid=decision.victim_pid
        )

    def _reevaluate_waiting_processes(self) -> None:
        """
        Los procesos WAITING o BLOCKED se vuelven a intentar
        automáticamente en el siguiente ciclo. Un proceso BLOCKED
        puede volver a READY cuando la estrategia de recuperación
        libera el recurso o la memoria que necesitaba.
        """
        pending = (
            self.process_manager.get_waiting_processes()
            + self.process_manager.get_blocked_processes()
        )

        for process in pending:

            if not process.pending_actions:
                continue

            action = process.pending_actions[0]

            if action["type"] == "request_resource":
                resource_id = action["resource"]

                resource = (
                    self.resource_manager.get_resource(
                        resource_id
                    )
                )

                if resource and resource.is_available:
                    process.set_state(ProcessState.READY)

                    self._log(
                        event_type="PROCESS_READY",
                        description=(
                            f"PID {process.pid} puede "
                            f"volver a intentar acceder "
                            f"a '{resource_id}'."
                        ),
                        pid=process.pid,
                        resource_id=resource_id
                    )

            elif action["type"] == "request_memory":
                amount = action.get(
                    "amount",
                    process.memory_required
                )

                if self.memory_manager.has_memory(amount):
                    process.set_state(ProcessState.READY)

                    self._log(
                        event_type="PROCESS_READY",
                        description=(
                            f"PID {process.pid} puede "
                            f"volver a solicitar memoria."
                        ),
                        pid=process.pid
                    )

    def _log(
            
        self,
        event_type: str,
        description: str,
        pid: int = None,
        resource_id: str = None
    ) -> None:

        event = Event(
            event_type=event_type,
            description=description,
            pid=pid,
            resource_id=resource_id
        )

        self.events.append(event)

        self.logger.log(event)

    def get_status(self) -> Dict[str, Any]:
        return {
            "step": self.step_counter,

            "memory": self.memory_manager.status(),

            "processes": {
                process.pid: {
                    "name": process.name,
                    "state": process.state.value,
                    "held_resources": list(
                        process.held_resources
                    ),
                    "pending_actions": len(
                        process.pending_actions
                    )
                }
                for process
                in self.process_manager.all_processes()
            },

            "resources": {
                resource.resource_id: {
                    "available": resource.available,
                    "owner": resource.owner
                }
                for resource
                in self.resource_manager.get_resources()
            },

            "files": {
                file.file_id: {
                    "name": file.name,
                    "size": file.size,
                    "in_use": file.in_use,
                    "owner": file.owner
                }
                for file
                in self.file_manager.get_files()
            },

            "metrics": {
                "total_processes":
                    self.process_manager.count(),

                "resource_requests":
                    self.resource_requests,

                "waits":
                    self.wait_count,

                "terminated":
                    self.process_manager
                    .count_terminated(),

                "blocked":
                    self.process_manager
                    .count_blocked(),

                "max_memory_used":
                    self.memory_manager.max_used,

                "deadlocks_detected":
                    self.deadlocks_detected,

                "deadlocks_resolved":
                    self.deadlocks_resolved,

                "resources_in_deadlocks":
                    sorted(self.resources_in_deadlocks),

                "aborted_pids":
                    sorted(self.aborted_pids),

                "pending_deadlocks": [
                    {
                        "processes": report.involved_pids,
                        "resources": report.involved_resources,
                    }
                    for report in self.pending_deadlocks
                ],
            }
        }