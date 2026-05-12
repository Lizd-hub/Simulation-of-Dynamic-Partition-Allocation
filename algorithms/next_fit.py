"""邻近适应算法（Next Fit）。"""

from __future__ import annotations

from .base import MemoryAllocatorBase, PartitionNode


class NextFitAllocator(MemoryAllocatorBase):
    """邻近适应算法。

    实现思路：
    与首次适应不同，Next Fit 不会每次都从链表头开始查找，而是从上一次
    分配结束后的位置继续向后扫描。如果扫描到链表尾部，则回绕到链表头。
    这样可以避免低地址区域被反复扫描，但也可能错过前面更合适的空闲块。
    """

    def __init__(self, total_size_kb: int) -> None:
        self.cursor: PartitionNode | None = None
        super().__init__(total_size_kb=total_size_kb, algorithm_name="Next Fit")

    def reset(self) -> None:
        super().reset()
        self.cursor = self.head

    def find_target_node(self, size_kb: int) -> PartitionNode | None:
        start = self.cursor or self.head
        if start is None:
            return None

        current = start
        wrapped = False

        while current is not None:
            if current.is_free and current.size_kb >= size_kb:
                return current

            current = current.next
            if current is None and not wrapped:
                current = self.head
                wrapped = True

            if current is start:
                break

        return None

    def after_allocate(self, allocated_node: PartitionNode) -> None:
        self.cursor = allocated_node.next or self.head

    def after_release(self, merged_node: PartitionNode) -> None:
        if self.cursor is None:
            self.cursor = merged_node

    def replace_node_reference(
        self,
        replaced_node: PartitionNode,
        replacement_node: PartitionNode,
    ) -> None:
        if self.cursor is replaced_node:
            self.cursor = replacement_node
