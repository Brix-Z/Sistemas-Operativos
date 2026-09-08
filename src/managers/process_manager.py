from typing import Dict, List, Optional

from src.models.process import Process, ProcessState


class ProcessManager:
    def __init__(self):
        self.processes: Dict[int, Process] = {}

    def add_process(self, process: Process) -> bool:
        """
        Agrega un proceso al sistema.

        Retorna False si ya existe un proceso con el mismo PID.
        """
        if process.pid in self.processes:
            return False

        self.processes[process.pid] = process
        return True

    def get_process(self, pid: int) -> Optional[Process]:
        return self.processes.get(pid)

    def remove_process(self, pid: int) -> bool:
        if pid not in self.processes:
            return False

        del self.processes[pid]
        return True

    def set_state(self, pid: int, state: ProcessState) -> bool:
        process = self.get_process(pid)

        if process is None:
            return False

        process.set_state(state)
        return True

    def get_by_state(self, state: ProcessState) -> List[Process]:
        return [
            process
            for process in self.processes.values()
            if process.state == state
        ]

    def get_ready_processes(self) -> List[Process]:
        return self.get_by_state(ProcessState.READY)

    def get_waiting_processes(self) -> List[Process]:
        return self.get_by_state(ProcessState.WAITING)

    def get_blocked_processes(self) -> List[Process]:
        return self.get_by_state(ProcessState.BLOCKED)

    def get_terminated_processes(self) -> List[Process]:
        return self.get_by_state(ProcessState.TERMINATED)

    def all_processes(self) -> List[Process]:
        return list(self.processes.values())

    def count(self) -> int:
        return len(self.processes)

    def count_terminated(self) -> int:
        return len(self.get_terminated_processes())

    def count_blocked(self) -> int:
        return len(self.get_blocked_processes())

    def has_active_processes(self) -> bool:
        return any(
            process.state != ProcessState.TERMINATED
            for process in self.processes.values()
        )