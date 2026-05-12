"""动态分区分配的基础数据结构与公共逻辑。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator


@dataclass
class PartitionNode:
    """链表中的一个分区节点。

    start_kb:
        分区起始地址，单位 KB。
    size_kb:
        分区大小，单位 KB。
    process_id:
        为 None 表示空闲块，否则表示该分区已被某个进程占用。
    """

    start_kb: int
    size_kb: int
    process_id: str | None = None
    prev: "PartitionNode | None" = field(default=None, repr=False)
    next: "PartitionNode | None" = field(default=None, repr=False)

    @property
    def end_kb(self) -> int:
        """返回分区的结束地址（右开区间）。"""

        return self.start_kb + self.size_kb

    @property
    def is_free(self) -> bool:
        """当前节点是否为空闲分区。"""

        return self.process_id is None


class MemoryAllocatorBase(ABC):
    """四种动态分区算法的公共父类。

    该类统一负责：
    1. 使用双向链表维护内存分区；
    2. 在分配时对空闲块进行拆分；
    3. 在回收时对相邻空闲块进行合并；
    4. 输出快照、统计信息以及空闲分区分布。

    子类只需要实现 `find_target_node`，即“如何选择一个可用空闲块”。
    """

    def __init__(self, total_size_kb: int, algorithm_name: str) -> None:
        self.total_size_kb = total_size_kb
        self.algorithm_name = algorithm_name
        self.head: PartitionNode | None = None
        self.reset()

    def reset(self) -> None:
        """重置整个内存为空闲状态。"""

        self.head = PartitionNode(start_kb=0, size_kb=self.total_size_kb)

    def iter_nodes(self) -> Iterator[PartitionNode]:
        """顺序遍历链表中的所有分区节点。"""

        current = self.head
        while current is not None:
            yield current
            current = current.next

    def iter_free_nodes(self) -> Iterator[PartitionNode]:
        """只遍历空闲分区。"""

        for node in self.iter_nodes():
            if node.is_free:
                yield node

    def locate_process(self, process_id: str) -> PartitionNode | None:
        """在线性链表中查找某个进程所在的分区节点。"""

        for node in self.iter_nodes():
            if node.process_id == process_id:
                return node
        return None

    def allocate(self, process_id: str, size_kb: int) -> int | None:
        """为进程分配内存，成功时返回起始地址，失败返回 None。"""

        target = self.find_target_node(size_kb)
        if target is None:
            return None

        if not target.is_free or target.size_kb < size_kb:
            raise RuntimeError("选中的空闲块不满足分配条件。")

        if target.size_kb == size_kb:
            target.process_id = process_id
            allocated = target
        else:
            remainder = PartitionNode(
                start_kb=target.start_kb + size_kb,
                size_kb=target.size_kb - size_kb,
                prev=target,
                next=target.next,
            )
            if target.next is not None:
                target.next.prev = remainder

            target.size_kb = size_kb
            target.process_id = process_id
            target.next = remainder
            allocated = target

        self.after_allocate(allocated)
        return allocated.start_kb

    def release(self, process_id: str) -> bool:
        """回收指定进程占用的内存，并尝试与相邻空闲块合并。"""

        node = self.locate_process(process_id)
        if node is None:
            return False

        node.process_id = None
        merged = self._merge_adjacent(node)
        self.after_release(merged)
        return True

    def snapshot(self) -> list[dict[str, int | str | None]]:
        """导出当前内存分区快照，用于前端可视化。"""

        blocks: list[dict[str, int | str | None]] = []
        for node in self.iter_nodes():
            blocks.append(
                {
                    "start_kb": node.start_kb,
                    "end_kb": node.end_kb,
                    "size_kb": node.size_kb,
                    "process_id": node.process_id,
                }
            )
        return blocks

    def free_blocks(self) -> list[dict[str, int]]:
        """导出空闲分区列表，用于统计碎片情况。"""

        blocks: list[dict[str, int]] = []
        for node in self.iter_free_nodes():
            blocks.append(
                {
                    "start_kb": node.start_kb,
                    "size_kb": node.size_kb,
                }
            )
        return blocks

    def allocation_stats(self) -> dict[str, int | float]:
        """计算当前时刻的统计信息。"""

        free_blocks = self.free_blocks()
        free_total_kb = sum(block["size_kb"] for block in free_blocks)
        allocated_total_kb = self.total_size_kb - free_total_kb
        largest_free_block_kb = max((block["size_kb"] for block in free_blocks), default=0)
        return {
            "total_size_kb": self.total_size_kb,
            "free_total_kb": free_total_kb,
            "allocated_total_kb": allocated_total_kb,
            "free_block_count": len(free_blocks),
            "largest_free_block_kb": largest_free_block_kb,
            "allocated_process_count": sum(1 for node in self.iter_nodes() if not node.is_free),
            "utilization_rate": round((allocated_total_kb / self.total_size_kb) * 100, 2),
        }

    def after_allocate(self, allocated_node: PartitionNode) -> None:
        """分配成功后的钩子，供子类维护额外状态。"""

    def after_release(self, merged_node: PartitionNode) -> None:
        """回收成功后的钩子，供子类维护额外状态。"""

    def replace_node_reference(
        self,
        replaced_node: PartitionNode,
        replacement_node: PartitionNode,
    ) -> None:
        """节点合并时更新子类维护的游标引用。"""

    def _merge_adjacent(self, node: PartitionNode) -> PartitionNode:
        """将刚刚释放的空闲块与左右相邻空闲块合并。"""

        current = node

        if current.prev is not None and current.prev.is_free:
            previous = current.prev
            self.replace_node_reference(current, previous)
            previous.size_kb += current.size_kb
            previous.next = current.next
            if current.next is not None:
                current.next.prev = previous
            current = previous

        if current.next is not None and current.next.is_free:
            following = current.next
            self.replace_node_reference(following, current)
            current.size_kb += following.size_kb
            current.next = following.next
            if following.next is not None:
                following.next.prev = current

        if current.prev is None:
            self.head = current

        return current

    @abstractmethod
    def find_target_node(self, size_kb: int) -> PartitionNode | None:
        """在链表中找到一个适合当前请求的空闲块。"""
