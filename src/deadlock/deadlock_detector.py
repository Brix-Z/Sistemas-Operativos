from dataclasses import dataclass, field
from typing import Dict, List

import networkx as nx

from src.managers.process_manager import ProcessManager
from src.managers.resource_manager import ResourceManager


PROCESS_PREFIX = "P:"
RESOURCE_PREFIX = "R:"


def process_node(pid: int) -> str:
    return f"{PROCESS_PREFIX}{pid}"


def resource_node(resource_id: str) -> str:
    return f"{RESOURCE_PREFIX}{resource_id}"


@dataclass
class DeadlockReport:
    deadlock_found: bool
    involved_pids: List[int] = field(default_factory=list)
    involved_resources: List[str] = field(default_factory=list)
    cycle: List[str] = field(default_factory=list)
    conditions: Dict[str, bool] = field(default_factory=dict)
    explanations: Dict[str, str] = field(default_factory=dict)


class DeadlockDetector:
    """
    Detecta interbloqueos construyendo el grafo de asignación/espera
    a partir del estado real de ProcessManager y ResourceManager.

    Un ciclo en este grafo equivale a una espera circular. Como todos
    los recursos del simulador se modelan como unidades discretas con
    un único propietario por unidad, un ciclo es condición necesaria y
    suficiente de interbloqueo.
    """

    def __init__(
        self,
        process_manager: ProcessManager,
        resource_manager: ResourceManager,
    ):
        self.process_manager = process_manager
        self.resource_manager = resource_manager

    def build_graph(self) -> "nx.DiGraph":
        graph = nx.DiGraph()

        for resource in self.resource_manager.get_resources():
            graph.add_node(resource_node(resource.resource_id))

        for process in self.process_manager.all_processes():
            graph.add_node(process_node(process.pid))

        for pid in self.resource_manager.process_resources:
            for resource_id in self.resource_manager.get_process_resources(pid):
                graph.add_edge(resource_node(resource_id), process_node(pid))

        for pid, resource_ids in self.resource_manager.get_waiting_processes().items():
            for resource_id in resource_ids:
                graph.add_edge(process_node(pid), resource_node(resource_id))

        return graph

    def detect(self) -> DeadlockReport:
        """Devuelve el primer interbloqueo encontrado, si existe."""
        reports = self.detect_all()

        if not reports:
            return DeadlockReport(deadlock_found=False)

        return reports[0]

    def detect_all(self) -> List[DeadlockReport]:
        """
        Devuelve un reporte por cada ciclo independiente encontrado.
        Permite detectar más de un interbloqueo simultáneo en
        escenarios amplios con varios grupos de procesos/recursos.
        """
        graph = self.build_graph()
        cycles = [cycle for cycle in nx.simple_cycles(graph) if len(cycle) >= 2]

        return [self._build_report(cycle) for cycle in cycles]

    def _build_report(self, cycle: List[str]) -> DeadlockReport:
        involved_pids = sorted({
            int(node[len(PROCESS_PREFIX):])
            for node in cycle
            if node.startswith(PROCESS_PREFIX)
        })

        involved_resources = sorted({
            node[len(RESOURCE_PREFIX):]
            for node in cycle
            if node.startswith(RESOURCE_PREFIX)
        })

        conditions, explanations = self._analyze_conditions(
            involved_pids,
            involved_resources,
            cycle,
        )

        return DeadlockReport(
            deadlock_found=True,
            involved_pids=involved_pids,
            involved_resources=involved_resources,
            cycle=cycle,
            conditions=conditions,
            explanations=explanations,
        )

    def _analyze_conditions(self, involved_pids, involved_resources, cycle):
        conditions = {}
        explanations = {}

        mutual_exclusion = any(
            not self.resource_manager.get_resource(rid).is_available
            for rid in involved_resources
        )

        conditions["exclusion_mutua"] = mutual_exclusion
        explanations["exclusion_mutua"] = (
            "Los recursos involucrados ({}) están completamente "
            "ocupados: ningún otro proceso puede tomarlos mientras "
            "su(s) propietario(s) los retienen.".format(
                ", ".join(involved_resources)
            )
            if mutual_exclusion else
            "Los recursos involucrados no muestran ocupación "
            "exclusiva en este momento."
        )

        hold_and_wait = any(
            len(self.process_manager.get_process(pid).held_resources) > 0
            for pid in involved_pids
        )

        conditions["espera_y_retencion"] = hold_and_wait
        explanations["espera_y_retencion"] = (
            "Al menos un proceso del ciclo ({}) conserva recursos "
            "asignados mientras solicita un recurso adicional.".format(
                ", ".join(str(pid) for pid in involved_pids)
            )
            if hold_and_wait else
            "Ningún proceso del ciclo retiene recursos mientras espera."
        )

        conditions["no_expropiacion"] = True
        explanations["no_expropiacion"] = (
            "El simulador no retira recursos a un proceso de forma "
            "forzada durante la ejecución normal; solo se liberan "
            "cuando el proceso termina por sí mismo o cuando se "
            "aplica la estrategia de recuperación."
        )

        conditions["espera_circular"] = True
        explanations["espera_circular"] = (
            "Se encontró una cadena cerrada en el grafo de "
            "asignación/espera: " + self._describe_cycle(cycle)
        )

        return conditions, explanations

    def _describe_cycle(self, cycle: List[str]) -> str:
        labels = []

        for node in list(cycle) + [cycle[0]]:
            if node.startswith(PROCESS_PREFIX):
                pid = int(node[len(PROCESS_PREFIX):])
                process = self.process_manager.get_process(pid)
                name = process.name if process else "?"
                labels.append(f"P{pid}({name})")
            else:
                resource_id = node[len(RESOURCE_PREFIX):]
                resource = self.resource_manager.get_resource(resource_id)
                name = resource.name if resource else "?"
                labels.append(f"{resource_id}({name})")

        return " -> ".join(labels)
