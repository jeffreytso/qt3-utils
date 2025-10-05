import tkinter as tk
from tkinter import ttk, messagebox
import time

# --- DEVELOPMENT SWITCH ---
# Set to True to run the GUI without hardware (uses a 'MockStage' class)
# Set to False to connect to the real stage controller
TEST_MODE = True

if not TEST_MODE:
    try:
        from encoderless_wrapper import EncoderlessMicrostage
    except ImportError:
        print("FATAL ERROR: Make sure 'stage_controller.py' is in the same directory.")
        exit()

# --- NEW: A Mock Stage Class for GUI Testing ---
class MockStage:
    """
    A fake stage class that mimics the real EncoderlessMicrostage.
    It prints actions to the console instead of controlling hardware.
    """
    def __init__(self):
        self.x_pos_um = 0.0
        self.y_pos_um = 0.0
        print("--- MockStage Initialized (TEST MODE) ---")

    def find_home(self):
        print("[Mock] Homing stage...")
        time.sleep(1) # Simulate the time it takes
        self.x_pos_um = 0.0
        self.y_pos_um = 0.0
        print("[Mock] Homing complete. Position is (0, 0).")

    def return_to_home(self):
        print("[Mock] Returning to home.")
        self.move_to(0, 0)

    def move_to(self, target_x_um, target_y_um, snap_to_stable_step=True):
        print(f"[Mock] Moving to ({target_x_um:.2f}, {target_y_um:.2f})")
        time.sleep(0.5) # Simulate move time
        self.x_pos_um = target_x_um
        self.y_pos_um = target_y_um
        print("[Mock] Move complete.")

    def get_position(self):
        return (self.x_pos_um, self.y_pos_um)

    def close(self):
        print("[Mock] Releasing hardware resources.")


class MicrostageApp(tk.Tk):
    """
    A Tkinter GUI for controlling the Mad City Labs MicroStage.
    """
    def __init__(self):
        super().__init__()
        self.title("Microstage Controller")
        self.resizable(False, False)

        # --- Initialize Hardware Connection OR Mock Object ---
        self.stage = None
        if TEST_MODE:
            self.stage = MockStage()
        else:
            try:
                self.stage = EncoderlessMicrostage()
            except Exception as e:
                messagebox.showerror(
                    "Hardware Connection Error",
                    f"Could not connect to the stage. Please ensure it is plugged in "
                    f"and all necessary driver files are present.\n\nError: {e}"
                )
                self.destroy()
                return

        # --- GUI State Variables ---
        self.x_set_var = tk.StringVar(value="0.0")
        self.y_set_var = tk.StringVar(value="0.0")
        self.x_step_var = tk.StringVar(value="1.0")
        self.y_step_var = tk.StringVar(value="1.0")
        self.x_current_var = tk.StringVar(value="--")
        self.y_current_var = tk.StringVar(value="--")
        self.is_homed = False

        # --- Build the GUI ---
        self._create_widgets()

        # --- Bind arrow keys to a handler function ---
        self.bind("<KeyPress-Up>", self._handle_key_press)
        self.bind("<KeyPress-Down>", self._handle_key_press)
        self.bind("<KeyPress-Left>", self._handle_key_press)
        self.bind("<KeyPress-Right>", self._handle_key_press)

        # --- Start the update loop to poll for position ---
        self._update_position_display()

        # --- Ensure clean shutdown ---
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")

        setup_frame = ttk.LabelFrame(main_frame, text="Setup", padding="10")
        setup_frame.grid(row=0, column=0, columnspan=5, sticky="ew", pady=(0, 10))
        setup_frame.columnconfigure(0, weight=1)
        
        ttk.Button(setup_frame, text="Find Home (Set 0,0)", command=self._find_home).grid(row=0, column=0, padx=5)
        ttk.Button(setup_frame, text="Return to Home", command=self._return_to_home).grid(row=0, column=1, padx=5)

        control_frame = ttk.LabelFrame(main_frame, text="Micros", padding="10")
        control_frame.grid(row=1, column=0, columnspan=5, sticky="ew")

        ttk.Label(control_frame, text="Set Value (µm)").grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(control_frame, text="Step (µm)").grid(row=0, column=2, padx=5, pady=5)
        ttk.Label(control_frame, text="Current (µm)").grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(control_frame, text="X axis").grid(row=1, column=0, sticky="w", padx=5)
        ttk.Button(control_frame, text="Set Position", command=self._set_x_position).grid(row=1, column=0, padx=(40, 5), sticky="e")
        ttk.Entry(control_frame, textvariable=self.x_set_var, width=10).grid(row=1, column=1)
        ttk.Entry(control_frame, textvariable=self.x_step_var, width=10).grid(row=1, column=2)
        ttk.Label(control_frame, textvariable=self.x_current_var, width=10, relief="sunken", anchor="center").grid(row=1, column=3, padx=5)
        
        ttk.Label(control_frame, text="Y axis").grid(row=2, column=0, sticky="w", padx=5, pady=(5,0))
        ttk.Button(control_frame, text="Set Position", command=self._set_y_position).grid(row=2, column=0, padx=(40, 5), sticky="e", pady=(5,0))
        ttk.Entry(control_frame, textvariable=self.y_set_var, width=10).grid(row=2, column=1, pady=(5,0))
        ttk.Entry(control_frame, textvariable=self.y_step_var, width=10).grid(row=2, column=2, pady=(5,0))
        ttk.Label(control_frame, textvariable=self.y_current_var, width=10, relief="sunken", anchor="center").grid(row=2, column=3, padx=5, pady=(5,0))
        
    def _check_if_homed(self):
        if not self.is_homed:
            messagebox.showwarning("Homing Required", "Please run the 'Find Home' sequence first to calibrate the stage position.")
            return False
        return True

    def _find_home(self):
        self.stage.find_home()
        self.is_homed = True
        if TEST_MODE: # Don't show popup in test mode, it's annoying
             print("Mock homing is complete.")
        else:
            messagebox.showinfo("Homing Complete", "Stage has been homed. The bottom-right corner is now (0, 0).")

    def _return_to_home(self):
        if not self._check_if_homed(): return
        self.stage.return_to_home()
    
    def _set_x_position(self):
        if not self._check_if_homed(): return
        try:
            target_x = float(self.x_set_var.get())
            current_pos = self.stage.get_position()
            self.stage.move_to(target_x, current_pos[1])
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number for the X position.")
        except Exception as e:
            messagebox.showerror("Movement Error", f"An error occurred: {e}")

    def _set_y_position(self):
        if not self._check_if_homed(): return
        try:
            target_y = float(self.y_set_var.get())
            current_pos = self.stage.get_position()
            self.stage.move_to(current_pos[0], target_y)
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number for the Y position.")
        except Exception as e:
            messagebox.showerror("Movement Error", f"An error occurred: {e}")

    def _handle_key_press(self, event):
        key_map = {
            "Up":    ('y', 1), "Down":  ('y', -1),
            "Left":  ('x', 1), "Right": ('x', -1)
        }
        if event.keysym in key_map:
            axis, direction = key_map[event.keysym]
            self._step_move(axis, direction)

    def _step_move(self, axis, direction):
        if not self._check_if_homed(): return
        try:
            current_pos = self.stage.get_position()
            if axis == 'x':
                step_val = float(self.x_step_var.get())
                new_target_x = current_pos[0] + (step_val * direction)
                self.stage.move_to(new_target_x, current_pos[1])
            elif axis == 'y':
                step_val = float(self.y_step_var.get())
                new_target_y = current_pos[1] + (step_val * direction)
                self.stage.move_to(current_pos[0], new_target_y)
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number for the Step value.")
        except Exception as e:
            messagebox.showerror("Movement Error", f"An error occurred: {e}")

    def _update_position_display(self):
        if self.stage and self.is_homed:
            try:
                x_um, y_um = self.stage.get_position()
                self.x_current_var.set(f"{x_um:.2f}")
                self.y_current_var.set(f"{y_um:.2f}")
            except Exception as e:
                self.x_current_var.set("Error")
                self.y_current_var.set("Error")
                print(f"Error updating position display: {e}")
        self.after(250, self._update_position_display)

    def _on_closing(self):
        print("Closing application and releasing resources...")
        if self.stage:
            self.stage.close()
        self.destroy()

if __name__ == "__main__":
    app = MicrostageApp()
    app.mainloop()

