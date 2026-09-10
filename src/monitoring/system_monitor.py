import os
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

import psutil


@dataclass
class SystemSnapshot:
   
    """ Datos REALES de la máquina donde corre el simulador, obtenidos con psutil. """

    cpu_percent: float
    cpu_count: int

    ram_total_mb: float
    ram_used_mb: float
    ram_percent: float

    disk_path: str
    disk_total_gb: float
    disk_used_gb: float
    disk_percent: float

    net_bytes_sent: int
    net_bytes_recv: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SystemMonitor:
    """
    Envoltorio delgado sobre psutil para obtener una fotografía breve
    del sistema operativo real (requerimiento 4.10). Esta sección es
    informativa y deliberadamente independiente del Simulator: no
    participa en la lógica de administración de recursos simulados ni
    en la detección de interbloqueos.
    """

    def __init__(self, disk_path: Optional[str] = None):
        self.disk_path = disk_path or os.path.abspath(os.sep)

    def snapshot(self) -> SystemSnapshot:
        cpu_percent = psutil.cpu_percent(interval=0.3)
        cpu_count = psutil.cpu_count(logical=True) or 0

        virtual_memory = psutil.virtual_memory()
        disk = psutil.disk_usage(self.disk_path)
        net = psutil.net_io_counters()

        return SystemSnapshot(
            cpu_percent=cpu_percent,
            cpu_count=cpu_count,
            ram_total_mb=round(virtual_memory.total / (1024 ** 2), 1),
            ram_used_mb=round(virtual_memory.used / (1024 ** 2), 1),
            ram_percent=virtual_memory.percent,
            disk_path=self.disk_path,
            disk_total_gb=round(disk.total / (1024 ** 3), 2),
            disk_used_gb=round(disk.used / (1024 ** 3), 2),
            disk_percent=disk.percent,
            net_bytes_sent=net.bytes_sent,
            net_bytes_recv=net.bytes_recv,
        )

    def format_report(self) -> str:
        snap = self.snapshot()

        return "\n".join([
            "=== MONITOREO DEL SISTEMA REAL (psutil) ===",
            "Estos valores describen la máquina física/virtual que",
            "ejecuta el simulador. NO deben confundirse con los",
            "recursos SIMULADOS (memoria, archivos, impresora, disco)",
            "que administra la lógica propia del proyecto.",
            "",
            f"CPU:  {snap.cpu_percent}% de uso "
            f"({snap.cpu_count} núcleos lógicos)",
            f"RAM:  {snap.ram_used_mb} MB usados de "
            f"{snap.ram_total_mb} MB ({snap.ram_percent}%)",
            f"Disco ({snap.disk_path}): {snap.disk_used_gb} GB usados "
            f"de {snap.disk_total_gb} GB ({snap.disk_percent}%)",
            f"Red:  {snap.net_bytes_sent} bytes enviados / "
            f"{snap.net_bytes_recv} bytes recibidos "
            f"(acumulado desde el arranque del sistema operativo)",
        ])
