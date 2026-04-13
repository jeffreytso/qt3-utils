"""Tkinter control panel for Newport-style TTL flipper mounts on NI-DAQ digital outputs."""
from __future__ import annotations

import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, List, Optional

from qt3utils.hardware.nidaq.digitaloutputs import FlipperMountController, FlipperMountError


class FlipperMirrorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("Qt3 Mirror — Flipper DAQ")
        root.resizable(False, False)
        self._controller: Optional[FlipperMountController] = None
        self._n_lines: int = 4
        self._busy = False

        self._device_var = tk.StringVar(value="Dev1")
        self._port_var = tk.StringVar(value="port0")
        self._line_start_var = tk.StringVar(value="0")
        self._n_lines_var = tk.StringVar(value="4")
        self._settle_var = tk.StringVar(value="500")

        self._status_var = tk.StringVar(value="Disconnected.")
        self._flipper_state_vars: List[tk.StringVar] = []

        self._build()
        root.protocol("WM_DELETE_WINDOW", self._on_quit)

    def _build(self) -> None:
        pad = {"padx": 8, "pady": 4}
        outer = ttk.Frame(self.root, padding="10")
        outer.grid(row=0, column=0, sticky="nsew")

        conn = ttk.LabelFrame(outer, text="DAQ connection", padding="8")
        conn.grid(row=0, column=0, sticky="ew", **pad)
        for c in range(4):
            conn.columnconfigure(c, weight=1)

        ttk.Label(conn, text="Device").grid(row=0, column=0, sticky="w")
        ttk.Entry(conn, textvariable=self._device_var, width=12).grid(
            row=0, column=1, sticky="ew", padx=(4, 8)
        )
        ttk.Label(conn, text="Port").grid(row=0, column=2, sticky="w")
        ttk.Entry(conn, textvariable=self._port_var, width=10).grid(
            row=0, column=3, sticky="ew", padx=(4, 0)
        )

        ttk.Label(conn, text="First line").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(conn, textvariable=self._line_start_var, width=6).grid(
            row=1, column=1, sticky="w", padx=(4, 8), pady=(6, 0)
        )
        ttk.Label(conn, text="# lines").grid(row=1, column=2, sticky="w", pady=(6, 0))
        ttk.Entry(conn, textvariable=self._n_lines_var, width=6).grid(
            row=1, column=3, sticky="w", padx=(4, 0), pady=(6, 0)
        )

        btn_row = ttk.Frame(conn)
        btn_row.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        self._connect_btn = ttk.Button(btn_row, text="Connect", command=self._connect)
        self._connect_btn.pack(side=tk.LEFT, padx=(0, 6))
        self._disconnect_btn = ttk.Button(
            btn_row, text="Disconnect", command=self._disconnect, state=tk.DISABLED
        )
        self._disconnect_btn.pack(side=tk.LEFT, padx=(0, 6))
        self._sync_btn = ttk.Button(
            btn_row,
            text="Initialize (sync to UP)",
            command=self._sync_all_up,
            state=tk.DISABLED,
        )
        self._sync_btn.pack(side=tk.LEFT)

        settle_row = ttk.Frame(conn)
        settle_row.grid(row=3, column=0, columnspan=4, sticky="w", pady=(8, 0))
        ttk.Label(settle_row, text="Settle time (ms) after each command").pack(
            side=tk.LEFT
        )
        ttk.Spinbox(
            settle_row,
            from_=0,
            to=60000,
            textvariable=self._settle_var,
            width=8,
        ).pack(side=tk.LEFT, padx=(6, 0))

        ctrl = ttk.LabelFrame(outer, text="Flippers (open-loop — no position readback)", padding="8")
        ctrl.grid(row=1, column=0, sticky="ew", **pad)

        bulk = ttk.Frame(ctrl)
        bulk.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 8))
        self._all_up_btn = ttk.Button(
            bulk, text="All up", command=self._all_up, state=tk.DISABLED
        )
        self._all_up_btn.pack(side=tk.LEFT, padx=(0, 6))
        self._all_down_btn = ttk.Button(
            bulk, text="All down", command=self._all_down, state=tk.DISABLED
        )
        self._all_down_btn.pack(side=tk.LEFT)

        self._toggle_btns: List[ttk.Button] = []
        n_default = 4
        for i in range(n_default):
            sv = tk.StringVar(value="—")
            self._flipper_state_vars.append(sv)
            row = 1 + i
            ttk.Label(ctrl, text=f"Flipper {i + 1}").grid(
                row=row, column=0, sticky="w", pady=2
            )
            ttk.Label(ctrl, textvariable=sv, width=14).grid(
                row=row, column=1, sticky="w", padx=(8, 8), pady=2
            )
            b = ttk.Button(
                ctrl,
                text="Toggle",
                command=lambda idx=i: self._toggle(idx),
                state=tk.DISABLED,
            )
            b.grid(row=row, column=2, sticky="e", pady=2)
            self._toggle_btns.append(b)

        status = ttk.Label(outer, textvariable=self._status_var, wraplength=420)
        status.grid(row=2, column=0, sticky="ew", **pad)

    def _parse_int(self, var: tk.StringVar, label: str) -> int:
        raw = var.get().strip()
        try:
            return int(raw, 10)
        except ValueError as e:
            raise ValueError(f"{label} must be an integer (got {raw!r})") from e

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._update_widget_states()

    def _update_widget_states(self) -> None:
        c = self._controller is not None and self._controller.connected
        busy = self._busy
        self._connect_btn.configure(state=tk.DISABLED if busy or c else tk.NORMAL)
        self._disconnect_btn.configure(state=tk.DISABLED if busy or not c else tk.NORMAL)
        bulk_state = tk.DISABLED if busy or not c else tk.NORMAL
        self._sync_btn.configure(state=bulk_state)
        self._all_up_btn.configure(state=bulk_state)
        self._all_down_btn.configure(state=bulk_state)
        for i, b in enumerate(self._toggle_btns):
            if busy or not c or i >= self._n_lines:
                b.configure(state=tk.DISABLED)
            else:
                b.configure(state=tk.NORMAL)

    def _refresh_flipper_labels(self) -> None:
        if not self._controller or not self._controller.connected:
            for sv in self._flipper_state_vars:
                sv.set("—")
            return
        levels = self._controller.levels
        for i, sv in enumerate(self._flipper_state_vars):
            if i >= self._n_lines:
                sv.set("n/a")
            elif i < len(levels):
                sv.set("UP (high)" if levels[i] else "DOWN (low)")
            else:
                sv.set("—")

    def _refresh_status(self) -> None:
        if self._controller and self._controller.connected:
            self._status_var.set(f"Connected: {self._controller.channel_string}")
        else:
            self._status_var.set("Disconnected.")

    def _connect(self) -> None:
        if self._busy:
            return
        try:
            device = self._device_var.get().strip() or "Dev1"
            port = self._port_var.get().strip() or "port0"
            line_start = self._parse_int(self._line_start_var, "First line")
            n_lines = self._parse_int(self._n_lines_var, "# lines")
            if n_lines < 1 or n_lines > 32:
                raise ValueError("# lines must be between 1 and 32")
            if line_start < 0:
                raise ValueError("First line must be non-negative")
        except ValueError as e:
            messagebox.showerror("Flipper DAQ", str(e))
            return

        if n_lines != len(self._toggle_btns):
            messagebox.showerror(
                "Flipper DAQ",
                f"This panel has {len(self._toggle_btns)} flipper rows; set # lines to "
                f"{len(self._toggle_btns)} or change the GUI.",
            )
            return

        self._set_busy(True)

        def work() -> None:
            err: Optional[BaseException] = None
            ctrl: Optional[FlipperMountController] = None
            try:
                ctrl = FlipperMountController(
                    device_name=device,
                    port=port,
                    line_start=line_start,
                    n_lines=n_lines,
                )
                ctrl.connect()
            except FlipperMountError as e:
                err = e
            except Exception as e:
                err = e

            def apply() -> None:
                self._set_busy(False)
                if err is not None:
                    messagebox.showerror("Flipper DAQ", str(err))
                    self._controller = None
                else:
                    self._controller = ctrl
                    self._n_lines = n_lines
                self._refresh_flipper_labels()
                self._refresh_status()
                self._update_widget_states()

            self.root.after(0, apply)

        threading.Thread(target=work, daemon=True).start()

    def _disconnect(self) -> None:
        if self._controller is not None:
            try:
                self._controller.close()
            except Exception:
                pass
            self._controller = None
        self._refresh_flipper_labels()
        self._refresh_status()
        self._update_widget_states()

    def _on_quit(self) -> None:
        self._disconnect()
        self.root.destroy()

    def _settle_ms(self) -> int:
        try:
            v = int(float(self._settle_var.get()))
            return max(0, v)
        except (TypeError, ValueError):
            return 500

    def _daq_call(self, op: Callable[[], None]) -> None:
        if self._busy or self._controller is None:
            return
        self._set_busy(True)

        def work() -> None:
            err: Optional[BaseException] = None
            try:
                op()
            except FlipperMountError as e:
                err = e
            except Exception as e:
                err = e
            time.sleep(self._settle_ms() / 1000.0)

            def finish() -> None:
                self._refresh_flipper_labels()
                self._set_busy(False)
                if err is not None:
                    messagebox.showerror("Flipper DAQ", str(err))
                self._update_widget_states()

            self.root.after(0, finish)

        threading.Thread(target=work, daemon=True).start()

    def _sync_all_up(self) -> None:
        if self._controller is None:
            return
        self._daq_call(self._controller.sync_all_up)

    def _all_up(self) -> None:
        if self._controller is None:
            return
        self._daq_call(self._controller.all_up)

    def _all_down(self) -> None:
        if self._controller is None:
            return
        self._daq_call(self._controller.all_down)

    def _toggle(self, index: int) -> None:
        if self._controller is None:
            return
        self._daq_call(lambda: self._controller.toggle(index))


def main() -> None:
    root = tk.Tk()
    btn_font = ("Segoe UI", 9) if sys.platform == "win32" else ("TkDefaultFont", 9)
    root.option_add("*TButton*Font", btn_font)
    root.option_add("*TLabel*Font", btn_font)
    FlipperMirrorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
