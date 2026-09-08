import json
from pathlib import Path
from typing import Dict, Any, List

from src.models.process import Process
from src.models.resource import Resource
from src.models.file import SimulatedFile


class ScenarioValidationError(Exception):
    pass


class ScenarioLoader:
    REQUIRED_ROOT_KEYS = {
        "scenario",
        "system",
        "resources",
        "files",
        "processes"
    }

    VALID_ACTIONS = {
        "request_memory",
        "release_memory",
        "request_resource",
        "release_resource",
        "create_file",
        "read_file",
        "write_file",
        "move_file",
        "delete_file",
        "terminate"
    }

    @classmethod
    def load(cls, file_path: str) -> Dict[str, Any]:
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"No se encontró el escenario: {file_path}"
            )

        if path.suffix.lower() != ".json":
            raise ScenarioValidationError(
                "El archivo del escenario debe ser JSON."
            )

        try:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
        except json.JSONDecodeError as error:
            raise ScenarioValidationError(
                f"JSON inválido: {error}"
            ) from error

        cls.validate(data)

        return data

    @classmethod
    def validate(cls, data: Dict[str, Any]) -> None:
        missing = cls.REQUIRED_ROOT_KEYS - data.keys()

        if missing:
            raise ScenarioValidationError(
                f"Faltan campos obligatorios: {sorted(missing)}"
            )

        cls._validate_system(data["system"])
        cls._validate_resources(data["resources"])
        cls._validate_files(data["files"])
        cls._validate_processes(
            data["processes"],
            data["resources"],
            data["files"]
        )

    @staticmethod
    def _validate_system(system: Dict[str, Any]) -> None:
        if "memory_total" not in system:
            raise ScenarioValidationError(
                "El sistema debe definir 'memory_total'."
            )

        memory_total = system["memory_total"]

        if not isinstance(memory_total, int):
            raise ScenarioValidationError(
                "'memory_total' debe ser entero."
            )

        if memory_total <= 0:
            raise ScenarioValidationError(
                "'memory_total' debe ser mayor que 0."
            )

    @staticmethod
    def _validate_resources(resources: List[Dict[str, Any]]) -> None:
        resource_ids = set()

        for resource in resources:
            required = {"id", "name", "quantity"}

            missing = required - resource.keys()

            if missing:
                raise ScenarioValidationError(
                    f"Recurso incompleto: faltan {sorted(missing)}"
                )

            resource_id = resource["id"]

            if resource_id in resource_ids:
                raise ScenarioValidationError(
                    f"ID de recurso duplicado: {resource_id}"
                )

            resource_ids.add(resource_id)

            quantity = resource["quantity"]

            if not isinstance(quantity, int) or quantity <= 0:
                raise ScenarioValidationError(
                    f"Cantidad inválida para recurso '{resource_id}'."
                )

    @staticmethod
    def _validate_files(files: List[Dict[str, Any]]) -> None:
        file_ids = set()

        for file_data in files:
            required = {"id", "name"}

            missing = required - file_data.keys()

            if missing:
                raise ScenarioValidationError(
                    f"Archivo incompleto: faltan {sorted(missing)}"
                )

            file_id = file_data["id"]

            if file_id in file_ids:
                raise ScenarioValidationError(
                    f"ID de archivo duplicado: {file_id}"
                )

            file_ids.add(file_id)

            size = file_data.get("size", 0)

            if not isinstance(size, int) or size < 0:
                raise ScenarioValidationError(
                    f"Tamaño inválido para archivo '{file_id}'."
                )

    @classmethod
    def _validate_processes(
        cls,
        processes: List[Dict[str, Any]],
        resources: List[Dict[str, Any]],
        files: List[Dict[str, Any]]
    ) -> None:

        pids = set()

        resource_ids = {
            resource["id"]
            for resource in resources
        }

        file_ids = {
            file_data["id"]
            for file_data in files
        }

        for process in processes:
            required = {
                "pid",
                "name",
                "memory_required",
                "actions"
            }

            missing = required - process.keys()

            if missing:
                raise ScenarioValidationError(
                    f"Proceso incompleto: faltan {sorted(missing)}"
                )

            pid = process["pid"]

            if not isinstance(pid, int):
                raise ScenarioValidationError(
                    "El PID debe ser entero."
                )

            if pid in pids:
                raise ScenarioValidationError(
                    f"PID duplicado: {pid}"
                )

            pids.add(pid)

            memory_required = process["memory_required"]

            if (
                not isinstance(memory_required, int)
                or memory_required < 0
            ):
                raise ScenarioValidationError(
                    f"Memoria inválida para PID {pid}."
                )

            actions = process["actions"]

            if not isinstance(actions, list):
                raise ScenarioValidationError(
                    f"'actions' debe ser lista en PID {pid}."
                )

            cls._validate_actions(
                pid,
                actions,
                resource_ids,
                file_ids
            )

    @classmethod
    def _validate_actions(
        cls,
        pid: int,
        actions: List[Dict[str, Any]],
        resource_ids: set,
        file_ids: set
    ) -> None:

        action_ids = set()

        # Copia local: un 'create_file' dentro de la secuencia de
        # acciones habilita referencias posteriores a ese mismo
        # archivo (leer/escribir/mover/eliminar), aunque no haya sido
        # declarado en la sección "files" del escenario.
        known_file_ids = set(file_ids)

        for action in actions:
            if "type" not in action:
                raise ScenarioValidationError(
                    f"Acción sin tipo en PID {pid}."
                )

            action_type = action["type"]

            if action_type not in cls.VALID_ACTIONS:
                raise ScenarioValidationError(
                    f"Acción desconocida '{action_type}' "
                    f"en PID {pid}."
                )

            action_id = action.get("id")

            if action_id is not None:
                if action_id in action_ids:
                    raise ScenarioValidationError(
                        f"ID de acción duplicado '{action_id}' "
                        f"en PID {pid}."
                    )

                action_ids.add(action_id)

            if action_type in {
                "request_resource",
                "release_resource"
            }:
                resource_id = action.get("resource")

                if resource_id not in resource_ids:
                    raise ScenarioValidationError(
                        f"PID {pid} usa recurso inexistente: "
                        f"{resource_id}"
                    )

            if action_type == "create_file":
                file_id = action.get("file")
                known_file_ids.add(file_id)

            if action_type in {
                "read_file",
                "write_file",
                "move_file",
                "delete_file"
            }:
                file_id = action.get("file")

                if file_id not in known_file_ids:
                    raise ScenarioValidationError(
                        f"PID {pid} usa archivo inexistente: "
                        f"{file_id}"
                    )

    @staticmethod
    def build_processes(
        data: Dict[str, Any]
    ) -> List[Process]:

        processes = []

        for process_data in data["processes"]:
            process = Process(
                pid=process_data["pid"],
                name=process_data["name"],
                memory_required=process_data[
                    "memory_required"
                ],
                required_resources=process_data.get(
                    "required_resources",
                    []
                ),
                pending_actions=list(
                    process_data["actions"]
                )
            )

            processes.append(process)

        return processes

    @staticmethod
    def build_resources(
        data: Dict[str, Any]
    ) -> List[Resource]:

        resources = []

        for resource_data in data["resources"]:
            resource = Resource(
                resource_id=resource_data["id"],
                name=resource_data["name"],
                resource_type=resource_data.get(
                    "type",
                    "exclusive"
                ),
                quantity=resource_data.get(
                    "quantity",
                    1
                )
            )

            resources.append(resource)

        return resources

    @staticmethod
    def build_files(
        data: Dict[str, Any]
    ) -> List[SimulatedFile]:

        files = []

        for file_data in data["files"]:
            simulated_file = SimulatedFile(
                file_id=file_data["id"],
                name=file_data["name"],
                size=file_data.get("size", 0)
            )

            files.append(simulated_file)

        return files