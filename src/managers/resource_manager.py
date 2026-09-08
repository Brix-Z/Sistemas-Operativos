from typing import Dict, List, Optional

from src.models.resource import Resource


class ResourceManager:
    def __init__(self):
        self.resources: Dict[str, Resource] = {}

        # Recursos que cada proceso tiene actualmente.
        self.process_resources: Dict[int, List[str]] = {}

        # Solicitudes pendientes:
        # PID -> lista de recursos que está esperando.
        self.waiting_requests: Dict[int, List[str]] = {}

    def add_resource(self, resource: Resource) -> bool:
        if resource.resource_id in self.resources:
            return False

        if resource.quantity <= 0:
            return False

        self.resources[resource.resource_id] = resource
        return True

    def get_resource(self, resource_id: str) -> Optional[Resource]:
        return self.resources.get(resource_id)

    def request_resource(
        self,
        pid: int,
        resource_id: str
    ) -> bool:

        resource = self.get_resource(resource_id)

        if resource is None:
            return False

        # El proceso ya posee el recurso.
        if resource_id in self.process_resources.get(pid, []):
            return True

        if resource.is_available:
            if resource.allocate(pid):

                self.process_resources.setdefault(
                    pid, []
                ).append(resource_id)

                # Ya no está esperando este recurso.
                self._remove_waiting_request(
                    pid,
                    resource_id
                )

                return True

        # El recurso está ocupado.
        self.waiting_requests.setdefault(
            pid,
            []
        ).append(resource_id)

        return False

    def release_resource(
        self,
        pid: int,
        resource_id: str
    ) -> bool:

        resource = self.get_resource(resource_id)

        if resource is None:
            return False

        owned_resources = self.process_resources.get(
            pid,
            []
        )

        if resource_id not in owned_resources:
            return False

        if not resource.release(pid):
            return False

        owned_resources.remove(resource_id)

        if not owned_resources:
            self.process_resources.pop(pid, None)

        return True

    def release_all(self, pid: int) -> List[str]:
        """
        Libera todos los recursos pertenecientes
        al proceso.
        """
        released = []

        owned_resources = list(
            self.process_resources.get(pid, [])
        )

        for resource_id in owned_resources:
            if self.release_resource(pid, resource_id):
                released.append(resource_id)

        return released

    def get_process_resources(
        self,
        pid: int
    ) -> List[str]:

        return list(
            self.process_resources.get(pid, [])
        )

    def get_resource_owner(
        self,
        resource_id: str
    ) -> Optional[int]:

        resource = self.get_resource(resource_id)

        if resource is None:
            return None

        return resource.owner

    def get_available_resources(self) -> List[str]:
        return [
            resource_id
            for resource_id, resource in self.resources.items()
            if resource.is_available
        ]

    def get_occupied_resources(self) -> List[str]:
        return [
            resource_id
            for resource_id, resource in self.resources.items()
            if not resource.is_available
        ]

    def get_waiting_processes(self) -> Dict[int, List[str]]:
        return {
            pid: list(resources)
            for pid, resources
            in self.waiting_requests.items()
        }

    def get_resources(self) -> List[Resource]:
        return list(self.resources.values())

    def _remove_waiting_request(
        self,
        pid: int,
        resource_id: str
    ) -> None:

        requests = self.waiting_requests.get(pid)

        if not requests:
            return

        if resource_id in requests:
            requests.remove(resource_id)

        if not requests:
            self.waiting_requests.pop(pid, None)

    def clear_process(self, pid: int) -> None:
        self.release_all(pid)
        self.waiting_requests.pop(pid, None)