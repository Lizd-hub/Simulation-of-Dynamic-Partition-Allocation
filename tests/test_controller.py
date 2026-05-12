"""控制器暂停/继续状态测试。"""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

import app


class SimulationControllerStateTest(unittest.TestCase):
    def test_pause_keeps_snapshot_and_resume_advances_tick(self) -> None:
        controller = app.SimulationController()

        with tempfile.TemporaryDirectory() as temp_dir:
            original_log_dir = app.LOG_DIR
            app.LOG_DIR = Path(temp_dir)
            try:
                started = controller.start(seed=12345, interval_ms=120)
                self.assertTrue(started["running"])
                self.assertFalse(started["paused"])

                time.sleep(0.18)
                paused = controller.pause()
                paused_tick = paused["tick"]
                self.assertFalse(paused["running"])
                self.assertTrue(paused["paused"])

                time.sleep(0.22)
                paused_again = controller.get_state()
                self.assertEqual(paused_again["tick"], paused_tick)

                resumed = controller.resume()
                self.assertTrue(resumed["running"])
                self.assertFalse(resumed["paused"])

                time.sleep(0.18)
                advanced = controller.get_state()
                self.assertGreater(advanced["tick"], paused_tick)

                stopped = controller.stop()
                self.assertFalse(stopped["running"])
                self.assertFalse(stopped["paused"])
            finally:
                controller.stop()
                app.LOG_DIR = original_log_dir


if __name__ == "__main__":
    unittest.main()
