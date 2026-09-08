import os
from pathlib import Path

from src.simulation.simulator import Simulator
from src.simulation.scenario_loader import ScenarioValidationError
from src.monitoring.system_monitor import SystemMonitor
from src.models.process import ProcessState


SCENARIOS_DIR = "scenarios"


def print_header(title: str) -> None:
    print("\n" + "=" * 64)
    print(title)
    print("=" * 64)


def list_scenarios():
    path = Path(SCENARIOS_DIR)

    if not path.exists():
        return []

    return sorted(path.glob("*.json"))


def choose_scenario_path():
    scenarios = list_scenarios()

    print_header("CARGAR ESCENARIO")

    for index, scenario_path in enumerate(scenarios, start=1):
        print(f"  {index}. {scenario_path.name}")

    print("  0. Ingresar una ruta manualmente "
          "(por ejemplo, el escenario sorpresa)")

    choice = input("Seleccione una opción: ").strip()

    if choice == "0":
        return input("Ruta del archivo JSON del escenario: ").strip()

    if choice.isdigit():
        index = int(choice) - 1
        if 0 <= index < len(scenarios):
            return str(scenarios[index])

    print("Opción inválida.")
    return None


def load_scenario_flow(simulator: Simulator) -> bool:
    path = choose_scenario_path()

    if not path:
        return False

    try:
        simulator.load_scenario(path)
        print(f"\nEscenario cargado correctamente: {path}")
        return True

    except FileNotFoundError as error:
        print(f"ERROR: {error}")

    except ScenarioValidationError as error:
        print(f"ESCENARIO INVÁLIDO: {error}")

    return False


def print_status(simulator: Simulator) -> None:
    status = simulator.get_status()

    print_header("ESTADO ACTUAL DEL SISTEMA")
    print(f"Paso actual: {status['step']}")

    mem = status["memory"]
    print(
        f"\nMemoria -> total: {mem['total']} | usada: {mem['used']} | "
        f"disponible: {mem['available']} | máx. usada: {mem['max_used']}"
    )

    print("\nProcesos:")
    for pid, info in status["processes"].items():
        print(
            f"  PID {pid} ({info['name']}): estado={info['state']}, "
            f"recursos_en_posesion={info['held_resources']}, "
            f"acciones_pendientes={info['pending_actions']}"
        )

    print("\nRecursos:")
    for resource_id, info in status["resources"].items():
        estado = (
            "LIBRE" if info["available"] > 0
            else f"OCUPADO por PID {info['owner']}"
        )
        print(f"  {resource_id}: {estado}")

    print("\nArchivos:")
    for file_id, info in status["files"].items():
        estado = (
            f"EN USO por PID {info['owner']}" if info["in_use"]
            else "disponible"
        )
        print(
            f"  {file_id} ({info['name']}, {info['size']} bytes): {estado}"
        )

    pending = status["metrics"]["pending_deadlocks"]

    if pending:
        print("\n[!] Interbloqueos pendientes de resolución:")
        for deadlock in pending:
            print(
                f"    Procesos {deadlock['processes']} <-> "
                f"Recursos {deadlock['resources']}"
            )

    if simulator.events:
        print(f"\nÚltimo evento: {simulator.events[-1].format()}")


def print_processes_by_state(
    simulator: Simulator,
    state: ProcessState,
    label: str,
) -> None:

    processes = simulator.process_manager.get_by_state(state)

    print_header(label)

    if not processes:
        print("  (ninguno)")
        return

    for process in processes:
        print(
            f"  PID {process.pid} ({process.name}) - "
            f"memoria: {process.memory_required}, "
            f"recursos: {process.held_resources}"
        )


def print_metrics(simulator: Simulator) -> None:
    metrics = simulator.get_status()["metrics"]

    print_header("RESULTADOS Y MÉTRICAS")
    print(f"Total de procesos:                     {metrics['total_processes']}")
    print(f"Procesos terminados:                   {metrics['terminated']}")
    print(f"Procesos bloqueados actualmente:        {metrics['blocked']}")
    print(f"Uso máximo de memoria:                  {metrics['max_memory_used']}")
    print(f"Solicitudes de recursos realizadas:     {metrics['resource_requests']}")
    print(f"Veces que un proceso tuvo que esperar:  {metrics['waits']}")
    print(f"Interbloqueos detectados:               {metrics['deadlocks_detected']}")
    print(f"Interbloqueos resueltos:                {metrics['deadlocks_resolved']}")
    print(f"Recursos involucrados en interbloqueos: {metrics['resources_in_deadlocks']}")
    print(f"Procesos abortados por recuperación:    {metrics['aborted_pids']}")


def detect_deadlocks_flow(simulator: Simulator) -> None:
    reports = simulator.detect_deadlocks()

    print_header("DETECCIÓN DE INTERBLOQUEOS")

    if not reports:
        print("No se detectó ningún interbloqueo en el estado actual.")
        return

    for report in reports:
        print(
            f"\nInterbloqueo entre procesos {report.involved_pids} "
            f"y recursos {report.involved_resources}"
        )
        print("Condiciones analizadas:")

        for name, present in report.conditions.items():
            marca = "SI" if present else "NO"
            print(f"  [{marca}] {name}: {report.explanations[name]}")


def visualize_flow(simulator: Simulator) -> None:
    print_header("VISUALIZACIÓN DEL GRAFO DE RECURSOS")

    path = simulator.visualize(show=False)
    print(f"Imagen generada en: {path}")

    if input("¿Abrir la imagen ahora? (s/n): ").strip().lower() == "s":
        try:
            os.startfile(path)
        except (AttributeError, OSError):
            print(
                "No se pudo abrir automáticamente. "
                "Ábrala manualmente desde la ruta indicada."
            )


def resolve_deadlocks_flow(simulator: Simulator) -> None:
    print_header("APLICAR ESTRATEGIA DE RECUPERACIÓN")

    if not simulator.pending_deadlocks:
        print("No hay interbloqueos pendientes de resolución.")
        return

    resolved = simulator.resolve_pending_deadlocks()
    print(f"Se resolvieron {resolved} interbloqueo(s).")


def monitoring_flow() -> None:
    print_header("MONITOREO DEL SISTEMA (psutil)")
    print(SystemMonitor().format_report())


def step_by_step_mode(simulator: Simulator) -> None:
    while True:
        print_header(
            f"MODO PASO A PASO (paso actual: {simulator.step_counter})"
        )
        print("  1. Ejecutar siguiente evento")
        print("  2. Ver estado general")
        print("  3. Ver procesos activos/listos")
        print("  4. Ver procesos esperando")
        print("  5. Ver procesos bloqueados")
        print("  6. Ver procesos terminados")
        print("  7. Detectar interbloqueos")
        print("  8. Visualizar grafo de recursos")
        print("  9. Aplicar estrategia de recuperación")
        print(" 10. Ver métricas actuales")
        print("  0. Volver al menú principal")

        choice = input("Seleccione una opción: ").strip()

        if choice == "1":
            if simulator.finished:
                print("La simulación ya terminó.")
            else:
                progress = simulator.step()
                if not progress:
                    if simulator.pending_deadlocks:
                        print(
                            "No hubo progreso: hay un interbloqueo "
                            "pendiente. Use la opción 9 para "
                            "resolverlo, o la 8 para visualizarlo "
                            "antes de resolverlo."
                        )
                    else:
                        print(
                            "No hubo progreso ni interbloqueo "
                            "detectable en este ciclo."
                        )

            if simulator.finished:
                print("\n*** La simulación ha terminado. ***")

        elif choice == "2":
            print_status(simulator)
        elif choice == "3":
            print_processes_by_state(
                simulator, ProcessState.READY, "PROCESOS ACTIVOS/LISTOS"
            )
        elif choice == "4":
            print_processes_by_state(
                simulator, ProcessState.WAITING, "PROCESOS ESPERANDO"
            )
        elif choice == "5":
            print_processes_by_state(
                simulator, ProcessState.BLOCKED, "PROCESOS BLOQUEADOS"
            )
        elif choice == "6":
            print_processes_by_state(
                simulator, ProcessState.TERMINATED, "PROCESOS TERMINADOS"
            )
        elif choice == "7":
            detect_deadlocks_flow(simulator)
        elif choice == "8":
            visualize_flow(simulator)
        elif choice == "9":
            resolve_deadlocks_flow(simulator)
        elif choice == "10":
            print_metrics(simulator)
        elif choice == "0":
            return
        else:
            print("Opción inválida.")


def automatic_mode(simulator: Simulator) -> None:
    print_header("MODO AUTOMÁTICO")

    simulator.run()

    print("\nSimulación finalizada.")
    print_metrics(simulator)


def main_menu() -> None:
    simulator = Simulator()
    scenario_loaded = False

    while True:
        print_header(
            "SIMULADOR DE ADMINISTRACIÓN DE RECURSOS E INTERBLOQUEOS"
        )
        print("  1. Cargar escenario")
        print("  2. Ejecutar en modo automático")
        print("  3. Ejecutar en modo paso a paso")
        print("  4. Ver estado actual")
        print("  5. Detectar interbloqueos")
        print("  6. Visualizar grafo de recursos")
        print("  7. Ver métricas y resultados")
        print("  8. Monitoreo del sistema (psutil)")
        print("  9. Salir")

        choice = input("Seleccione una opción: ").strip()

        if choice == "1":
            scenario_loaded = load_scenario_flow(simulator)
            continue

        if choice == "8":
            monitoring_flow()
            continue

        if choice == "9":
            print("Saliendo del simulador...")
            break

        if choice in {"2", "3", "4", "5", "6", "7"} and not scenario_loaded:
            print("Primero debe cargar un escenario (opción 1).")
            continue

        if choice == "2":
            automatic_mode(simulator)
        elif choice == "3":
            step_by_step_mode(simulator)
        elif choice == "4":
            print_status(simulator)
        elif choice == "5":
            detect_deadlocks_flow(simulator)
        elif choice == "6":
            visualize_flow(simulator)
        elif choice == "7":
            print_metrics(simulator)
        else:
            print("Opción inválida.")


if __name__ == "__main__":
    main_menu()
