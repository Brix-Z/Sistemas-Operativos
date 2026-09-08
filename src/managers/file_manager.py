from typing import Dict, List, Optional

from src.models.file import SimulatedFile


class FileManager:
    def __init__(self):
        self.files: Dict[str, SimulatedFile] = {}

    def add_file(self, simulated_file: SimulatedFile) -> bool:
        if simulated_file.file_id in self.files:
            return False

        self.files[simulated_file.file_id] = simulated_file
        return True

    def get_file(
        self,
        file_id: str
    ) -> Optional[SimulatedFile]:

        return self.files.get(file_id)

    def create_file(
        self,
        file_id: str,
        name: str,
        size: int = 0
    ) -> bool:

        if file_id in self.files:
            return False

        if size < 0:
            return False

        self.files[file_id] = SimulatedFile(
            file_id=file_id,
            name=name,
            size=size,
            created=True
        )

        return True

    def read_file(
        self,
        pid: int,
        file_id: str
    ) -> bool:

        file = self.get_file(file_id)

        if file is None:
            return False

        # Abrimos temporalmente el archivo.
        if not file.open(pid):
            return False

        # La lectura es simulada.
        file.close(pid)

        return True

    def write_file(
        self,
        pid: int,
        file_id: str,
        new_size: Optional[int] = None
    ) -> bool:

        file = self.get_file(file_id)

        if file is None:
            return False

        if new_size is not None and new_size < 0:
            return False

        if not file.open(pid):
            return False

        if new_size is not None:
            file.size = new_size

        file.close(pid)

        return True

    def move_file(
        self,
        pid: int,
        file_id: str,
        new_name: str
    ) -> bool:

        file = self.get_file(file_id)

        if file is None:
            return False

        if not file.open(pid):
            return False

        file.name = new_name
        file.close(pid)

        return True

    def delete_file(
        self,
        pid: int,
        file_id: str
    ) -> bool:

        file = self.get_file(file_id)

        if file is None:
            return False

        if file.in_use:
            return False

        del self.files[file_id]

        return True

    def get_files(self) -> List[SimulatedFile]:
        return list(self.files.values())

    def get_files_in_use(self) -> List[SimulatedFile]:
        return [
            file
            for file in self.files.values()
            if file.in_use
        ]