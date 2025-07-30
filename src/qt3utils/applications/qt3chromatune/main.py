import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

from chromatune import Chromatune


class ChromatuneApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SuperK CHROMATUNE Control")
        self.laser = None

        # Notebook: Manual vs. Scan
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=5, pady=5)

        self._build_manual_tab(nb)
        self._build_scan_tab(nb)

    # ── Manual Control Tab ─────────────────────────────────────────────────
    def _build_manual_tab(self, nb):
        tab = ttk.Frame(nb); nb.add(tab, text="Manual Control")

        # Connection & Emission
        row = ttk.Frame(tab, padding=5); row.pack(fill="x")
        ttk.Button(row, text="Connect",    command=self.connect).pack(side="left", padx=2)
        ttk.Button(row, text="Disconnect", command=self.disconnect).pack(side="left", padx=2)
        self.emit_var = tk.BooleanVar()
        ttk.Checkbutton(row, text="Emission On", variable=self.emit_var,
                        command=self.toggle_emission).pack(side="left", padx=10)

        # Shutter
        row = ttk.Frame(tab, padding=5); row.pack(fill="x")
        ttk.Label(row, text="Shutter:").pack(side="left")
        self.sh_cb = ttk.Combobox(row, values=["Closed","Open","Auto"], width=8)
        self.sh_cb.current(0); self.sh_cb.pack(side="left", padx=4)
        ttk.Button(row, text="Set", command=self.set_shutter).pack(side="left")

        # Power Mode
        row = ttk.Frame(tab, padding=5); row.pack(fill="x")
        ttk.Label(row, text="Power Mode:").pack(side="left")
        self.pm_cb = ttk.Combobox(row, values=["Manual","Max","Passive","Active","Tracker"], width=10)
        self.pm_cb.current(0); self.pm_cb.pack(side="left", padx=4)
        ttk.Button(row, text="Set", command=self.set_power_mode).pack(side="left")

        # ND Attenuation
        row = ttk.Frame(tab, padding=5); row.pack(fill="x")
        ttk.Label(row, text="ND Atten (dB):").pack(side="left")
        self.nd_entry = ttk.Entry(row, width=8); self.nd_entry.insert(0, "0.0")
        self.nd_entry.pack(side="left", padx=4)
        ttk.Button(row, text="Set", command=self.set_nd).pack(side="left")

        # Filter Settings
        fl = ttk.LabelFrame(tab, text="Filter (Center nm, BW nm, Power nW)", padding=5)
        fl.pack(fill="x", pady=5)
        self.center_e = ttk.Entry(fl, width=6); self.center_e.insert(0, "550.0")
        self.bw_e     = ttk.Entry(fl, width=6); self.bw_e.insert(0, "5.0")
        self.pwr_e    = ttk.Entry(fl, width=8); self.pwr_e.insert(0, "1000000")
        for lbl, w in [("Center:", self.center_e), ("BW:", self.bw_e), ("Power:", self.pwr_e)]:
            ttk.Label(fl, text=lbl).pack(side="left", padx=2)
            w.pack(side="left", padx=2)
        ttk.Button(fl, text="Set", command=self.set_filter).pack(side="left", padx=4)
        ttk.Button(fl, text="Get", command=self.get_filter).pack(side="left")
        self.filter_lbl = ttk.Label(fl, text="–––")
        self.filter_lbl.pack(side="left", padx=10)

        # Power Readout
        row = ttk.Frame(tab, padding=5); row.pack(fill="x")
        ttk.Button(row, text="Read Power", command=self.read_power).pack(side="left")
        self.power_lbl = ttk.Label(row, text="––– nW")
        self.power_lbl.pack(side="left", padx=4)

    # ── Scan Tab ──────────────────────────────────────────────────────────────
    def _build_scan_tab(self, nb):
        tab = ttk.Frame(nb); nb.add(tab, text="Wavelength Scan")

        # Start / Stop / Velocity / Mode / Step
        row = ttk.Frame(tab, padding=5); row.pack(fill="x")
        for lbl,var in [("Start λ:", "start"), ("Stop λ:", "stop"), ("Vel (nm/s):", "vel")]:
            ttk.Label(row, text=lbl).pack(side="left", padx=2)
            setattr(self, f"{var}_e", ttk.Entry(row, width=7))
            getattr(self, f"{var}_e").pack(side="left", padx=2)
        self.start_e.insert(0, "500.0")
        self.stop_e.insert(0,  "600.0")
        self.vel_e.insert(0,   "5.0")

        # Mode + Step
        row = ttk.Frame(tab, padding=5); row.pack(fill="x")
        self.scan_mode = tk.StringVar(value="continuous")
        ttk.Radiobutton(row, text="Continuous", variable=self.scan_mode, value="continuous",
                        command=self._toggle_step).pack(side="left", padx=4)
        ttk.Radiobutton(row, text="Stepped",    variable=self.scan_mode, value="stepped",
                        command=self._toggle_step).pack(side="left", padx=4)
        ttk.Label(row, text="Step (nm):").pack(side="left", padx=2)
        self.step_e = ttk.Entry(row, width=7); self.step_e.insert(0, "1.0")
        self.step_e.pack(side="left", padx=2)
        self.step_e.config(state="disabled")

        # Loop toggle
        row = ttk.Frame(tab, padding=5); row.pack(fill="x")
        self.loop_var = tk.BooleanVar()
        ttk.Checkbutton(row, text="Repeat until stopped",
                        variable=self.loop_var).pack(side="left")

        # Start / Stop buttons
        row = ttk.Frame(tab, padding=5); row.pack(fill="x")
        ttk.Button(row, text="Start Scan", command=self.start_scan).pack(side="left", padx=4)
        ttk.Button(row, text="Stop Scan",  command=self.stop_scan).pack(side="left", padx=4)

        # Status & Progress
        row = ttk.Frame(tab, padding=5); row.pack(fill="x")
        ttk.Label(row, text="Current λ:").pack(side="left")
        self.curr_lbl = ttk.Label(row, text="––– nm")
        self.curr_lbl.pack(side="left", padx=4)
        self.prog = ttk.Progressbar(row, length=200)
        self.prog.pack(side="left", padx=10)

    def _toggle_step(self):
        state = "normal" if self.scan_mode.get()=="stepped" else "disabled"
        self.step_e.config(state=state)

    # ── Connection & Manual Helpers ──────────────────────────────────────────

    def connect(self):
        try:
            self.laser = Chromatune()
            self.laser.open("USB0")
            messagebox.showinfo("Connected", "Laser connected.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def disconnect(self):
        if self.laser:
            self.laser.close()
            self.laser = None
            messagebox.showinfo("Disconnected", "Laser disconnected.")

    def toggle_emission(self):
        if not self.laser: return messagebox.showwarning("Warning","Connect first.")
        self.laser.set_emission(self.emit_var.get())

    def set_shutter(self):
        if not self.laser: return messagebox.showwarning("Warning","Connect first.")
        modes = {"Closed":0,"Open":1,"Auto":2}
        self.laser.set_shutter(modes[self.sh_cb.get()])

    def set_power_mode(self):
        if not self.laser: return messagebox.showwarning("Warning","Connect first.")
        self.laser.set_power_mode(self.pm_cb.current())

    def set_nd(self):
        if not self.laser: return messagebox.showwarning("Warning","Connect first.")
        try:
            val = float(self.nd_entry.get())
            self.laser.set_nd_attenuation(val)
        except ValueError:
            messagebox.showerror("Error","Invalid ND value.")

    def set_filter(self):
        if not self.laser: return messagebox.showwarning("Warning","Connect first.")
        try:
            c = float(self.center_e.get())
            b = float(self.bw_e.get())
            p = int(self.pwr_e.get())
            self.laser.set_filter(c, b, p)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def get_filter(self):
        if not self.laser: return messagebox.showwarning("Warning","Connect first.")
        c,b,p = self.laser.get_filter()
        self.filter_lbl.config(text=f"{c:.1f} nm, {b:.1f} nm, {p} nW")

    def read_power(self):
        if not self.laser: return messagebox.showwarning("Warning","Connect first.")
        p = self.laser.get_photodiode_power()
        self.power_lbl.config(text=f"{p:.1f} nW")

    # ── Scan Helpers ─────────────────────────────────────────────────────────

    def start_scan(self):
        if not self.laser: return messagebox.showwarning("Warning","Connect first.")
        try:
            s = float(self.start_e.get())
            e = float(self.stop_e.get())
            v = float(self.vel_e.get())
            mode = self.scan_mode.get()
            step = float(self.step_e.get()) if mode=="stepped" else None
        except ValueError:
            return messagebox.showerror("Error","Invalid scan params.")
        total = abs(e - s)
        self.prog["value"] = 0

        def worker():
            curr = s
            direction = 1 if e>=s else -1
            dt = 0.1
            step_c = v*dt*direction
            first = True
            while first or (self.loop_var.get() and not stop_event.is_set()):
                first = False
                curr = s
                while (direction>0 and curr<=e) or (direction<0 and curr>=e):
                    if stop_event.is_set(): return
                    self.laser.set_wavelength(curr)
                    self.after(0, lambda c=curr: self._update_scan(c, s, e))
                    curr += (step_c if mode=="continuous" else step*direction)
                    time.sleep(dt if mode=="continuous" else abs(step)/v)
                # ensure endpoint
                self.laser.set_wavelength(e)
                self.after(0, lambda c=e: self._update_scan(c, s, e))
            self.after(0, lambda: messagebox.showinfo("Scan","Complete"))

        stop_event = threading.Event()
        self._scan_stop = stop_event
        threading.Thread(target=worker, daemon=True).start()

    def stop_scan(self):
        if hasattr(self, "_scan_stop"):
            self._scan_stop.set()

    def _update_scan(self, current, start, stop):
        self.curr_lbl.config(text=f"{current:.2f} nm")
        self.prog["value"] = abs(current - start)/abs(stop-start)*100

if __name__ == "__main__":
    ChromatuneApp().mainloop()
