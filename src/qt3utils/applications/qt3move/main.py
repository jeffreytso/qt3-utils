import tkinter as tk
from tkinter import ttk, messagebox
from encoderless_wrapper import EncoderlessMicrostage
    

# --- Main Application ---
class MicrostageApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Microstage Controller")
        self.resizable(False, False)

        # --- Initialize Hardware Connection OR Mock Object ---
        self.stage = None
        try:
            self.stage = EncoderlessMicrostage()
        except Exception as e:
            messagebox.showerror(
                "Hardware Connection Error",
                f"Could not initialize stage controller.\n\nPlease check hardware connections and ensure all driver files are present.\n\nError: {e}"
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
        self.stepping_enabled_var = tk.BooleanVar(value=False)
        self.is_homed = False

        self._create_widgets()
        
        self._update_position_display()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")

        # --- Homing and Setup Frame ---
        setup_frame = ttk.LabelFrame(main_frame, text="Setup", padding="10")
        setup_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        setup_frame.columnconfigure((0, 1), weight=1)
        
        ttk.Button(setup_frame, text="Find Home (Set 0,0)", command=self._find_home).grid(row=0, column=0, padx=5, sticky="ew")
        ttk.Button(setup_frame, text="Return to Home", command=self._return_to_home).grid(row=0, column=1, padx=5, sticky="ew")

        # --- Main Position Control Frame ---
        control_frame = ttk.LabelFrame(main_frame, text="Set Position", padding="10")
        control_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        # Header Labels
        ttk.Label(control_frame, text="Set Value (µm)").grid(row=0, column=2, padx=5, pady=5)
        ttk.Label(control_frame, text="Current (µm)").grid(row=0, column=3, padx=5, pady=5)

        # X-Axis Controls
        ttk.Label(control_frame, text="X axis").grid(row=1, column=0, sticky="w", padx=5)
        ttk.Button(control_frame, text="Set Position", command=self._set_x_position).grid(row=1, column=1, padx=5)
        ttk.Entry(control_frame, textvariable=self.x_set_var, width=10).grid(row=1, column=2)
        ttk.Label(control_frame, textvariable=self.x_current_var, width=10, relief="sunken", anchor="center").grid(row=1, column=3, padx=5)
        
        # Y-Axis Controls
        ttk.Label(control_frame, text="Y axis").grid(row=2, column=0, sticky="w", padx=5, pady=(5,0))
        ttk.Button(control_frame, text="Set Position", command=self._set_y_position).grid(row=2, column=1, padx=5, pady=(5,0))
        ttk.Entry(control_frame, textvariable=self.y_set_var, width=10).grid(row=2, column=2, pady=(5,0))
        ttk.Label(control_frame, textvariable=self.y_current_var, width=10, relief="sunken", anchor="center").grid(row=2, column=3, padx=5, pady=(5,0))

        # --- Stepping Control Frame ---
        stepping_frame = ttk.LabelFrame(main_frame, text="Stepping Control", padding="10")
        stepping_frame.grid(row=2, column=0, columnspan=2, sticky="ew")
        
        ttk.Checkbutton(
            stepping_frame, 
            text="Enable stepping with arrow keys", 
            variable=self.stepping_enabled_var, 
            command=self._toggle_key_bindings
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=5, pady=(0, 10))
        
        ttk.Label(stepping_frame, text="X Step (µm):").grid(row=1, column=0, sticky="w", padx=5)
        ttk.Entry(stepping_frame, textvariable=self.x_step_var, width=10).grid(row=1, column=1, padx=5)

        ttk.Label(stepping_frame, text="Y Step (µm):").grid(row=2, column=0, sticky="w", padx=5, pady=(5,0))
        ttk.Entry(stepping_frame, textvariable=self.y_step_var, width=10).grid(row=2, column=1, padx=5, pady=(5,0))

    def _toggle_key_bindings(self):
        """Enables or disables the arrow key bindings based on the checkbox state."""
        if self.stepping_enabled_var.get():
            self._enable_key_bindings()
        else:
            self._disable_key_bindings()

    def _enable_key_bindings(self):
        """Binds arrow keys to the jogging function."""
        print("Arrow key stepping enabled.")
        self.bind("<KeyPress-Up>", self._handle_key_press)
        self.bind("<KeyPress-Down>", self._handle_key_press)
        self.bind("<KeyPress-Left>", self._handle_key_press)
        self.bind("<KeyPress-Right>", self._handle_key_press)

    def _disable_key_bindings(self):
        """Unbinds arrow keys."""
        print("Arrow key stepping disabled.")
        self.unbind("<KeyPress-Up>")
        self.unbind("<KeyPress-Down>")
        self.unbind("<KeyPress-Left>")
        self.unbind("<KeyPress-Right>")
    
    def _check_if_homed(self, show_warning=True):
        if not self.is_homed:
            if show_warning:
                messagebox.showwarning("Homing Required", "Please run the 'Find Home' sequence first to calibrate the stage position.")
            return False
        return True

    def _find_home(self):
        try:
            self.stage.find_home()
            self.is_homed = True
            self.stage.get_position() # Update internal state if necessary
            messagebox.showinfo("Homing Complete", "Stage has been homed. The bottom-right corner is now (0, 0).")
        except Exception as e:
            messagebox.showerror("Homing Error", f"An error occurred during homing:\n{e}")

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
        # Failsafe in case bindings are somehow active when they shouldn't be
        if not self.stepping_enabled_var.get():
            return

        key_map = {
            "Up":    ('y', 1), "Down":  ('y', -1),
            "Left":  ('x', 1), "Right": ('x', -1) # Remember: Left is +X, Right is -X in our coordinate system
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
        # Only update the display if the stage has been homed
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
