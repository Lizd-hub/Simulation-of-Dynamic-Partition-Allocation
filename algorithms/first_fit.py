"""首次适应算法（First Fit）。"""

from __future__ import annotations

from .base import MemoryAllocatorBase, PartitionNode


class FirstFitAllocator(MemoryAllocatorBase):
    """首次适应算法。

    实现思路：
    从链表头部开始顺序扫描，找到第一个容量大于等于申请大小的空闲块，
    立即完成分配。因此该算法实现简单，平均查找速度通常较好，但长期运行
    后容易在低地址区域形成较多碎片。
    """

    def __init__(self, total_size_kb: int) -> None:
        super().__init__(total_size_kb=total_size_kb, algorithm_name="First Fit")

    def find_target_node(self, size_kb: int) -> PartitionNode | None:
        for node in self.iter_free_nodes():
            if node.size_kb >= size_kb:
                return node
        return None
