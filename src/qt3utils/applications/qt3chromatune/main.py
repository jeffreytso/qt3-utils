import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from chromatune import Chromatune  # your Chromatune wrapper


class ChromatuneApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SuperK CHROMATUNE Control")
        self.laser = None

        # ── Manual Control Section ──────────────────────────────────────────
        man = ttk.LabelFrame(self, text="Manual Control", padding=5)
        man.pack(fill="x", padx=5, pady=5)

        # Connection & Emission
        row = ttk.Frame(man, padding=2); row.pack(fill="x")
        ttk.Button(row, text="Connect",    command=self.connect).pack(side="left", padx=2)
        ttk.Button(row, text="Disconnect", command=self.disconnect).pack(side="left", padx=2)
        self.emit_var = tk.BooleanVar()
        ttk.Checkbutton(row, text="Emission On", variable=self.emit_var,
                        command=self.toggle_emission).pack(side="left", padx=10)

        # Shutter
        row = ttk.Frame(man, padding=2); row.pack(fill="x")
        ttk.Label(row, text="Shutter:").pack(side="left")
        self.sh_cb = ttk.Combobox(row, values=["Closed","Open","Auto"], width=8)
        self.sh_cb.current(0); self.sh_cb.pack(side="left", padx=4)
        ttk.Button(row, text="Set", command=self.set_shutter).pack(side="left")

        # Power Mode
        row = ttk.Frame(man, padding=2); row.pack(fill="x")
        ttk.Label(row, text="Power Mode:").pack(side="left")
        self.pm_cb = ttk.Combobox(row,
            values=["Manual","Max","Passive","Active","Tracker"], width=10)
        self.pm_cb.current(0); self.pm_cb.pack(side="left", padx=4)
        ttk.Button(row, text="Set", command=self.set_power_mode).pack(side="left")

        # ND Attenuation
        row = ttk.Frame(man, padding=2); row.pack(fill="x")
        ttk.Label(row, text="ND Atten (dB):").pack(side="left")
        self.nd_entry = ttk.Entry(row, width=8); self.nd_entry.insert(0, "0.0")
        self.nd_entry.pack(side="left", padx=4)
        ttk.Button(row, text="Set", command=self.set_nd).pack(side="left")

        # Filter Settings
        fl = ttk.LabelFrame(man, text="Filter Setting", padding=5)
        fl.pack(fill="x", pady=5)
        self.center_e = ttk.Entry(fl, width=6); self.center_e.insert(0, "550.0")
        self.bw_e     = ttk.Entry(fl, width=6); self.bw_e.insert(0, "5.0")
        self.pwr_e    = ttk.Entry(fl, width=8); self.pwr_e.insert(0, "1000000")
        for lbl, w in [("Center nm:", self.center_e),
                       ("BW nm:",     self.bw_e),
                       ("Power nW:",  self.pwr_e)]:
            ttk.Label(fl, text=lbl).pack(side="left", padx=2)
            w.pack(side="left", padx=2)
        ttk.Button(fl, text="Set", command=self.set_filter).pack(side="left", padx=4)
        ttk.Button(fl, text="Get", command=self.get_filter).pack(side="left")
        self.filter_lbl = ttk.Label(fl, text="–––"); self.filter_lbl.pack(side="left", padx=10)

        # Power Readout
        row = ttk.Frame(man, padding=2); row.pack(fill="x")
        ttk.Button(row, text="Read Power", command=self.read_power).pack(side="left")
        self.power_lbl = ttk.Label(row, text="––– nW"); self.power_lbl.pack(side="left", padx=4)


        # ── Scan Control + Live Plots Section ────────────────────────────────
        scan = ttk.LabelFrame(self, text="Wavelength Scan + Live Plots", padding=5)
        scan.pack(fill="both", expand=True, padx=5, pady=5)

        # 1) Scan Controls
        ctrl = ttk.Frame(scan, padding=2)
        ctrl.pack(side="top", fill="x")

        # Start/Stop/Velocity
        for lbl,var in [("Start λ:", "start"), ("Stop λ:", "stop"), ("Vel nm/s:", "vel")]:
            ttk.Label(ctrl, text=lbl).pack(side="left", padx=2)
            setattr(self, f"{var}_e", ttk.Entry(ctrl, width=7))
            getattr(self, f"{var}_e").pack(side="left", padx=2)
        self.start_e.insert(0, "500.0")
        self.stop_e.insert(0,  "600.0")
        self.vel_e.insert(0,   "5.0")

        # Mode + Step size
        self.scan_mode = tk.StringVar(value="continuous")
        for text,val in [("Continuous","continuous"), ("Stepped","stepped")]:
            ttk.Radiobutton(ctrl, text=text, variable=self.scan_mode, value=val,
                            command=self._toggle_step).pack(side="left", padx=4)
        ttk.Label(ctrl, text="Step nm:").pack(side="left", padx=2)
        self.step_e = ttk.Entry(ctrl, width=7); self.step_e.insert(0, "1.0")
        self.step_e.pack(side="left", padx=2)
        self.step_e.config(state="disabled")

        # Loop until stopped
        self.loop_var = tk.BooleanVar()
        ttk.Checkbutton(ctrl, text="Repeat until stopped",
                        variable=self.loop_var).pack(side="left", padx=10)

        # Start/Stop buttons
        ttk.Button(ctrl, text="Start Scan", command=self.start_scan).pack(side="left", padx=4)
        ttk.Button(ctrl, text="Stop Scan",  command=self.stop_scan).pack(side="left", padx=4)

        # Current λ + Progress
        self.curr_lbl = ttk.Label(ctrl, text="Current λ: ––– nm")
        self.curr_lbl.pack(side="left", padx=10)
        self.prog = ttk.Progressbar(ctrl, length=150)
        self.prog.pack(side="left", padx=10)


        # 2) Live Plots (Wavelength vs Time, Power vs Time)
        fig = Figure(figsize=(6,3), tight_layout=True)
        self.ax_wl    = fig.add_subplot(121)
        self.ax_power = fig.add_subplot(122)
        self.ax_wl.set_title("Wavelength vs Time")
        self.ax_wl.set_xlabel("t (s)"); self.ax_wl.set_ylabel("λ (nm)")
        self.ax_power.set_title("Power vs Time")
        self.ax_power.set_xlabel("t (s)"); self.ax_power.set_ylabel("Power (nW)")

        self.canvas = FigureCanvasTkAgg(fig, master=scan)
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)

        # Prepare data storage and line objects
        self.scan_times  = []
        self.scan_wls    = []
        self.scan_powers = []
        self.line_wl,    = self.ax_wl.plot([], [], '-o')
        self.line_power, = self.ax_power.plot([], [], '-o')


    # ── Helper Methods ────────────────────────────────────────────────────────

    def _toggle_step(self):
        state = "normal" if self.scan_mode.get()=="stepped" else "disabled"
        self.step_e.config(state=state)

    def connect(self):
        try:
            self.laser = Chromatune()
            self.laser.open_ethernet("192.168.0.139")  # or your IP/port
            messagebox.showinfo("Connected", "Laser connected.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def disconnect(self):
        if self.laser:
            self.laser.close()
            self.laser = None
            messagebox.showinfo("Disconnected", "Laser disconnected.")

    def toggle_emission(self):
        if not self.laser:
            return messagebox.showwarning("Warning","Connect first.")
        self.laser.set_emission(self.emit_var.get())

    def set_shutter(self):
        if not self.laser:
            return messagebox.showwarning("Warning","Connect first.")
        modes = {"Closed":0,"Open":1,"Auto":2}
        self.laser.set_shutter(modes[self.sh_cb.get()])

    def set_power_mode(self):
        if not self.laser:
            return messagebox.showwarning("Warning","Connect first.")
        self.laser.set_power_mode(self.pm_cb.current())

    def set_nd(self):
        if not self.laser:
            return messagebox.showwarning("Warning","Connect first.")
        try:
            v = float(self.nd_entry.get())
            self.laser.set_nd_attenuation(v)
        except ValueError:
            messagebox.showerror("Error","Invalid ND value.")

    def set_filter(self):
        if not self.laser:
            return messagebox.showwarning("Warning","Connect first.")
        try:
            c = float(self.center_e.get())
            b = float(self.bw_e.get())
            p = int(self.pwr_e.get())
            self.laser.set_filter(c, b, p)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def get_filter(self):
        if not self.laser:
            return messagebox.showwarning("Warning","Connect first.")
        c,b,p = self.laser.get_filter()
        self.filter_lbl.config(text=f"{c:.1f} nm, {b:.1f} nm, {p} nW")

    def read_power(self):
        if not self.laser:
            return messagebox.showwarning("Warning","Connect first.")
        p = self.laser.get_photodiode_power()
        self.power_lbl.config(text=f"{p:.1f} nW")

    def start_scan(self):
        if not self.laser:
            return messagebox.showwarning("Warning","Connect first.")
        try:
            s    = float(self.start_e.get())
            e    = float(self.stop_e.get())
            v    = float(self.vel_e.get())
            mode = self.scan_mode.get()
            step = float(self.step_e.get()) if mode=="stepped" else None
        except ValueError:
            return messagebox.showerror("Error","Invalid scan params.")

        # Clear previous data & reset plots
        self.scan_times.clear()
        self.scan_wls.clear()
        self.scan_powers.clear()
        self.line_wl.set_data([], [])
        self.line_power.set_data([], [])
        self.canvas.draw()
        self._t0 = time.time()
        self.prog["value"] = 0

        # Fixed bandwidth & power
        bw = float(self.bw_e.get())
        pw = int(self.pwr_e.get())

        stop_event = threading.Event()
        self._scan_stop = stop_event

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
                    if stop_event.is_set():
                        return
                    # drive the filter center + fixed BW/power
                    self.laser.set_filter(curr, bw, pw)
                    self._do_step(curr)
                    # update progress UI
                    self.after(0, lambda c=curr: self._update_scan(c, s, e))
                    curr += (step_c if mode=="continuous" else step*direction)
                    time.sleep(dt if mode=="continuous" else abs(step)/v)
                # ensure endpoint
                self.laser.set_filter(e, bw, pw)
                self._do_step(e)
                self.after(0, lambda c=e: self._update_scan(c, s, e))
            self.after(0, lambda: messagebox.showinfo("Scan","Complete"))

        threading.Thread(target=worker, daemon=True).start()

    def stop_scan(self):
        if hasattr(self, "_scan_stop"):
            self._scan_stop.set()

    def _do_step(self, current_nm: float):
        """Record and plot a step (called in worker thread)."""
        elapsed = time.time() - self._t0
        power   = self.laser.get_photodiode_power()

        self.scan_times.append(elapsed)
        self.scan_wls.append(current_nm)
        self.scan_powers.append(power)

        self.after(0, self._update_plots)

    def _update_plots(self):
        """Update both live plots on the main thread."""
        self.line_wl.set_data(self.scan_times, self.scan_wls)
        self.line_power.set_data(self.scan_times, self.scan_powers)

        self.ax_wl.relim();    self.ax_wl.autoscale_view()
        self.ax_power.relim(); self.ax_power.autoscale_view()

        self.canvas.draw()

    def _update_scan(self, current, start, stop):
        """Update Current λ label and progress bar."""
        self.curr_lbl.config(text=f"Current λ: {current:.2f} nm")
        self.prog["value"] = abs(current - start)/abs(stop-start)*100


if __name__ == "__main__":
    ChromatuneApp().mainloop()
