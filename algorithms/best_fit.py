"""最佳适应算法（Best Fit）。"""

from __future__ import annotations

from .base import MemoryAllocatorBase, PartitionNode


class BestFitAllocator(MemoryAllocatorBase):
    """最佳适应算法。

    实现思路：
    每次遍历全部空闲块，挑选“满足条件且剩余空间最小”的那一块分配。
    该策略试图减少每次分配时留下的大块浪费，但可能产生较多细碎的小空闲块。
    """

    def __init__(self, total_size_kb: int) -> None:
        super().__init__(total_size_kb=total_size_kb, algorithm_name="Best Fit")

    def find_target_node(self, size_kb: int) -> PartitionNode | None:
        candidate: PartitionNode | None = None
        for node in self.iter_free_nodes():
            if node.size_kb < size_kb:
                continue
            if candidate is None or node.size_kb < candidate.size_kb:
                candidate = node
        return candidate
