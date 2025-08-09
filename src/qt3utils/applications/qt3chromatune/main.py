import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Optional

# import your driver class (use the path/module name where you put it)
# from my_chromatune_driver import Chromatune
from chromatune import Chromatune   # <-- adjust import to your file/module


class ChromatuneGUI:
    def __init__(self, master: tk.Tk):
        self.master = master
        self.master.title("SuperK Chromatune Controller")
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

        # Device handle
        self.dev: Optional[Chromatune] = None
        self._status_job = None
        self._cached_wl = None
        self._last_spectrum = ([], [])

        # -------- Connection variables --------
        self.var_portname = tk.StringVar(value="superk")
        self.var_host_ip = tk.StringVar(value="192.168.0.209")
        self.var_host_port = tk.IntVar(value=10001)
        self.var_sys_ip = tk.StringVar(value="192.168.0.139")
        self.var_sys_port = tk.IntVar(value=10001)
        self.var_timeout = tk.IntVar(value=100)
        self.var_protocol = tk.IntVar(value=0)  # 0 TCP

        # -------- MAIN module variables --------
        self.var_emission = tk.BooleanVar(value=False)
        self.var_setup_mode = tk.IntVar(value=1)  # const power
        self.var_watchdog = tk.IntVar(value=0)
        self.var_power_permille = tk.IntVar(value=500)
        self.var_current_permille = tk.IntVar(value=0)

        # -------- FILTER module variables --------
        self.var_shutter_mode = tk.IntVar(value=2)   # auto
        self.var_power_mode = tk.IntVar(value=4)     # tracker
        self.var_center_nm = tk.DoubleVar(value=550.0)
        self.var_bw_nm = tk.DoubleVar(value=10.0)
        self.var_nd_db = tk.DoubleVar(value=0.0)

        # build UI
        self._build_ui()

    # ================= UI LAYOUT =================

    def _build_ui(self):
        pad = {"padx": 8, "pady": 6}

        # ---- Connection frame ----
        frm_conn = ttk.LabelFrame(self.master, text="Connection")
        frm_conn.grid(row=0, column=0, sticky="nsew", **pad)

        ttk.Label(frm_conn, text="Port name").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm_conn, textvariable=self.var_portname, width=12).grid(row=0, column=1, sticky="w", padx=4)

        ttk.Label(frm_conn, text="Local IP").grid(row=1, column=0, sticky="w")
        ttk.Entry(frm_conn, textvariable=self.var_host_ip, width=15).grid(row=1, column=1, sticky="w", padx=4)
        ttk.Label(frm_conn, text="Local Port").grid(row=1, column=2, sticky="e")
        ttk.Entry(frm_conn, textvariable=self.var_host_port, width=7).grid(row=1, column=3, sticky="w", padx=4)

        ttk.Label(frm_conn, text="Laser IP").grid(row=2, column=0, sticky="w")
        ttk.Entry(frm_conn, textvariable=self.var_sys_ip, width=15).grid(row=2, column=1, sticky="w", padx=4)
        ttk.Label(frm_conn, text="Laser Port").grid(row=2, column=2, sticky="e")
        ttk.Entry(frm_conn, textvariable=self.var_sys_port, width=7).grid(row=2, column=3, sticky="w", padx=4)

        ttk.Label(frm_conn, text="Timeout (ms)").grid(row=0, column=2, sticky="e")
        ttk.Entry(frm_conn, textvariable=self.var_timeout, width=7).grid(row=0, column=3, sticky="w", padx=4)

        btn_connect = ttk.Button(frm_conn, text="Connect", command=self.on_connect)
        btn_connect.grid(row=0, column=4, rowspan=2, sticky="nsew", padx=6)
        btn_disconnect = ttk.Button(frm_conn, text="Disconnect", command=self.on_disconnect)
        btn_disconnect.grid(row=2, column=4, sticky="nsew", padx=6)

        # ---- Main module frame ----
        frm_main = ttk.LabelFrame(self.master, text="Main Module")
        frm_main.grid(row=1, column=0, sticky="nsew", **pad)

        cb_emit = ttk.Checkbutton(frm_main, text="Emission ON", variable=self.var_emission,
                                  command=self.on_toggle_emission)
        cb_emit.grid(row=0, column=0, sticky="w")

        ttk.Label(frm_main, text="Setup mode").grid(row=0, column=1, sticky="e")
        cmb_setup = ttk.Combobox(frm_main, width=18, state="readonly",
                                 values=[
                                     "0: Const current",
                                     "1: Const power",
                                     "2: Ext mod current",
                                     "3: Ext mod power",
                                     "4: Power lock",
                                 ])
        cmb_setup.current(1)
        cmb_setup.bind("<<ComboboxSelected>>", self.on_set_setup_mode)
        cmb_setup.grid(row=0, column=2, padx=4)

        ttk.Label(frm_main, text="Watchdog (s)").grid(row=0, column=3, sticky="e")
        ttk.Entry(frm_main, textvariable=self.var_watchdog, width=6).grid(row=0, column=4, sticky="w")
        ttk.Button(frm_main, text="Set", command=self.on_set_watchdog).grid(row=0, column=5, padx=4)

        ttk.Label(frm_main, text="Power ‰").grid(row=1, column=0, sticky="e")
        ttk.Entry(frm_main, textvariable=self.var_power_permille, width=6).grid(row=1, column=1, sticky="w")
        ttk.Button(frm_main, text="Set", command=self.on_set_power_permille).grid(row=1, column=2, padx=4)

        ttk.Label(frm_main, text="Current ‰").grid(row=1, column=3, sticky="e")
        ttk.Entry(frm_main, textvariable=self.var_current_permille, width=6).grid(row=1, column=4, sticky="w")
        ttk.Button(frm_main, text="Set", command=self.on_set_current_permille).grid(row=1, column=5, padx=4)

        ttk.Button(frm_main, text="Reset Interlock", command=self.on_reset_interlock).grid(row=2, column=0, padx=4, pady=2)
        ttk.Button(frm_main, text="Disable Interlock", command=self.on_disable_interlock).grid(row=2, column=1, padx=4, pady=2)

        ttk.Button(frm_main, text="Refresh Status", command=self.refresh_status_once).grid(row=2, column=4, padx=4)
        self.lbl_status_main = ttk.Label(frm_main, text="status: —")
        self.lbl_status_main.grid(row=2, column=5, sticky="w")

        # ---- Filter module frame ----
        frm_f = ttk.LabelFrame(self.master, text="Optical Filter")
        frm_f.grid(row=2, column=0, sticky="nsew", **pad)

        ttk.Label(frm_f, text="Shutter").grid(row=0, column=0, sticky="e")
        cmb_shut = ttk.Combobox(frm_f, width=14, state="readonly",
                                values=["0: Closed", "1: Open", "2: Auto"])
        cmb_shut.current(2)
        cmb_shut.bind("<<ComboboxSelected>>", self.on_set_shutter_mode)
        cmb_shut.grid(row=0, column=1, padx=4)

        ttk.Label(frm_f, text="Power mode").grid(row=0, column=2, sticky="e")
        cmb_pwr = ttk.Combobox(frm_f, width=18, state="readonly",
                               values=[
                                   "0: Manual",
                                   "1: Max",
                                   "2: Passive",
                                   "3: Active",
                                   "4: Tracker",
                               ])
        cmb_pwr.current(4)
        cmb_pwr.bind("<<ComboboxSelected>>", self.on_set_power_mode)
        cmb_pwr.grid(row=0, column=3, padx=4)

        ttk.Label(frm_f, text="Center (nm)").grid(row=1, column=0, sticky="e")
        ttk.Entry(frm_f, textvariable=self.var_center_nm, width=8).grid(row=1, column=1, sticky="w")
        ttk.Label(frm_f, text="BW (nm)").grid(row=1, column=2, sticky="e")
        ttk.Entry(frm_f, textvariable=self.var_bw_nm, width=8).grid(row=1, column=3, sticky="w")
        ttk.Button(frm_f, text="Set Filter", command=self.on_set_filter).grid(row=1, column=4, padx=6)

        ttk.Label(frm_f, text="ND (dB)").grid(row=2, column=0, sticky="e")
        ttk.Entry(frm_f, textvariable=self.var_nd_db, width=8).grid(row=2, column=1, sticky="w")
        ttk.Button(frm_f, text="Set ND", command=self.on_set_nd).grid(row=2, column=2, padx=6)

        ttk.Button(frm_f, text="Refresh Filter Status", command=self.refresh_status_once).grid(row=2, column=4, padx=6)
        self.lbl_status_filter = ttk.Label(frm_f, text="status: —")
        self.lbl_status_filter.grid(row=2, column=5, sticky="w")

        # ---- Spectrum frame ----
        frm_s = ttk.LabelFrame(self.master, text="Spectrum")
        frm_s.grid(row=3, column=0, sticky="nsew", **pad)

        ttk.Button(frm_s, text="Read Full Spectrum", command=self.on_read_spectrum).grid(row=0, column=0, padx=4)
        ttk.Button(frm_s, text="Save CSV…", command=self.on_save_csv).grid(row=0, column=1, padx=4)
        self.lbl_spec_info = ttk.Label(frm_s, text="N=0")
        self.lbl_spec_info.grid(row=0, column=2, padx=6)

        self.canvas = tk.Canvas(frm_s, width=640, height=240, bg="white", highlightthickness=1, highlightbackground="#ccc")
        self.canvas.grid(row=1, column=0, columnspan=6, padx=4, pady=4, sticky="nsew")

        # grid stretch
        for r in range(4):
            self.master.grid_rowconfigure(r, weight=0)
        self.master.grid_rowconfigure(3, weight=1)
        self.master.grid_columnconfigure(0, weight=1)
        frm_s.grid_columnconfigure(5, weight=1)
        frm_s.grid_rowconfigure(1, weight=1)

    # ================= Event Handlers =================

    def on_connect(self):
        if self.dev is not None:
            messagebox.showinfo("Already connected", "Device is already connected.")
            return
        try:
            self.dev = Chromatune(
                port_name=self.var_portname.get().strip(),
                host_address=self.var_host_ip.get().strip(),
                host_port=int(self.var_host_port.get()),
                system_address=self.var_sys_ip.get().strip(),
                system_port=int(self.var_sys_port.get()),
                protocol_num=int(self.var_protocol.get()),
                ms_timeout=int(self.var_timeout.get()),
            )
            self._schedule_status_updates()
            messagebox.showinfo("Connected", "Successfully connected to Chromatune.")
        except Exception as e:
            self.dev = None
            messagebox.showerror("Connect failed", str(e))

    def on_disconnect(self):
        self._cancel_status_updates()
        try:
            if self.dev:
                self.dev.close()
                messagebox.showinfo("Disconnected", "Successfully disconnected to Chromatune.")
        finally:
            self.dev = None
            self._cached_wl = None
            self._last_spectrum = ([], [])
            self.canvas.delete("all")

    def on_close(self):
        self.on_disconnect()
        self.master.destroy()

    # ----- main module controls -----

    def on_toggle_emission(self):
        if not self.dev:
            return
        try:
            self.dev.set_emission(self.var_emission.get())
        except Exception as e:
            messagebox.showerror("Emission", str(e))

    def on_set_setup_mode(self, _event=None):
        if not self.dev:
            return
        try:
            self.dev.set_setup_mode(self.var_setup_mode.get())
        except Exception as e:
            messagebox.showerror("Setup mode", str(e))

    def on_set_watchdog(self):
        if not self.dev:
            return
        try:
            self.dev.set_watchdog_seconds(int(self.var_watchdog.get()))
        except Exception as e:
            messagebox.showerror("Watchdog", str(e))

    def on_set_power_permille(self):
        if not self.dev:
            return
        try:
            self.dev.set_power_level_permille(int(self.var_power_permille.get()))
        except Exception as e:
            messagebox.showerror("Power level", str(e))

    def on_set_current_permille(self):
        if not self.dev:
            return
        try:
            self.dev.set_current_level_permille(int(self.var_current_permille.get()))
        except Exception as e:
            messagebox.showerror("Current level", str(e))

    def on_reset_interlock(self):
        if not self.dev:
            return
        try:
            self.dev.reset_interlock()
        except Exception as e:
            messagebox.showerror("Interlock", str(e))

    def on_disable_interlock(self):
        if not self.dev:
            return
        try:
            self.dev.disable_interlock()
        except Exception as e:
            messagebox.showerror("Interlock", str(e))

    # ----- filter controls -----

    def on_set_shutter_mode(self, _event=None):
        if not self.dev:
            return
        try:
            self.dev.set_shutter_mode(self.var_shutter_mode.get())
        except Exception as e:
            messagebox.showerror("Shutter mode", str(e))

    def on_set_power_mode(self, _event=None):
        if not self.dev:
            return
        try:
            self.dev.set_power_mode(self.var_power_mode.get())
        except Exception as e:
            messagebox.showerror("Power mode", str(e))

    def on_set_filter(self):
        if not self.dev:
            return
        try:
            self.dev.set_filter(
                center_nm=float(self.var_center_nm.get()),
                bandwidth_nm=float(self.var_bw_nm.get()),
            )
            # new center/bw could change spectrum pixel mapping → refresh cache
            self._cached_wl = None
        except Exception as e:
            messagebox.showerror("Set filter", str(e))

    def on_set_nd(self):
        if not self.dev:
            return
        try:
            self.dev.set_nd_attenuation_db(float(self.var_nd_db.get()))
        except Exception as e:
            messagebox.showerror("ND attenuation", str(e))

    # ----- status -----

    def _schedule_status_updates(self):
        self._cancel_status_updates()
        self._status_job = self.master.after(500, self._status_tick)

    def _cancel_status_updates(self):
        if self._status_job:
            try:
                self.master.after_cancel(self._status_job)
            except Exception:
                pass
            self._status_job = None

    def _status_tick(self):
        self.refresh_status_once()
        self._status_job = self.master.after(1000, self._status_tick)

    def refresh_status_once(self):
        if not self.dev:
            return
        try:
            # main status
            bits = self.dev.get_status_bits()
            em_on = bool(bits & (1 << 0))
            self.var_emission.set(em_on)
            text_main = f"0x{bits:04X} (emission={'ON' if em_on else 'OFF'})"
            self.lbl_status_main.configure(text=text_main)
            # filter status
            b = self.dev.get_status_bits_filter()
            image_ready = bool(b & (1 << 10))
            shutter_open = bool(b & (1 << 0))
            text_filter = f"0x{b:08X} (img={'ready' if image_ready else '—'}, shutter={'open' if shutter_open else '—'})"
            self.lbl_status_filter.configure(text=text_filter)
        except Exception as e:
            self.lbl_status_main.configure(text=f"status err: {e}")
            self.lbl_status_filter.configure(text=f"status err: {e}")

    # ----- spectrum -----

    def on_read_spectrum(self):
        if not self.dev:
            return
        # run in background so UI doesn't freeze while waiting for image ready
        t = threading.Thread(target=self._read_spectrum_worker, daemon=True)
        t.start()

    def _read_spectrum_worker(self):
        try:
            # cache wavelengths once unless pixel count changed
            if self._cached_wl is None:
                self._cached_wl = self.dev.read_wavelengths_nm()
            wl, amp = self.dev.read_full_spectrum(refresh_wavelengths=False)
            self._last_spectrum = (wl, amp)
            self._draw_spectrum(wl, amp)
        except Exception as e:
            self.master.after(0, lambda: messagebox.showerror("Spectrum", str(e)))

    def _draw_spectrum(self, wl, amp):
        # simple autoscaled line plot on Tk canvas
        self.canvas.delete("all")
        w = int(self.canvas["width"])
        h = int(self.canvas["height"])
        n = min(len(wl), len(amp))
        self.lbl_spec_info.configure(text=f"N={n}")
        if n < 2:
            return
        xmin, xmax = min(wl), max(wl)
        ymin, ymax = min(amp), max(amp)
        if ymax == ymin:
            ymax = ymin + 1

        # axes
        margin = 32
        x0, y0 = margin, h - margin
        x1, y1 = w - margin, margin
        self.canvas.create_rectangle(x0, y1, x1, y0, outline="#999")

        # map helpers
        def xmap(x):
            return x0 + (x - xmin) * (x1 - x0) / (xmax - xmin) if xmax > xmin else x0

        def ymap(y):
            return y0 - (y - ymin) * (y0 - y1) / (ymax - ymin)

        # polyline (downsample if very dense)
        step = max(1, n // (x1 - x0))
        pts = []
        for i in range(0, n, step):
            pts.extend([xmap(wl[i]), ymap(amp[i])])
        if len(pts) >= 4:
            self.canvas.create_line(*pts, width=1)

        # labels
        self.canvas.create_text(x0, y1 - 12, anchor="w", text=f"{xmin:.2f} nm")
        self.canvas.create_text(x1, y1 - 12, anchor="e", text=f"{xmax:.2f} nm")
        self.canvas.create_text(x0 - 4, y1, anchor="ne", text=f"{int(ymax)}")
        self.canvas.create_text(x0 - 4, y0, anchor="se", text=f"{int(ymin)}")

    # ----- export -----

    def on_save_csv(self):
        wl, amp = self._last_spectrum
        if not wl or not amp:
            messagebox.showinfo("Save CSV", "No spectrum to save yet.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("wavelength_nm,amplitude\n")
                for x, y in zip(wl, amp):
                    f.write(f"{x:.6f},{y}\n")
            messagebox.showinfo("Save CSV", f"Saved {len(wl)} points to {path}")
        except Exception as e:
            messagebox.showerror("Save CSV", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = ChromatuneGUI(root)
    root.mainloop()
