"""最坏适应算法（Worst Fit）。"""

from __future__ import annotations

from .base import MemoryAllocatorBase, PartitionNode


class WorstFitAllocator(MemoryAllocatorBase):
    """最坏适应算法。

    实现思路：
    每次都从所有空闲块中选择最大的那一块进行分配，希望分配之后仍保留
    较大的连续空间，避免产生过小的不可用碎片。代价是需要扫描全部空闲块。
    """

    def __init__(self, total_size_kb: int) -> None:
        super().__init__(total_size_kb=total_size_kb, algorithm_name="Worst Fit")

    def find_target_node(self, size_kb: int) -> PartitionNode | None:
        candidate: PartitionNode | None = None
        for node in self.iter_free_nodes():
            if node.size_kb < size_kb:
                continue
            if candidate is None or node.size_kb > candidate.size_kb:
                candidate = node
        return candidate
