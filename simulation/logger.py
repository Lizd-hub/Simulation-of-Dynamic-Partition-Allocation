"""CSV 日志输出。"""

from __future__ import annotations

import csv
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class LogEntry:
    """供前端展示的最近日志记录。"""

    timestamp: str
    tick: int
    action: str
    process_id: str
    size_kb: int
    result: str
    detail: str


class CsvEventLogger:
    """负责为单个算法输出实时 CSV 日志。"""

    def __init__(self, log_dir: Path, session_id: str, algorithm_key: str) -> None:
        self.algorithm_key = algorithm_key
        self.file_name = f"{session_id}-{algorithm_key}.csv"
        self.path = log_dir / self.file_name
        self.recent_entries: deque[LogEntry] = deque(maxlen=16)

        with self.path.open("w", newline="", encoding="utf-8-sig") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(
                [
                    "timestamp",
                    "tick",
                    "algorithm",
                    "action",
                    "process_id",
                    "size_kb",
                    "result",
                    "detail",
                    "free_block_count",
                    "free_distribution_kb",
                ]
            )

    def log(
        self,
        tick: int,
        action: str,
        process_id: str,
        size_kb: int,
        result: str,
        detail: str,
        free_block_count: int,
        free_distribution_kb: list[int],
    ) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        distribution = "|".join(str(size) for size in free_distribution_kb)

        with self.path.open("a", newline="", encoding="utf-8-sig") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(
                [
                    timestamp,
                    tick,
                    self.algorithm_key,
                    action,
                    process_id,
                    size_kb,
                    result,
                    detail,
                    free_block_count,
                    distribution,
                ]
            )

        self.recent_entries.appendleft(
            LogEntry(
                timestamp=timestamp,
                tick=tick,
                action=action,
                process_id=process_id,
                size_kb=size_kb,
                result=result,
                detail=detail,
            )
        )

    def serialize_recent(self) -> list[dict[str, str | int]]:
        return [
            {
                "timestamp": entry.timestamp,
                "tick": entry.tick,
                "action": entry.action,
                "process_id": entry.process_id,
                "size_kb": entry.size_kb,
                "result": entry.result,
                "detail": entry.detail,
            }
            for entry in self.recent_entries
        ]
