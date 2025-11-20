import tkinter as tk
from tkinter import ttk, messagebox
import pyvisa
import time
import threading

# ==============================================================================
# CONFIGURATION
# ==============================================================================
SWITCH_IP = '192.168.0.94'
SWITCH_PORT = 5020

# Using Socket Port 5000 based on tests
LASER_CONFIG = [
    {'ip': '192.168.0.96', 'switch_port': 1, 'socket_port': 5000},
    {'ip': '192.168.0.99', 'switch_port': 2, 'socket_port': 5000},
    # {'ip': '192.168.0.97', 'switch_port': 3, 'socket_port': 5000},
]

# ==============================================================================
# BACKEND CONTROLLER
# ==============================================================================
class SantecController:
    def __init__(self):
        self.rm = pyvisa.ResourceManager()
        self.switch = None
        self.lasers = []
        self.active_laser = None
        self.is_connected = False

    def connect(self):
        try:
            # 1. Connect Switch
            switch_addr = f'TCPIP0::{SWITCH_IP}::{SWITCH_PORT}::SOCKET'
            self.switch = self.rm.open_resource(switch_addr)
            self.switch.write_termination = '\r'
            self.switch.read_termination = '\r'
            self.switch.timeout = 3000
            self.switch.query("*IDN?") 

            # 2. Connect Lasers
            self.lasers = []
            for cfg in LASER_CONFIG:
                addr = f"TCPIP0::{cfg['ip']}::{cfg['socket_port']}::SOCKET"
                try:
                    inst = self.rm.open_resource(addr)
                    inst.write_termination = '\r'
                    inst.read_termination = '\r'
                    inst.timeout = 3000
                    inst.write(":SYST:COMM:COD 0") # Force Legacy Mode
                    
                    idn = inst.query("*IDN?").strip()
                    min_wav = float(inst.query(":WAV:MIN?"))
                    max_wav = float(inst.query(":WAV:MAX?"))
                    
                    self.lasers.append({
                        'obj': inst,
                        'ip': cfg['ip'],
                        'port': cfg['switch_port'],
                        'min': min_wav,
                        'max': max_wav,
                        'idn': idn
                    })
                except Exception as e:
                    print(f"Failed to connect to laser {cfg['ip']}: {e}")

            if not self.lasers:
                raise Exception("No lasers connected successfully.")

            self.is_connected = True
            return f"Connected: Switch + {len(self.lasers)} Lasers"

        except Exception as e:
            self.is_connected = False
            raise e

    def _select_best_laser(self, target_nm):
        candidates = [l for l in self.lasers if l['min'] <= target_nm <= l['max']]
        if not candidates: return None
        if len(candidates) == 1: return candidates[0]

        best_laser = None
        max_edge_dist = -1.0

        for laser in candidates:
            dist = min(target_nm - laser['min'], laser['max'] - target_nm)
            if dist > max_edge_dist:
                max_edge_dist = dist
                best_laser = laser
        return best_laser

    def check_valid_range(self, start_nm, end_nm):
        start_valid = any(l['min'] <= start_nm <= l['max'] for l in self.lasers)
        end_valid = any(l['min'] <= end_nm <= l['max'] for l in self.lasers)
        return start_valid and end_valid

    def set_wavelength(self, target_nm):
        chosen = self._select_best_laser(target_nm)
        if not chosen: raise ValueError(f"{target_nm}nm is out of range.")

        if self.active_laser != chosen:
            if self.active_laser: self.active_laser['obj'].write(":POW:STAT 0")
            self.switch.write(f"CH {chosen['port']}")
            time.sleep(0.2) 
            self.active_laser = chosen

        inst = chosen['obj']
        inst.write(f":WAV {target_nm}")
        if inst.query(":POW:STAT?").strip() == "0": inst.write(":POW:STAT 1")

    def close(self):
        for laser in self.lasers:
            try: laser['obj'].write(":POW:STAT 0"); laser['obj'].close()
            except: pass
        if self.switch:
            try: self.switch.close()
            except: pass

# ==============================================================================
# FRONTEND GUI
# ==============================================================================
class LaserSweepApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Santec Laser Controller + Subpixels")
        self.ctrl = SantecController()
        self.stop_flag = False
        self.is_running = False
        self._build_gui()

    def _build_gui(self):
        # Connection
        conn_frame = tk.LabelFrame(self.root, text="Connection")
        conn_frame.pack(fill="x", padx=10, pady=5)
        self.btn_connect = tk.Button(conn_frame, text="Connect System", command=self.connect_hardware, bg="#dddddd")
        self.btn_connect.pack(side="left", padx=5, pady=5)
        self.lbl_status = tk.Label(conn_frame, text="Status: Disconnected", fg="red")
        self.lbl_status.pack(side="left", padx=5)

        # Manual Control
        manual_frame = tk.LabelFrame(self.root, text="Manual Control")
        manual_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(manual_frame, text="Set Wavelength (nm):").pack(side="left", padx=5)
        self.ent_manual_wav = tk.Entry(manual_frame, width=10)
        self.ent_manual_wav.pack(side="left", padx=5)
        self.btn_set_manual = tk.Button(manual_frame, text="Set", command=self.set_manual_wavelength, state="disabled")
        self.btn_set_manual.pack(side="left", padx=5)

        # Sweep Config
        sweep_frame = tk.LabelFrame(self.root, text="Sweep Configuration")
        sweep_frame.pack(fill="x", padx=10, pady=5)

        # Row 0: Range
        tk.Label(sweep_frame, text="Start (nm):").grid(row=0, column=0, sticky="e")
        self.ent_start = tk.Entry(sweep_frame, width=10); self.ent_start.grid(row=0, column=1)
        tk.Label(sweep_frame, text="End (nm):").grid(row=0, column=2, sticky="e")
        self.ent_end = tk.Entry(sweep_frame, width=10); self.ent_end.grid(row=0, column=3)

        # Row 1: Upsweep
        tk.Label(sweep_frame, text="Upsweep Time (s):").grid(row=1, column=0, sticky="e")
        self.ent_up_time = tk.Entry(sweep_frame, width=10); self.ent_up_time.grid(row=1, column=1)
        
        tk.Label(sweep_frame, text="Up Pixels:").grid(row=1, column=2, sticky="e")
        self.ent_up_pixels = tk.Entry(sweep_frame, width=10); self.ent_up_pixels.grid(row=1, column=3)
        
        tk.Label(sweep_frame, text="Up Subpixels:").grid(row=1, column=4, sticky="e")
        self.ent_up_sub = tk.Entry(sweep_frame, width=5); self.ent_up_sub.grid(row=1, column=5)
        self.ent_up_sub.insert(0, "1")

        # Row 2: Downsweep
        tk.Label(sweep_frame, text="Downsweep Time (s):").grid(row=2, column=0, sticky="e")
        self.ent_down_time = tk.Entry(sweep_frame, width=10); self.ent_down_time.grid(row=2, column=1)
        
        tk.Label(sweep_frame, text="Down Pixels:").grid(row=2, column=2, sticky="e")
        self.ent_down_pixels = tk.Entry(sweep_frame, width=10); self.ent_down_pixels.grid(row=2, column=3)

        tk.Label(sweep_frame, text="Down Subpixels:").grid(row=2, column=4, sticky="e")
        self.ent_down_sub = tk.Entry(sweep_frame, width=5); self.ent_down_sub.grid(row=2, column=5)
        self.ent_down_sub.insert(0, "1")

        # Row 3: Repeats
        tk.Label(sweep_frame, text="Scans:").grid(row=3, column=0, sticky="e")
        self.ent_scans = tk.Entry(sweep_frame, width=10); self.ent_scans.grid(row=3, column=1)
        tk.Label(sweep_frame, text="Delay (s):").grid(row=3, column=2, sticky="e")
        self.ent_delay = tk.Entry(sweep_frame, width=10); self.ent_delay.grid(row=3, column=3)

        for child in sweep_frame.winfo_children(): child.grid_configure(padx=5, pady=5)

        # Actions
        action_frame = tk.Frame(self.root)
        action_frame.pack(fill="x", padx=10, pady=10)
        self.btn_start = tk.Button(action_frame, text="START", bg="green", fg="white", font=("Arial", 10, "bold"), command=self.start_sweep_thread, state="disabled")
        self.btn_start.pack(side="left", fill="x", expand=True, padx=5)
        self.btn_stop = tk.Button(action_frame, text="STOP", bg="red", fg="white", font=("Arial", 10, "bold"), command=self.stop_sweep, state="disabled")
        self.btn_stop.pack(side="left", fill="x", expand=True, padx=5)

        self.txt_log = tk.Text(self.root, height=12, width=60)
        self.txt_log.pack(padx=10, pady=5)

    def log(self, msg):
        self.root.after(0, lambda: self.txt_log.insert(tk.END, msg + "\n"))
        self.root.after(0, lambda: self.txt_log.see(tk.END))

    def connect_hardware(self):
        try:
            msg = self.ctrl.connect()
            self.lbl_status.config(text=msg, fg="green")
            self.btn_connect.config(state="disabled")
            self.btn_set_manual.config(state="normal")
            self.btn_start.config(state="normal")
            self.log("Connected.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def set_manual_wavelength(self):
        try:
            val = float(self.ent_manual_wav.get())
            self.ctrl.set_wavelength(val)
            self.log(f"Manual Set: {val} nm")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def start_sweep_thread(self):
        try:
            start = float(self.ent_start.get())
            end = float(self.ent_end.get())
            if not self.ctrl.check_valid_range(start, end): raise ValueError("Range invalid.")
            
            self.sweep_params = {
                'start': start, 'end': end,
                'up_time': float(self.ent_up_time.get()),
                'up_pix': int(self.ent_up_pixels.get()),
                'up_sub': max(1, int(self.ent_up_sub.get())),
                'down_time': float(self.ent_down_time.get()),
                'down_pix': int(self.ent_down_pixels.get()),
                'down_sub': max(1, int(self.ent_down_sub.get())),
                'scans': int(self.ent_scans.get()),
                'delay': float(self.ent_delay.get())
            }
        except ValueError as e:
            messagebox.showerror("Input Error", str(e))
            return

        self.stop_flag = False
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        threading.Thread(target=self.run_sweep, daemon=True).start()

    def stop_sweep(self):
        self.stop_flag = True
        self.log("Stopping...")

    def run_sweep(self):
        p = self.sweep_params
        self.log(f"--- Starting Sweep ---")
        total_up = p['up_pix'] * p['up_sub']
        total_down = p['down_pix'] * p['down_sub']

        try:
            self.ctrl.set_wavelength(p['start'])
            time.sleep(1.0)

            for i in range(p['scans']):
                if self.stop_flag: break
                self.log(f"Scan {i+1}/{p['scans']}")

                if total_up > 0:
                    step_nm = (p['end'] - p['start']) / total_up
                    start_t = time.perf_counter()
                    for step in range(1, total_up + 1):
                        if self.stop_flag: break
                        self.ctrl.set_wavelength(p['start'] + (step * step_nm))
                        elapsed = time.perf_counter() - start_t
                        target = (step / total_up) * p['up_time']
                        if target > elapsed: time.sleep(target - elapsed)

                if self.stop_flag: break

                if total_down > 0:
                    step_nm = (p['end'] - p['start']) / total_down
                    start_t = time.perf_counter()
                    for step in range(1, total_down + 1):
                        if self.stop_flag: break
                        self.ctrl.set_wavelength(p['end'] - (step * step_nm))
                        elapsed = time.perf_counter() - start_t
                        target = (step / total_down) * p['down_time']
                        if target > elapsed: time.sleep(target - elapsed)

                if i < p['scans'] - 1: time.sleep(p['delay'])

        except Exception as e:
            self.log(f"Error: {e}")
        finally:
            self.log("Done.")
            self.stop_flag = False
            self.root.after(0, lambda: [self.btn_start.config(state="normal"), self.btn_stop.config(state="disabled")])

    # --- CORRECTED: Defined INSIDE the class ---
    def on_closing(self):
        self.stop_flag = True
        try:
            self.ctrl.close()
        except:
            pass
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = LaserSweepApp(root)
    # Now we can reference on_closing correctly
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()