"""统一的仿真调度器。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import random

from algorithms import (
    BestFitAllocator,
    FirstFitAllocator,
    NextFitAllocator,
    WorstFitAllocator,
)
from simulation.logger import CsvEventLogger


TOTAL_MEMORY_KB = 10 * 1024
ALGORITHM_DEFINITIONS = [
    ("first_fit", "First Fit", FirstFitAllocator),
    ("best_fit", "Best Fit", BestFitAllocator),
    ("worst_fit", "Worst Fit", WorstFitAllocator),
    ("next_fit", "Next Fit", NextFitAllocator),
]


@dataclass
class ProcessSpec:
    """描述一个由统一事件流生成的进程。"""

    process_id: str
    size_kb: int
    created_tick: int
    end_tick: int

    @property
    def lifetime_ticks(self) -> int:
        return self.end_tick - self.created_tick


@dataclass
class AlgorithmRuntime:
    """单个算法的运行期数据。"""

    key: str
    label: str
    allocator: object
    logger: CsvEventLogger
    failure_count: int = 0
    success_count: int = 0
    release_count: int = 0

    def serialize(self) -> dict[str, object]:
        blocks = self.allocator.snapshot()
        free_blocks = self.allocator.free_blocks()
        free_distribution = [block["size_kb"] for block in free_blocks]
        stats = self.allocator.allocation_stats()
        return {
            "key": self.key,
            "label": self.label,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "release_count": self.release_count,
            "blocks": blocks,
            "free_blocks": free_blocks,
            "free_distribution": free_distribution,
            "stats": stats,
            "recent_logs": self.logger.serialize_recent(),
            "log_file": self.logger.file_name,
        }


def build_placeholder_state() -> dict[str, object]:
    """在仿真未启动时，为前端提供默认渲染数据。"""

    algorithms = []
    for key, label, _allocator_type in ALGORITHM_DEFINITIONS:
        algorithms.append(
            {
                "key": key,
                "label": label,
                "failure_count": 0,
                "success_count": 0,
                "release_count": 0,
                "blocks": [
                    {
                        "start_kb": 0,
                        "end_kb": TOTAL_MEMORY_KB,
                        "size_kb": TOTAL_MEMORY_KB,
                        "process_id": None,
                    }
                ],
                "free_blocks": [{"start_kb": 0, "size_kb": TOTAL_MEMORY_KB}],
                "free_distribution": [TOTAL_MEMORY_KB],
                "stats": {
                    "total_size_kb": TOTAL_MEMORY_KB,
                    "free_total_kb": TOTAL_MEMORY_KB,
                    "allocated_total_kb": 0,
                    "free_block_count": 1,
                    "largest_free_block_kb": TOTAL_MEMORY_KB,
                    "allocated_process_count": 0,
                    "utilization_rate": 0.0,
                },
                "recent_logs": [],
                "log_file": "",
            }
        )
    return {
        "running": False,
        "paused": False,
        "session_id": "",
        "seed": None,
        "tick": 0,
        "interval_ms": 700,
        "active_processes": [],
        "algorithms": algorithms,
    }


class SimulationEngine:
    """将同一批进程事件同时分发给四种算法。"""

    def __init__(
        self,
        log_dir: Path,
        seed: int | None = None,
        interval_ms: int = 700,
    ) -> None:
        self.log_dir = log_dir
        self.seed = seed if seed is not None else random.randint(100_000, 999_999)
        self.interval_ms = interval_ms
        self.random = random.Random(self.seed)
        self.current_tick = 0
        self.pid_counter = 1
        self.active_processes: dict[str, ProcessSpec] = {}
        self.session_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.runtimes: list[AlgorithmRuntime] = []

        for key, label, allocator_type in ALGORITHM_DEFINITIONS:
            logger = CsvEventLogger(log_dir=self.log_dir, session_id=self.session_id, algorithm_key=key)
            allocator = allocator_type(TOTAL_MEMORY_KB)
            runtime = AlgorithmRuntime(key=key, label=label, allocator=allocator, logger=logger)
            self.runtimes.append(runtime)
            self._log_runtime_event(
                runtime,
                action="RESET",
                process_id="-",
                size_kb=0,
                result="OK",
                detail="初始化 10MB 空闲内存",
            )

    def step(self) -> dict[str, object]:
        """推进一个时钟周期。"""

        self.current_tick += 1

        due_processes = sorted(
            (
                process
                for process in self.active_processes.values()
                if process.end_tick <= self.current_tick
            ),
            key=lambda process: (process.end_tick, process.process_id),
        )
        for process in due_processes:
            self._release_process(process)
            self.active_processes.pop(process.process_id, None)

        should_create_process = (
            len(self.active_processes) < 2
            or len(self.active_processes) < 8 and self.random.random() < 0.72
        )
        if should_create_process:
            process = self._create_process()
            self.active_processes[process.process_id] = process
            self._allocate_process(process)

        return self.serialize()

    def serialize(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "seed": self.seed,
            "tick": self.current_tick,
            "interval_ms": self.interval_ms,
            "active_processes": [
                {
                    "process_id": process.process_id,
                    "size_kb": process.size_kb,
                    "created_tick": process.created_tick,
                    "end_tick": process.end_tick,
                    "lifetime_ticks": process.lifetime_ticks,
                }
                for process in sorted(
                    self.active_processes.values(),
                    key=lambda item: item.process_id,
                )
            ],
            "algorithms": [runtime.serialize() for runtime in self.runtimes],
        }

    def _create_process(self) -> ProcessSpec:
        process_id = f"P{self.pid_counter:03d}"
        self.pid_counter += 1

        size_kb = self.random.randint(100, 800)
        lifetime_ticks = self.random.randint(3, 8)
        return ProcessSpec(
            process_id=process_id,
            size_kb=size_kb,
            created_tick=self.current_tick,
            end_tick=self.current_tick + lifetime_ticks,
        )

    def _allocate_process(self, process: ProcessSpec) -> None:
        for runtime in self.runtimes:
            address = runtime.allocator.allocate(process.process_id, process.size_kb)
            if address is None:
                runtime.failure_count += 1
                self._log_runtime_event(
                    runtime,
                    action="ALLOCATE",
                    process_id=process.process_id,
                    size_kb=process.size_kb,
                    result="FAIL",
                    detail=f"申请 {process.size_kb}KB 失败，可用连续空间不足",
                )
                continue

            runtime.success_count += 1
            self._log_runtime_event(
                runtime,
                action="ALLOCATE",
                process_id=process.process_id,
                size_kb=process.size_kb,
                result="OK",
                detail=f"分配成功，起始地址 {address}KB，预计运行 {process.lifetime_ticks} 个时钟",
            )

    def _release_process(self, process: ProcessSpec) -> None:
        for runtime in self.runtimes:
            released = runtime.allocator.release(process.process_id)
            if released:
                runtime.release_count += 1
                detail = f"回收 {process.process_id} 占用的 {process.size_kb}KB 内存"
                result = "OK"
            else:
                detail = f"{process.process_id} 未装入内存，无需回收"
                result = "SKIP"

            self._log_runtime_event(
                runtime,
                action="RELEASE",
                process_id=process.process_id,
                size_kb=process.size_kb,
                result=result,
                detail=detail,
            )

    def _log_runtime_event(
        self,
        runtime: AlgorithmRuntime,
        action: str,
        process_id: str,
        size_kb: int,
        result: str,
        detail: str,
    ) -> None:
        free_distribution = [block["size_kb"] for block in runtime.allocator.free_blocks()]
        runtime.logger.log(
            tick=self.current_tick,
            action=action,
            process_id=process_id,
            size_kb=size_kb,
            result=result,
            detail=detail,
            free_block_count=len(free_distribution),
            free_distribution_kb=free_distribution,
        )
