"""核心算法回归测试。"""

from __future__ import annotations

import unittest

from algorithms import (
    BestFitAllocator,
    FirstFitAllocator,
    NextFitAllocator,
    WorstFitAllocator,
)


class AllocatorBehaviorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.allocator_types = [
            FirstFitAllocator,
            BestFitAllocator,
            WorstFitAllocator,
            NextFitAllocator,
        ]

    def test_allocate_and_release_restore_single_free_block(self) -> None:
        for allocator_type in self.allocator_types:
            allocator = allocator_type(1024)
            self.assertEqual(allocator.allocate("P001", 256), 0)
            self.assertEqual(allocator.allocate("P002", 128), 256)
            self.assertTrue(allocator.release("P001"))
            self.assertTrue(allocator.release("P002"))
            self.assertEqual(allocator.free_blocks(), [{"start_kb": 0, "size_kb": 1024}])

    def test_best_fit_prefers_smallest_suitable_hole(self) -> None:
        allocator = BestFitAllocator(1000)
        allocator.allocate("P001", 200)
        allocator.allocate("P002", 100)
        allocator.allocate("P003", 150)
        allocator.allocate("P004", 250)
        allocator.release("P002")
        allocator.release("P004")

        address = allocator.allocate("P005", 90)
        self.assertEqual(address, 200)

    def test_worst_fit_prefers_largest_hole(self) -> None:
        allocator = WorstFitAllocator(1200)
        allocator.allocate("P001", 200)
        allocator.allocate("P002", 250)
        allocator.allocate("P003", 150)
        allocator.release("P002")

        address = allocator.allocate("P004", 120)
        self.assertEqual(address, 600)

    def test_next_fit_continues_search_from_last_position(self) -> None:
        allocator = NextFitAllocator(1000)
        allocator.allocate("P001", 100)
        allocator.allocate("P002", 200)
        allocator.allocate("P003", 100)
        allocator.release("P002")

        address = allocator.allocate("P004", 180)
        self.assertEqual(address, 400)


if __name__ == "__main__":
    unittest.main()
