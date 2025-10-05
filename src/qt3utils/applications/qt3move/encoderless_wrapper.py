# stage_controller.py

import time
from mcl_wrapper import MCL_Microdrive # Assumes your low-level wrapper is in mcl_wrapper.py

# --- Physical Constants ---
# µm per step
MICRONS_PER_MICROSTEP = 0.09525 

# --- Configuration Constants ---
# Default speed for stage movements in mm/s
DEFAULT_VELOCITY = 0.5 
# A travel distance larger than the stage's range 25000µm to ensure we hit a limit switch during homing.
HOMING_TRAVEL_UM = 30000 
# Define software travel limits in µm, relative to the home position
X_LIMIT_UM, Y_LIMIT_UM = 12000.0, 12000.0
# A small distance in µm to overshoot the target for backlash compensation.
BACKLASH_COMP_UM = 10.0


class EncoderlessMicrostage:
    """
    A high-level Python wrapper to control a Mad City Labs MicroStage
    without encoders, implementing dead reckoning and high-precision move logic.
    """
    def __init__(self):
        """Initializes the connection and the internal position counters."""
        self.mcl = None
        self.handle = None
        
        try:
            self.mcl = MCL_Microdrive()
            self.handle = self.mcl.init_handle()
            if not self.handle:
                raise Exception("Failed to get a valid hardware handle.")
        except Exception as e:
            print(f"FATAL: Could not connect to the stage. Check connections and DLL file. Error: {e}")
            raise
        
        # Internal position counters (bookkeeping) in microsteps
        self.x_pos_steps = 0
        self.y_pos_steps = 0
        
        print(f"Connected to stage (Handle: {self.handle}). Position is unreferenced.")
        print(f"Software limits set to X: {X_LIMIT_UM} µm, Y: {Y_LIMIT_UM} µm.")
        print("Run find_home() to establish a (0, 0) origin at the bottom-right corner.")

    def _wait_for_move(self):
        """Private helper function to block execution until a move is complete."""
        time.sleep(0.1) # A brief initial pause to ensure the move command has been processed
        while self.mcl.move_status(self.handle):
            time.sleep(0.2)
        print("  - Move complete.")

    def find_home(self):
        """
        Performs a homing sequence by driving the stage against its physical
        limit switches to find the bottom-right corner, then defines it as (0, 0).
        """
        print("Starting homing sequence...")
        
        # 1. Move Y to the 'bottom' limit switch
        print("Homing Y axis (moving to bottom limit)...")
        steps_y = -round(HOMING_TRAVEL_UM / MICRONS_PER_MICROSTEP)
        self.mcl.move_three_axes_m(2, DEFAULT_VELOCITY, steps_y, 0, 0, 0, 0, 0, 0, self.handle)
        self._wait_for_move()

        # 2. Move X to the 'right' limit switch
        print("Homing X axis (moving to right limit)...")
        steps_x = round(HOMING_TRAVEL_UM / MICRONS_PER_MICROSTEP)
        self.mcl.move_three_axes_m(1, DEFAULT_VELOCITY, steps_x, 0, 0, 0, 0, 0, 0, self.handle)
        self._wait_for_move()

        # 3. Virtually set this physical location as our (0, 0) origin
        self.set_position(0, 0)
        print("✅ Homing complete. Bottom-right corner is now defined as (0, 0).")
        
    def return_to_home(self):
        """Moves the stage back to the defined (0, 0) origin."""
        print("Returning to home (0, 0)...")
        self.move_to(0, 0)

    def get_position(self):
        """Returns the current virtual position in microns based on internal counters."""
        x_microns = self.x_pos_steps * MICRONS_PER_MICROSTEP
        y_microns = self.y_pos_steps * MICRONS_PER_MICROSTEP
        return (x_microns, y_microns)

    def move_to(self, target_x_um, target_y_um, snap_to_stable_step=True):
        """
        Moves to an absolute position with backlash compensation and optional step snapping for stability.
        """
        # --- Rule 1 Implementation (Holding Torque) ---
        stable_step_size_um = 8 * MICRONS_PER_MICROSTEP # Approx 0.762 µm
        
        final_target_x = target_x_um
        final_target_y = target_y_um
        
        if snap_to_stable_step:
            # Round the user's target to the nearest stable step position for maximum holding torque
            final_target_x = round(target_x_um / stable_step_size_um) * stable_step_size_um
            final_target_y = round(target_y_um / stable_step_size_um) * stable_step_size_um
            if (final_target_x != target_x_um) or (final_target_y != target_y_um):
                print(f"Note: Target snapped to stable position: ({final_target_x:.3f}, {final_target_y:.3f}) µm")

        # --- Boundary Check ---
        if not (0 <= final_target_x <= X_LIMIT_UM and 0 <= final_target_y <= Y_LIMIT_UM):
            print(f"⚠️ Move aborted: Target ({final_target_x:.2f}, {final_target_y:.2f}) is outside allowed limits.")
            return

        # --- Rule 2 Implementation (Backlash Compensation) ---
        print(f"Moving to ({final_target_x:.3f}, {final_target_y:.3f}) µm with backlash compensation...")
        
        # 1. Define an overshoot position. Move past the target on both axes.
        overshoot_x = final_target_x - BACKLASH_COMP_UM # Move further LEFT
        overshoot_y = final_target_y + BACKLASH_COMP_UM # Move further UP

        # 2. Move to the overshoot position first
        self._execute_move(overshoot_x, overshoot_y)
        
        # 3. Move backward to the final, stable target position. This is the "reverse approach".
        print("Performing final reverse approach...")
        self._execute_move(final_target_x, final_target_y)

    def _execute_move(self, target_x_um, target_y_um):
        """A private helper method that calculates and executes a single, direct move."""
        current_x_um, current_y_um = self.get_position()
        
        # Calculate distance to move in the user's coordinate system
        delta_x_user = target_x_um - current_x_um
        delta_y_user = target_y_um - current_y_um
        
        # Invert the X-axis for the hardware, since user's positive X is left.
        delta_x_hardware = -delta_x_user
        # Y-axis is standard: user's positive Y (up) is also hardware's positive Y.
        delta_y_hardware = delta_y_user
        
        # Convert distances from microns to microsteps for the hardware command
        steps_to_move_x = round(delta_x_hardware / MICRONS_PER_MICROSTEP)
        steps_to_move_y = round(delta_y_hardware / MICRONS_PER_MICROSTEP)
        
        # Command the move if there's any distance to travel
        if steps_to_move_x != 0 or steps_to_move_y != 0:
            self.mcl.move_three_axes_m(
                1, DEFAULT_VELOCITY, steps_to_move_x,  # Axis 1 (X)
                2, DEFAULT_VELOCITY, steps_to_move_y,  # Axis 2 (Y)
                0, 0, 0,                               # Axis 3
                self.handle
            )
            self._wait_for_move()
        
        # Update our internal position to reflect the new commanded location
        self.set_position(target_x_um, target_y_um)

    def set_position(self, x_um=0, y_um=0):
        """Resets the internal counters to define the current physical location as (x, y) µm."""
        self.x_pos_steps = round(x_um / MICRONS_PER_MICROSTEP)
        self.y_pos_steps = round(y_um / MICRONS_PER_MICROSTEP)

    def close(self):
        """Releases the hardware handle to ensure it can be used by other programs."""
        if self.handle and self.mcl:
            self.mcl.release_handle(self.handle)
            self.handle = None # Prevent reuse
            print("Hardware handle released.")


# --- Example Usage ---
if __name__ == "__main__":
    stage = None
    try:
        # Create an instance of our controller
        stage = EncoderlessMicrostage()
        
        # 1. Calibrate the origin by running the homing sequence
        stage.find_home()
        
        # 2. Test a valid move within the 12x12 µm limits
        print("\n--- Testing a valid move ---")
        stage.move_to(10.5, 8.2) 
        print(f"Final position read from wrapper: {stage.get_position()}")
        
        # 3. Test a move that is outside the software limits
        print("\n--- Testing an invalid move ---")
        stage.move_to(15, 10) # Should be aborted by the boundary check
        
        # 4. Return the stage to its defined home position
        print("\n--- Returning home ---")
        stage.return_to_home()
        print(f"Final position read from wrapper: {stage.get_position()}")
        
    except Exception as e:
        print(f"\nAn error occurred in the main script: {e}")
    finally:
        # This 'finally' block ensures the connection is closed even if an error occurs
        if stage:
            stage.close()