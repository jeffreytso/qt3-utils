import tkinter as tk
from tkinter import ttk, messagebox
import time

class MockMicrostage:
    """
    A mock implementation of the EncoderlessMicrostage that simulates
    hardware functionality without requiring an actual connection.
    """
    def __init__(self):
        self.x_position = 0.0
        self.y_position = 0.0
        self.is_homed = False
        
    def find_home(self):
        """Simulates the homing sequence."""
        self.x_position = 0.0
        self.y_position = 0.0
        self.is_homed = True
        
    def return_to_home(self):
        """Simulates returning to home position."""
        self.x_position = 0.0
        self.y_position = 0.0
        
    def get_position(self):
        """Returns the current simulated position."""
        return (self.x_position, self.y_position)
        
    def move_to(self, x, y):
        """Simulates moving to a target position."""
        self.x_position = x
        self.y_position = y
        
    def close(self):
        """Simulates closing the hardware connection."""
        pass

class StandaloneMicrostageApp(tk.Tk):
    """
    A standalone Tkinter GUI for controlling the Mad City Labs MicroStage
    that doesn't require a hardware connection. Uses mock functionality
    to simulate the real hardware behavior.
    """
    def __init__(self):
        super().__init__()
        self.title("Microstage Controller (Standalone)")
        self.resizable(False, False)

        # --- Initialize Mock Hardware Connection ---
        self.stage = MockMicrostage()

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

        # --- NEW: Bind arrow keys to a handler function ---
        self.bind("<KeyPress-Up>", self._handle_key_press)
        self.bind("<KeyPress-Down>", self._handle_key_press)
        self.bind("<KeyPress-Left>", self._handle_key_press)
        self.bind("<KeyPress-Right>", self._handle_key_press)

        # --- Start the update loop to poll for position ---
        self._update_position_display()

        # --- Ensure clean shutdown ---
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _create_widgets(self):
        """Creates and arranges all the GUI elements."""
        main_frame = ttk.Frame(self, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")

        # --- Homing and Setup Frame ---
        setup_frame = ttk.LabelFrame(main_frame, text="Setup", padding="10")
        setup_frame.grid(row=0, column=0, columnspan=5, sticky="ew", pady=(0, 10))
        setup_frame.columnconfigure(0, weight=1)
        
        ttk.Button(setup_frame, text="Find Home (Set 0,0)", command=self._find_home).grid(row=0, column=0, padx=5)
        ttk.Button(setup_frame, text="Return to Home", command=self._return_to_home).grid(row=0, column=1, padx=5)

        # --- Main Control Frame (resembling the user's image) ---
        control_frame = ttk.LabelFrame(main_frame, text="Micros", padding="10")
        control_frame.grid(row=1, column=0, columnspan=5, sticky="ew")

        # Header Labels
        ttk.Label(control_frame, text="Set Value (µm)").grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(control_frame, text="Step (µm)").grid(row=0, column=2, padx=5, pady=5)
        ttk.Label(control_frame, text="Current (µm)").grid(row=0, column=3, padx=5, pady=5)

        # X-Axis Controls
        ttk.Label(control_frame, text="X axis").grid(row=1, column=0, sticky="w", padx=5)
        ttk.Button(control_frame, text="Set Position", command=self._set_x_position).grid(row=1, column=0, padx=(40, 5), sticky="e")
        ttk.Entry(control_frame, textvariable=self.x_set_var, width=10).grid(row=1, column=1)
        ttk.Entry(control_frame, textvariable=self.x_step_var, width=10).grid(row=1, column=2)
        ttk.Label(control_frame, textvariable=self.x_current_var, width=10, relief="sunken", anchor="center").grid(row=1, column=3, padx=5)
        
        # Y-Axis Controls
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
        """Handles jogging the stage with arrow keys."""
        # Map keysym to the axis and direction for _step_move
        key_map = {
            "Up":    ('y', 1),   # Positive Y is UP
            "Down":  ('y', -1),  # Negative Y is DOWN
            "Left":  ('x', 1),   # Positive X is LEFT
            "Right": ('x', -1)   # Negative X is RIGHT
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
        """Periodically reads stage position and updates the GUI."""
        if self.stage and self.is_homed:
            try:
                x_um, y_um = self.stage.get_position()
                self.x_current_var.set(f"{x_um:.2f}")
                self.y_current_var.set(f"{y_um:.2f}")
            except Exception as e:
                self.x_current_var.set("Error")
                self.y_current_var.set("Error")
                print(f"Error updating position display: {e}")
        
        # Schedule this function to run again in 250ms
        self.after(250, self._update_position_display)

    def _on_closing(self):
        """Handles cleanup when the application window is closed."""
        print("Closing application and releasing hardware...")
        if self.stage:
            self.stage.close()
        self.destroy()

if __name__ == "__main__":
    app = StandaloneMicrostageApp()
    app.mainloop()
