import os
from typing import Optional

import matplotlib.pyplot as plt
import networkx as nx

from src.deadlock.deadlock_detector import (
    DeadlockDetector,
    DeadlockReport,
    PROCESS_PREFIX,
    RESOURCE_PREFIX,
)
from src.managers.process_manager import ProcessManager
from src.managers.resource_manager import ResourceManager


PROCESS_COLOR = "#1f77b4"
FREE_RESOURCE_COLOR = "#2ca02c"
OCCUPIED_RESOURCE_COLOR = "#ff7f0e"
CYCLE_COLOR = "#d62728"


class GraphVisualizer:
    """
    Genera una representación visual del grafo de asignación/espera
    de recursos a partir de los datos reales del escenario en
    ejecución (no datos de ejemplo ni codificados a mano).
    """

    def __init__(
        self,
        process_manager: ProcessManager,
        resource_manager: ResourceManager,
        output_dir: str = "visualizations",
    ):
        self.process_manager = process_manager
        self.resource_manager = resource_manager
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def render(
        self,
        file_name: str = "grafo_recursos.png",
        report: Optional[DeadlockReport] = None,
        show: bool = False,
    ) -> str:
        detector = DeadlockDetector(
            self.process_manager,
            self.resource_manager,
        )
        graph = detector.build_graph()

        cycle_edges = set()

        if report and report.deadlock_found:
            cycle = report.cycle
            for i in range(len(cycle)):
                a = cycle[i]
                b = cycle[(i + 1) % len(cycle)]
                if graph.has_edge(a, b):
                    cycle_edges.add((a, b))

        cycle_nodes = set(report.cycle) if report and report.deadlock_found else set()

        labels = {}
        color_map = {}

        for node in graph.nodes:
            if node.startswith(PROCESS_PREFIX):
                pid = int(node[len(PROCESS_PREFIX):])
                process = self.process_manager.get_process(pid)
                labels[node] = f"P{pid}\n{process.name}" if process else node
                color_map[node] = (
                    CYCLE_COLOR if node in cycle_nodes else PROCESS_COLOR
                )
            else:
                resource_id = node[len(RESOURCE_PREFIX):]
                resource = self.resource_manager.get_resource(resource_id)
                labels[node] = (
                    f"{resource_id}\n({resource.name})" if resource else node
                )

                if node in cycle_nodes:
                    color_map[node] = CYCLE_COLOR
                elif resource and not resource.is_available:
                    color_map[node] = OCCUPIED_RESOURCE_COLOR
                else:
                    color_map[node] = FREE_RESOURCE_COLOR

        edge_colors = [
            CYCLE_COLOR if edge in cycle_edges
            else ("black" if edge[0].startswith(RESOURCE_PREFIX) else "gray")
            for edge in graph.edges
        ]

        process_nodes = [n for n in graph.nodes if n.startswith(PROCESS_PREFIX)]
        resource_nodes = [n for n in graph.nodes if n.startswith(RESOURCE_PREFIX)]

        plt.figure(figsize=(9, 7))
        pos = nx.spring_layout(graph, seed=42)

        nx.draw_networkx_nodes(
            graph, pos,
            nodelist=process_nodes,
            node_shape="o",
            node_color=[color_map[n] for n in process_nodes],
            node_size=1800,
        )
        nx.draw_networkx_nodes(
            graph, pos,
            nodelist=resource_nodes,
            node_shape="s",
            node_color=[color_map[n] for n in resource_nodes],
            node_size=1800,
        )
        nx.draw_networkx_labels(graph, pos, labels=labels, font_size=8)
        nx.draw_networkx_edges(
            graph, pos,
            edge_color=edge_colors,
            arrows=True,
            arrowsize=20,
            connectionstyle="arc3,rad=0.1",
        )

        title = "Grafo de asignación/espera de recursos"

        if report and report.deadlock_found:
            title += (
                f"\nInterbloqueo detectado: "
                f"procesos {report.involved_pids}"
            )

        plt.title(title)
        plt.axis("off")
        plt.margins(0.15)
        plt.tight_layout()

        output_path = os.path.join(self.output_dir, file_name)
        plt.savefig(output_path, dpi=150)

        if show:
            plt.show()

        plt.close()

        return output_path
