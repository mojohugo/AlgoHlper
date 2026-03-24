from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable


class InProcessTaskQueue:
    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="algohlper")

    def submit(self, fn: Callable[[], None]) -> None:
        self.executor.submit(fn)
