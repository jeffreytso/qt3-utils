"""NI-DAQ digital output control for edge-triggered flipper mounts (e.g. Newport 889x)."""
from __future__ import annotations

import threading
import time
from typing import List, Optional, Sequence

import nidaqmx


class FlipperMountError(Exception):
    """Raised when flipper DAQ operations fail."""


class FlipperMountController:
    """
    Drives one digital port (multiple lines) with software-timed writes.

    Tracks last commanded line levels so only intentional transitions occur.
    After connect, all lines are driven high once (rising edge on any line that
    was low) so software state matches the usual "UP" idle level.
    """

    def __init__(
        self,
        device_name: str = "Dev1",
        port: str = "port0",
        line_start: int = 0,
        n_lines: int = 4,
    ) -> None:
        if n_lines < 1:
            raise ValueError("n_lines must be at least 1")
        self._device_name = device_name
        self._port = port
        self._line_start = line_start
        self._n = n_lines
        last = line_start + n_lines - 1
        self._channel_string = f"{device_name}/{port}/line{line_start}:{last}"
        self._task: Optional[nidaqmx.Task] = None
        self._levels: List[bool] = [False] * n_lines
        self._lock = threading.Lock()

    @property
    def channel_string(self) -> str:
        return self._channel_string

    @property
    def connected(self) -> bool:
        return self._task is not None

    @property
    def levels(self) -> List[bool]:
        """Copy of last commanded line levels (True = high, UP for typical TTL flipper inputs)."""
        with self._lock:
            return list(self._levels)

    def connect(self) -> None:
        with self._lock:
            if self._task is not None:
                return
            task = None
            try:
                task = nidaqmx.Task()
                task.do_channels.add_do_chan(self._channel_string)
                levels = [True] * self._n
                task.write(levels)
                self._task = task
                self._levels = levels
                task = None
            except Exception as e:
                if task is not None:
                    try:
                        task.close()
                    except Exception:
                        pass
                raise FlipperMountError(
                    f"Failed to connect to {self._channel_string}: {e}"
                ) from e

    def close(self) -> None:
        with self._lock:
            if self._task is None:
                return
            t = self._task
            self._task = None
            try:
                t.stop()
            except Exception:
                pass
            try:
                t.close()
            except Exception:
                pass

    def write_levels(self, levels: Sequence[bool]) -> None:
        if len(levels) != self._n:
            raise ValueError(f"expected {self._n} booleans, got {len(levels)}")
        lst = [bool(x) for x in levels]
        with self._lock:
            if self._task is None:
                raise FlipperMountError("Not connected")
            try:
                self._task.write(lst)
                self._levels = lst
            except Exception as e:
                raise FlipperMountError(f"write failed: {e}") from e

    def toggle(self, index: int) -> None:
        if index < 0 or index >= self._n:
            raise IndexError(f"flipper index out of range: {index}")
        with self._lock:
            if self._task is None:
                raise FlipperMountError("Not connected")
            new = list(self._levels)
            new[index] = not new[index]
            try:
                self._task.write(new)
                self._levels = new
            except Exception as e:
                raise FlipperMountError(f"toggle failed: {e}") from e

    def all_up(self) -> None:
        self.write_levels([True] * self._n)

    def all_down(self) -> None:
        self.write_levels([False] * self._n)

    def sync_all_up(self, pulse_low_ms: float = 15.0, pulse_high_ms: float = 15.0) -> None:
        """
        For each line, pulse that line low then high while holding other lines
        at their current commanded values, ending with all lines high.

        Ensures each line sees a rising edge even if it was already high.
        """
        low_s = pulse_low_ms / 1000.0
        high_s = pulse_high_ms / 1000.0
        with self._lock:
            if self._task is None:
                raise FlipperMountError("Not connected")
            try:
                for i in range(self._n):
                    bits = list(self._levels)
                    bits[i] = False
                    self._task.write(bits)
                    self._levels = bits
                    time.sleep(low_s)
                    bits = list(self._levels)
                    bits[i] = True
                    self._task.write(bits)
                    self._levels = bits
                    time.sleep(high_s)
            except Exception as e:
                raise FlipperMountError(f"sync_all_up failed: {e}") from e
