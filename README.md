# Simulador de Administración de Recursos e Interbloqueos

Proyecto parcial de Sistemas Operativos. Simula la administración de
procesos, memoria, archivos y recursos exclusivos/compartidos que
realiza un sistema operativo, con detección automática de
interbloqueos, análisis de las cuatro condiciones, visualización del
grafo de asignación/espera y una estrategia propia de recuperación.

## Instalación

Requiere Python 3.10 o superior.

```bash
pip install -r requirements.txt
```

Dependencias: `networkx` (grafo de asignación/espera y detección de
ciclos), `matplotlib` (visualización), `psutil` (monitoreo real del
sistema).

## Ejecución

```bash
python main.py
```

Se abre un menú interactivo por consola (CLI) con las siguientes
opciones:

1. **Cargar escenario** — lista los archivos `.json` en `scenarios/`
   o permite escribir manualmente la ruta de cualquier otro archivo.
2. **Ejecutar en modo automático** — corre el escenario completo y
   muestra el resultado final y las métricas. Si se produce un
   interbloqueo, se detecta y se resuelve automáticamente para que la
   simulación pueda continuar.
3. **Ejecutar en modo paso a paso** — avanza un evento a la vez.
   Cuando ocurre un interbloqueo, la simulación se detiene (los
   procesos involucrados pasan a estado `BLOCKED`) y **no** se
   resuelve automáticamente: primero se puede consultar el estado,
   ver el análisis de las cuatro condiciones y generar la
   visualización del ciclo, y solo cuando el usuario elige
   "Aplicar estrategia de recuperación" se ejecuta la recuperación y
   la simulación continúa.
4. **Ver estado actual** — memoria, procesos, recursos, archivos y
   último evento.
5. **Detectar interbloqueos** — ejecuta el detector bajo demanda, sin
   modificar el estado, y muestra el análisis de las cuatro
   condiciones para cada ciclo encontrado.
6. **Visualizar grafo de recursos** — genera una imagen PNG en
   `visualizations/` con el grafo de asignación/espera; si hay un
   interbloqueo, el ciclo se resalta en rojo.
7. **Ver métricas y resultados**.
8. **Monitoreo del sistema (psutil)** — CPU, RAM, disco y red
   **reales** de la máquina que ejecuta el programa. Esta sección es
   informativa y está separada de la lógica de recursos simulados.
9. **Salir**.

## Arquitectura

```
main.py                          Interfaz CLI (menú interactivo)
src/
├── models/                      Entidades de datos
│   ├── process.py               Process, ProcessState
│   ├── resource.py              Resource (exclusivo o compartido)
│   ├── memory.py                Memory
│   ├── file.py                  SimulatedFile
│   └── event.py                 Event (para el log)
├── managers/                    Lógica de administración
│   ├── process_manager.py
│   ├── memory_manager.py
│   ├── resource_manager.py
│   └── file_manager.py
├── simulation/
│   ├── scenario_loader.py       Carga y valida los JSON de escenario
│   └── simulator.py             Motor de simulación (orquesta todo)
├── deadlock/
│   ├── deadlock_detector.py     Grafo de asignación/espera + ciclos
│   └── recovery.py              Estrategia de recuperación
├── visualization/
│   └── graph_visualizer.py      Dibuja el grafo con NetworkX/Matplotlib
├── monitoring/
│   └── system_monitor.py        Monitoreo real con psutil
└── logging_system/
    └── event_logger.py          Registro de eventos a archivo
scenarios/                       Escenarios de prueba (JSON)
logs/                            Un archivo .log por simulación ejecutada
visualizations/                  Imágenes generadas por el visualizador
```

## Detección de interbloqueos

`DeadlockDetector` construye dinámicamente el grafo de
asignación/espera a partir del estado real de `ProcessManager` y
`ResourceManager` (no usa nombres fijos como P1/R1: funciona con
cualquier combinación de procesos y recursos definida en el
escenario). Los nodos son procesos (`P:<pid>`) y recursos
(`R:<id>`); una arista `recurso -> proceso` representa una
asignación, y `proceso -> recurso` representa una solicitud
pendiente. Un ciclo en ese grafo es un interbloqueo. La búsqueda de
ciclos usa `networkx.simple_cycles`, por lo que generaliza a
interbloqueos de más de dos procesos (ver `escenario_5_amplio.json`,
que produce un ciclo de tres procesos).

Cuando se detecta un ciclo, se analizan automáticamente las cuatro
condiciones (exclusión mutua, espera y retención, no expropiación,
espera circular) generando las explicaciones a partir del estado real
del escenario, no de texto fijo por caso.

## Estrategia de recuperación

Implementada en `src/deadlock/recovery.py`: cuando se confirma un
interbloqueo, se elige como "víctima" al proceso del ciclo que
retiene menos recursos (para minimizar el trabajo perdido; en caso de
empate se elige el PID más alto). Se le retiran forzosamente sus
recursos y su memoria y se termina, lo que rompe deliberadamente la
condición de **no expropiación**. El resto de los procesos —
incluidos los que no participaban en el ciclo— continúan con
normalidad.

## Escenarios incluidos

| Archivo | Propósito |
|---|---|
| `escenario_1_normal.json` | Ejecución normal, sin espera ni interbloqueo. |
| `escenario_2_espera_temporal.json` | Un proceso espera un recurso ocupado, pero se libera a tiempo y ambos terminan. |
| `escenario_3_interbloqueo.json` | Interbloqueo simple de 2 procesos / 2 recursos exclusivos en orden cruzado. |
| `escenario_4_prevencion_recuperacion.json` | Interbloqueo con recursos distintos, más un tercer proceso independiente para demostrar que la recuperación no afecta al resto del sistema. |
| `escenario_5_amplio.json` | 5 procesos y 4 recursos (incluye uno compartido con cupo 2); produce un interbloqueo de **tres** procesos para probar que la detección generaliza más allá del caso trivial. |

Cada escenario es un JSON independiente en `scenarios/` y se carga
sin modificar el código fuente (opción 1 del menú, incluyendo la
posibilidad de escribir manualmente la ruta de un escenario externo).

## Logs

Cada ejecución genera un archivo nuevo en `logs/` con marca de tiempo
(`simulation_AAAAMMDD_HHMMSS.log`), con todos los eventos relevantes:
creación de procesos, solicitudes y asignaciones de memoria/recursos,
liberaciones, operaciones de archivos, cambios de estado,
detección de interbloqueos con el análisis de las cuatro condiciones,
y la decisión de recuperación aplicada.
