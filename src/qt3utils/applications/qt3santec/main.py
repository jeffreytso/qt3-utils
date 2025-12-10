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

    def set_power(self, power_value):
        """Set the optical output power level.
        
        Args:
            power_value: Power level in dBm (range: -15 to +13 dBm)
        
        Raises:
            ValueError: If power value is out of valid range
            RuntimeError: If no laser is available
        """
        if not self.lasers:
            raise RuntimeError("No lasers connected.")
        
        # Validate power range: -15dBm to +13dBm
        if power_value < -15.0 or power_value > 13.0:
            raise ValueError(f"Power must be between -15 and +13 dBm. Got {power_value} dBm.")
        
        # Use active laser if available, otherwise use first laser
        if self.active_laser:
            inst = self.active_laser['obj']
        else:
            # If no active laser, use first available laser
            inst = self.lasers[0]['obj']
            # Switch to this laser
            if self.switch:
                self.switch.write(f"CH {self.lasers[0]['port']}")
                time.sleep(0.2)
            self.active_laser = self.lasers[0]
        
        # Set power using Legacy mode command :POW
        inst.write(f":POW {power_value}")
        
        # Ensure power is on
        if inst.query(":POW:STAT?").strip() == "0":
            inst.write(":POW:STAT 1")

    def check_continuous_range(self, start_nm, end_nm):
        """Check if start and end wavelengths are within a single laser's range.
        Returns the laser object if valid, None otherwise."""
        for laser in self.lasers:
            if laser['min'] <= start_nm <= laser['max'] and laser['min'] <= end_nm <= laser['max']:
                return laser
        return None

    def configure_continuous_sweep(self, laser, start_nm, stop_nm, speed_nm_per_s, mode):
        """Configure continuous sweep parameters on a specific laser.
        
        Args:
            laser: Laser dictionary object
            start_nm: Start wavelength in nm
            stop_nm: Stop wavelength in nm
            speed_nm_per_s: Sweep speed (1, 2, 5, 10, 20, 50, 100, or 200 nm/s)
            mode: Sweep mode (1=one-way continuous, 3=two-way continuous)
        """
        valid_speeds = [1, 2, 5, 10, 20, 50, 100, 200]
        if speed_nm_per_s not in valid_speeds:
            raise ValueError(f"Speed must be one of {valid_speeds} nm/s")
        
        if mode not in [1, 3]:
            raise ValueError("Mode must be 1 (one-way) or 3 (two-way)")
        
        inst = laser['obj']
        
        # Switch to this laser if not already active
        if self.active_laser != laser:
            if self.active_laser: self.active_laser['obj'].write(":POW:STAT 0")
            self.switch.write(f"CH {laser['port']}")
            time.sleep(0.2)
            self.active_laser = laser
        
        # Configure sweep parameters
        inst.write(f":WAV:SWE:STARt {start_nm}")
        inst.write(f":WAV:SWE:STOP {stop_nm}")
        inst.write(f":WAV:SWE:SPE {speed_nm_per_s}")
        inst.write(f":WAV:SWE:MOD {mode}")
        
        # Ensure power is on
        if inst.query(":POW:STAT?").strip() == "0":
            inst.write(":POW:STAT 1")

    def start_continuous_sweep(self, laser):
        """Start continuous sweep on a laser."""
        inst = laser['obj']
        inst.write(":WAV:SWE 1")

    def start_repeat_sweep(self, laser):
        """Start repeat scan on a laser."""
        inst = laser['obj']
        inst.write(":WAV:SWE:REP")

    def stop_continuous_sweep(self, laser):
        """Stop continuous sweep on a laser."""
        inst = laser['obj']
        inst.write(":WAV:SWE 0")

    def get_sweep_status(self, laser):
        """Get current sweep status.
        
        Returns:
            0: Stopped
            1: Running
            3: Standing by trigger
            4: Preparation for sweep start
        """
        inst = laser['obj']
        status = inst.query(":WAV:SWE?").strip()
        # Handle both legacy and SCPI responses
        try:
            return int(status)
        except ValueError:
            # SCPI format might have + prefix
            return int(status.lstrip('+'))

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
        self.root.title("Santec Laser Controller")
        self.ctrl = SantecController()
        self.stop_flag = False
        self.is_running = False
        self._build_gui()

    def _build_gui(self):
        # Set minimum window size to prevent resizing when switching modes
        self.root.minsize(600, 500)
        
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
        
        tk.Label(manual_frame, text="Set Power (dBm):").pack(side="left", padx=5)
        self.ent_manual_power = tk.Entry(manual_frame, width=10)
        self.ent_manual_power.pack(side="left", padx=5)
        self.btn_set_power = tk.Button(manual_frame, text="Set Power", command=self.set_manual_power, state="disabled")
        self.btn_set_power.pack(side="left", padx=5)

        # Sweep Type Selection
        sweep_type_frame = tk.Frame(self.root)
        sweep_type_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(sweep_type_frame, text="Sweep Type:").pack(side="left", padx=5)
        self.combo_sweep_type = ttk.Combobox(sweep_type_frame, width=20, state="readonly", values=["Step Sweep", "Continuous Sweep"])
        self.combo_sweep_type.pack(side="left", padx=5)
        self.combo_sweep_type.set("Step Sweep")
        self.combo_sweep_type.bind("<<ComboboxSelected>>", self._toggle_sweep_type)

        # Sweep Config (Step Sweep)
        self.sweep_frame = tk.LabelFrame(self.root, text="Sweep Configuration")
        self.sweep_frame.pack(fill="x", padx=10, pady=5)

        # Row 0: Range and Sweep direction option
        tk.Label(self.sweep_frame, text="Start (nm):").grid(row=0, column=0, sticky="e")
        self.ent_start = tk.Entry(self.sweep_frame, width=10); self.ent_start.grid(row=0, column=1)
        tk.Label(self.sweep_frame, text="End (nm):").grid(row=0, column=2, sticky="e")
        self.ent_end = tk.Entry(self.sweep_frame, width=10); self.ent_end.grid(row=0, column=3)
        tk.Label(self.sweep_frame, text="Direction:").grid(row=0, column=4, sticky="e")
        self.combo_sweep_direction = ttk.Combobox(self.sweep_frame, width=12, state="readonly", values=["One-way", "Two-way"])
        self.combo_sweep_direction.grid(row=0, column=5, sticky="w")
        self.combo_sweep_direction.set("Two-way")
        self.combo_sweep_direction.bind("<<ComboboxSelected>>", self._toggle_one_way)

        # Row 1: Upsweep
        tk.Label(self.sweep_frame, text="Upsweep Time (s):").grid(row=1, column=0, sticky="e")
        self.ent_up_time = tk.Entry(self.sweep_frame, width=10); self.ent_up_time.grid(row=1, column=1)
        
        tk.Label(self.sweep_frame, text="Up Pixels:").grid(row=1, column=2, sticky="e")
        self.ent_up_pixels = tk.Entry(self.sweep_frame, width=10); self.ent_up_pixels.grid(row=1, column=3)
        
        tk.Label(self.sweep_frame, text="Up Subpixels:").grid(row=1, column=4, sticky="e")
        self.ent_up_sub = tk.Entry(self.sweep_frame, width=5); self.ent_up_sub.grid(row=1, column=5)
        self.ent_up_sub.insert(0, "1")

        # Row 2: Downsweep
        self.lbl_down_time = tk.Label(self.sweep_frame, text="Downsweep Time (s):")
        self.lbl_down_time.grid(row=2, column=0, sticky="e")
        self.ent_down_time = tk.Entry(self.sweep_frame, width=10); self.ent_down_time.grid(row=2, column=1)
        
        self.lbl_down_pixels = tk.Label(self.sweep_frame, text="Down Pixels:")
        self.lbl_down_pixels.grid(row=2, column=2, sticky="e")
        self.ent_down_pixels = tk.Entry(self.sweep_frame, width=10); self.ent_down_pixels.grid(row=2, column=3)

        self.lbl_down_sub = tk.Label(self.sweep_frame, text="Down Subpixels:")
        self.lbl_down_sub.grid(row=2, column=4, sticky="e")
        self.ent_down_sub = tk.Entry(self.sweep_frame, width=5); self.ent_down_sub.grid(row=2, column=5)
        self.ent_down_sub.insert(0, "1")

        # Row 3: Repeats
        tk.Label(self.sweep_frame, text="Scans:").grid(row=3, column=0, sticky="e")
        self.ent_scans = tk.Entry(self.sweep_frame, width=10); self.ent_scans.grid(row=3, column=1)
        tk.Label(self.sweep_frame, text="Delay (s):").grid(row=3, column=2, sticky="e")
        self.ent_delay = tk.Entry(self.sweep_frame, width=10); self.ent_delay.grid(row=3, column=3)

        for child in self.sweep_frame.winfo_children(): child.grid_configure(padx=5, pady=5)

        # Continuous Sweep Config
        self.cont_sweep_frame = tk.LabelFrame(self.root, text="Continuous Sweep Configuration")
        self.cont_sweep_frame.pack(fill="x", padx=10, pady=5)

        # Row 0: Range and Laser selection
        tk.Label(self.cont_sweep_frame, text="Start (nm):").grid(row=0, column=0, sticky="e")
        self.ent_cont_start = tk.Entry(self.cont_sweep_frame, width=10); self.ent_cont_start.grid(row=0, column=1)
        tk.Label(self.cont_sweep_frame, text="End (nm):").grid(row=0, column=2, sticky="e")
        self.ent_cont_end = tk.Entry(self.cont_sweep_frame, width=10); self.ent_cont_end.grid(row=0, column=3)
        tk.Label(self.cont_sweep_frame, text="Laser:").grid(row=0, column=4, sticky="e")
        self.combo_cont_laser = ttk.Combobox(self.cont_sweep_frame, width=20, state="readonly")
        self.combo_cont_laser.grid(row=0, column=5, sticky="w")
        self.combo_cont_laser.set("Auto")

        # Row 1: Speed and Mode
        tk.Label(self.cont_sweep_frame, text="Speed (nm/s):").grid(row=1, column=0, sticky="e")
        self.combo_cont_speed = ttk.Combobox(self.cont_sweep_frame, width=10, state="readonly", values=["1", "2", "5", "10", "20", "50", "100", "200"])
        self.combo_cont_speed.grid(row=1, column=1)
        self.combo_cont_speed.set("10")
        tk.Label(self.cont_sweep_frame, text="Mode:").grid(row=1, column=2, sticky="e")
        self.combo_cont_mode = ttk.Combobox(self.cont_sweep_frame, width=15, state="readonly", values=["One-way", "Two-way"])
        self.combo_cont_mode.grid(row=1, column=3, sticky="w")
        self.combo_cont_mode.set("One-way")

        # Row 2: Scans and Delay
        tk.Label(self.cont_sweep_frame, text="Scans:").grid(row=2, column=0, sticky="e")
        self.ent_cont_scans = tk.Entry(self.cont_sweep_frame, width=10); self.ent_cont_scans.grid(row=2, column=1)
        tk.Label(self.cont_sweep_frame, text="Delay (s):").grid(row=2, column=2, sticky="e")
        self.ent_cont_delay = tk.Entry(self.cont_sweep_frame, width=10); self.ent_cont_delay.grid(row=2, column=3)

        for child in self.cont_sweep_frame.winfo_children(): child.grid_configure(padx=5, pady=5)
        
        # Calculate and set consistent heights for both frames to prevent resizing
        self.root.update_idletasks()  # Update to get actual sizes
        step_height = self.sweep_frame.winfo_reqheight()
        cont_height = self.cont_sweep_frame.winfo_reqheight()
        max_height = max(step_height, cont_height)
        
        # Set minimum height for both frames
        self.sweep_frame.config(height=max_height)
        self.cont_sweep_frame.config(height=max_height)
        
        # Initially hide continuous sweep frame
        self.cont_sweep_frame.pack_forget()

        # Actions - placed after sweep configuration sections
        self.action_frame = tk.Frame(self.root)
        self.action_frame.pack(fill="x", padx=10, pady=10)
        self.btn_start = tk.Button(self.action_frame, text="START", bg="green", fg="white", font=("Arial", 10, "bold"), command=self.start_sweep_thread, state="disabled")
        self.btn_start.pack(side="left", fill="x", expand=True, padx=5)
        self.btn_stop = tk.Button(self.action_frame, text="STOP", bg="red", fg="white", font=("Arial", 10, "bold"), command=self.stop_sweep, state="disabled")
        self.btn_stop.pack(side="left", fill="x", expand=True, padx=5)

        # Logger - placed after action buttons
        self.txt_log = tk.Text(self.root, height=12, width=60)
        self.txt_log.pack(padx=10, pady=5)

    def log(self, msg):
        self.root.after(0, lambda: self.txt_log.insert(tk.END, msg + "\n"))
        self.root.after(0, lambda: self.txt_log.see(tk.END))

    def _toggle_sweep_type(self, event=None):
        """Show/hide sweep sections based on selected sweep type"""
        sweep_type = self.combo_sweep_type.get()
        if sweep_type == "Step Sweep":
            self.cont_sweep_frame.pack_forget()
            # Pack step sweep frame before action frame to maintain order
            self.sweep_frame.pack(fill="x", padx=10, pady=5, before=self.action_frame)
            # Update action buttons to use step sweep
            self.btn_start.config(command=self.start_sweep_thread)
            self.btn_stop.config(command=self.stop_sweep)
        elif sweep_type == "Continuous Sweep":
            self.sweep_frame.pack_forget()
            # Pack continuous sweep frame before action frame to maintain order
            self.cont_sweep_frame.pack(fill="x", padx=10, pady=5, before=self.action_frame)
            # Update action buttons to use continuous sweep
            self.btn_start.config(command=self.start_continuous_sweep_thread)
            self.btn_stop.config(command=self.stop_continuous_sweep)

    def _toggle_one_way(self, *args):
        """Show/hide downsweep fields based on sweep direction selection"""
        direction = self.combo_sweep_direction.get()
        is_one_way = (direction == "One-way")
        if is_one_way:
            self.lbl_down_time.grid_remove()
            self.ent_down_time.grid_remove()
            self.lbl_down_pixels.grid_remove()
            self.ent_down_pixels.grid_remove()
            self.lbl_down_sub.grid_remove()
            self.ent_down_sub.grid_remove()
        else:
            self.lbl_down_time.grid()
            self.ent_down_time.grid()
            self.lbl_down_pixels.grid()
            self.ent_down_pixels.grid()
            self.lbl_down_sub.grid()
            self.ent_down_sub.grid()

    def connect_hardware(self):
        try:
            msg = self.ctrl.connect()
            self.lbl_status.config(text=msg, fg="green")
            self.btn_connect.config(state="disabled")
            self.btn_set_manual.config(state="normal")
            self.btn_set_power.config(state="normal")
            self.btn_start.config(state="normal")
            
            # Populate laser dropdown for continuous sweep
            laser_options = ["Auto"]
            for i, laser in enumerate(self.ctrl.lasers):
                laser_options.append(f"Laser {i+1} ({laser['min']:.1f}-{laser['max']:.1f} nm)")
            self.combo_cont_laser['values'] = laser_options
            self.combo_cont_laser.set("Auto")
            
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

    def set_manual_power(self):
        try:
            val = float(self.ent_manual_power.get())
            self.ctrl.set_power(val)
            self.log(f"Manual Set Power: {val} dBm")
        except ValueError as e:
            messagebox.showerror("Error", str(e))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def start_sweep_thread(self):
        try:
            # Validate and convert inputs with better error messages
            start_str = self.ent_start.get().strip()
            if not start_str:
                raise ValueError("Start wavelength is required.")
            start = float(start_str)
            
            end_str = self.ent_end.get().strip()
            if not end_str:
                raise ValueError("End wavelength is required.")
            end = float(end_str)
            
            if not self.ctrl.check_valid_range(start, end): 
                raise ValueError("Range invalid.")
            
            up_time_str = self.ent_up_time.get().strip()
            if not up_time_str:
                raise ValueError("Upsweep time is required.")
            up_time = float(up_time_str)
            
            up_pix_str = self.ent_up_pixels.get().strip()
            if not up_pix_str:
                raise ValueError("Up pixels is required.")
            up_pix = int(up_pix_str)
            
            up_sub_str = self.ent_up_sub.get().strip()
            up_sub = max(1, int(up_sub_str)) if up_sub_str else 1
            
            # Get sweep direction from dropdown
            direction = self.combo_sweep_direction.get()
            is_one_way = (direction == "One-way")
            
            down_time_str = self.ent_down_time.get().strip()
            if not is_one_way:
                if not down_time_str:
                    raise ValueError("Downsweep time is required (or select 'One-way' direction).")
                down_time = float(down_time_str)
            else:
                down_time = 0.0  # Not used in one-way mode
            
            down_pix_str = self.ent_down_pixels.get().strip()
            if not is_one_way:
                if not down_pix_str:
                    raise ValueError("Down pixels is required (or select 'One-way' direction).")
                down_pix = int(down_pix_str)
            else:
                down_pix = 0  # Not used in one-way mode
            
            down_sub_str = self.ent_down_sub.get().strip()
            down_sub = max(1, int(down_sub_str)) if down_sub_str else 1
            
            scans_str = self.ent_scans.get().strip()
            if not scans_str:
                raise ValueError("Number of scans is required.")
            scans = int(scans_str)
            
            delay_str = self.ent_delay.get().strip()
            if not delay_str:
                raise ValueError("Delay is required.")
            delay = float(delay_str)
            
            self.sweep_params = {
                'start': start, 'end': end,
                'up_time': up_time,
                'up_pix': up_pix,
                'up_sub': up_sub,
                'down_time': down_time,
                'down_pix': down_pix,
                'down_sub': down_sub,
                'scans': scans,
                'delay': delay,
                'one_way': is_one_way
            }
        except ValueError as e:
            error_msg = str(e)
            if "could not convert" in error_msg.lower() or "invalid literal" in error_msg.lower():
                messagebox.showerror("Input Error", "Please enter valid numbers in all required fields.")
            else:
                messagebox.showerror("Input Error", error_msg)
            return

        self.stop_flag = False
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        threading.Thread(target=self.run_sweep, daemon=True).start()

    def stop_sweep(self):
        self.stop_flag = True
        self.log("Stopping...")

    def start_continuous_sweep_thread(self):
        try:
            # Validate and convert inputs with better error messages
            start_str = self.ent_cont_start.get().strip()
            if not start_str:
                raise ValueError("Start wavelength is required.")
            start = float(start_str)
            
            end_str = self.ent_cont_end.get().strip()
            if not end_str:
                raise ValueError("End wavelength is required.")
            end = float(end_str)
            
            speed = int(self.combo_cont_speed.get())
            mode_str = self.combo_cont_mode.get()
            mode = 1 if mode_str == "One-way" else 3
            
            scans_str = self.ent_cont_scans.get().strip()
            if not scans_str:
                raise ValueError("Number of scans is required.")
            scans = int(scans_str)
            
            delay_str = self.ent_cont_delay.get().strip()
            if not delay_str:
                raise ValueError("Delay is required.")
            delay = float(delay_str)
            
            # Determine which laser to use
            laser = None
            laser_selection = self.combo_cont_laser.get()
            if laser_selection == "Auto":
                laser = self.ctrl.check_continuous_range(start, end)
                if not laser:
                    raise ValueError(f"Range {start}-{end} nm is not within any single laser's range.")
            else:
                # Extract laser index from selection (e.g., "Laser 1 (...)" -> index 0)
                laser_idx = int(laser_selection.split()[1]) - 1
                if laser_idx < 0 or laser_idx >= len(self.ctrl.lasers):
                    raise ValueError("Invalid laser selection.")
                laser = self.ctrl.lasers[laser_idx]
                if not (laser['min'] <= start <= laser['max'] and laser['min'] <= end <= laser['max']):
                    raise ValueError(f"Range {start}-{end} nm is not within selected laser's range ({laser['min']:.1f}-{laser['max']:.1f} nm).")
            
            self.cont_sweep_params = {
                'laser': laser,
                'start': start,
                'end': end,
                'speed': speed,
                'mode': mode,
                'scans': scans,
                'delay': delay
            }
        except ValueError as e:
            error_msg = str(e)
            if "could not convert" in error_msg.lower() or "invalid literal" in error_msg.lower():
                messagebox.showerror("Input Error", "Please enter valid numbers in all required fields.")
            else:
                messagebox.showerror("Input Error", error_msg)
            return

        self.stop_flag = False
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        threading.Thread(target=self.run_continuous_sweep, daemon=True).start()

    def stop_continuous_sweep(self):
        self.stop_flag = True
        if hasattr(self, 'cont_sweep_params'):
            try:
                self.ctrl.stop_continuous_sweep(self.cont_sweep_params['laser'])
            except:
                pass
        self.log("Stopping continuous sweep...")

    def run_continuous_sweep(self):
        p = self.cont_sweep_params
        self.log(f"--- Starting Continuous Sweep ---")
        self.log(f"Laser: {p['laser']['ip']} ({p['laser']['min']:.1f}-{p['laser']['max']:.1f} nm)")
        self.log(f"Range: {p['start']:.3f} - {p['end']:.3f} nm")
        self.log(f"Speed: {p['speed']} nm/s, Mode: {'One-way' if p['mode'] == 1 else 'Two-way'}")
        self.log(f"Number of scans: {p['scans']}")

        try:
            # Ensure sweep is stopped before configuring
            self.ctrl.stop_continuous_sweep(p['laser'])
            time.sleep(0.2)  # Brief pause to ensure stop command is processed

            # Configure the sweep
            self.ctrl.configure_continuous_sweep(p['laser'], p['start'], p['end'], p['speed'], p['mode'])
            self.log("Sweep configured.")

            # Use repeat scan command for multiple scans
            # The repeat command will handle the repeats, but we need to monitor and stop after desired number
            completed_scans = 0
            last_status = None
            sweep_running = False
            
            # Start the repeat scan
            self.ctrl.start_repeat_sweep(p['laser'])
            self.log("Repeat scan started.")
            time.sleep(0.2)  # Brief pause to allow sweep to start
            
            # Monitor sweep and count completed scans
            while completed_scans < p['scans']:
                if self.stop_flag:
                    self.ctrl.stop_continuous_sweep(p['laser'])
                    break
                
                status = self.ctrl.get_sweep_status(p['laser'])
                
                # Track when sweep is running
                if status == 1:  # Running
                    sweep_running = True
                
                # Detect when a scan completes (status transitions from Running to Stopped)
                if status == 0 and sweep_running:
                    completed_scans += 1
                    self.log(f"Scan {completed_scans}/{p['scans']} completed.")
                    sweep_running = False
                    
                    # If we've completed all scans, stop
                    if completed_scans >= p['scans']:
                        self.ctrl.stop_continuous_sweep(p['laser'])
                        break
                    
                    # Wait for delay before next scan (if not last scan)
                    if completed_scans < p['scans']:
                        self.log(f"Waiting {p['delay']} s before next scan...")
                        delay_start = time.time()
                        while time.time() - delay_start < p['delay']:
                            if self.stop_flag:
                                self.ctrl.stop_continuous_sweep(p['laser'])
                                break
                            time.sleep(0.1)
                        
                        # Restart repeat scan after delay if not stopped
                        if not self.stop_flag:
                            self.ctrl.start_repeat_sweep(p['laser'])
                            time.sleep(0.2)  # Brief pause to allow sweep to start
                
                last_status = status
                time.sleep(0.1)  # Check every 100ms

        except Exception as e:
            self.log(f"Error: {e}")
        finally:
            try:
                self.ctrl.stop_continuous_sweep(p['laser'])
            except:
                pass
            self.log("Continuous sweep done.")
            self.stop_flag = False
            self.root.after(0, lambda: [self.btn_start.config(state="normal"), self.btn_stop.config(state="disabled")])

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

                if not p['one_way'] and total_down > 0:
                    step_nm = (p['end'] - p['start']) / total_down
                    start_t = time.perf_counter()
                    for step in range(1, total_down + 1):
                        if self.stop_flag: break
                        self.ctrl.set_wavelength(p['end'] - (step * step_nm))
                        elapsed = time.perf_counter() - start_t
                        target = (step / total_down) * p['down_time']
                        if target > elapsed: time.sleep(target - elapsed)
                elif p['one_way'] and i < p['scans'] - 1:
                    # Reset to start position for next scan
                    self.ctrl.set_wavelength(p['start'])
                    time.sleep(0.5)  # Brief pause after reset

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
        # Stop any running continuous sweeps
        if hasattr(self, 'cont_sweep_params'):
            try:
                self.ctrl.stop_continuous_sweep(self.cont_sweep_params['laser'])
            except:
                pass
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