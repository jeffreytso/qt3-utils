# Up is positive value for Y axis
# left is positive value for X axis
from mcl_wrapper import MCL_Microdrive
import time
try:
    mcl = MCL_Microdrive()
    handle = mcl.init_handle()
except Exception as e:
    print(f"FATAL: Could not connect to the stage. Error: {e}")
    raise

print(f"Connected to stage (Handle: {handle}).")

# print(mcl.get_axis_info(handle))

# print(mcl.axis_information(2, handle))
# print(mcl.axis_information(1, handle))
print(bin(mcl.status(handle)))
mcl.move_m(1, 0.5, -10000, handle)
print(bin(mcl.status(handle)))


# print(bin(mcl.status(handle)))
# print(mcl.current_position_m(1, handle))

# mcl.move_m(1, 0.1, 100, handle)
# while mcl.move_status(handle) == 1:
#     time.sleep(0.1)
# print(bin(mcl.status(handle)))
# print(mcl.current_position_m(1, handle))

# mcl.move_m(1, 0.1, -100, handle)
# while mcl.move_status(handle) == 1:
#     time.sleep(0.1)
# print(bin(mcl.status(handle)))
# print(mcl.current_position_m(1, handle))

# mcl.move_m(2, 0.1, 100, handle)
# while mcl.move_status(handle) == 1:
#     time.sleep(0.1)
# print(bin(mcl.status(handle)))
# print(mcl.current_position_m(2, handle))

# mcl.move_m(2, 0.1, -100, handle)
# while mcl.move_status(handle) == 1:
#     time.sleep(0.1)
# print(bin(mcl.status(handle)))
# print(mcl.current_position_m(2, handle))




# print("Axis 2:" + str(mcl.current_position_m(1, handle)))
# mcl.single_step(1, -1, handle)
# print("Axis 2:" + str(mcl.current_position_m(1, handle)))

# print("Axis 1:" + str(mcl.current_position_m(1, handle)))
# mcl.single_step(1, -1, handle)
# print("Axis 1:" + str(mcl.current_position_m(1, handle)))
# mcl.single_step(1, 1, handle)
# print("Axis 1:" + str(mcl.current_position_m(1, handle)))

# print("Axis 1:" + str(mcl.current_position_m(1, handle)))
# mcl.move(1, 1.0, -1, handle)
# time.sleep(2)
# print("Axis 1:" + str(mcl.current_position_m(1, handle)))
# mcl.move(1, 1.0, 1, handle)
# time.sleep(2)
# print("Axis 1:" + str(mcl.current_position_m(1, handle)))

# print("Axis 2:" + str(mcl.current_position_m(2, handle)))
# mcl.move(2, 1.0, 1, handle)
# time.sleep(2)
# print("Axis 2:" + str(mcl.current_position_m(2, handle)))
# mcl.move(2, 1.0, -1, handle)
# time.sleep(2)
# print("Axis 2:" + str(mcl.current_position_m(2, handle)))

if handle and mcl:
    mcl.release_handle(handle)
    handle = None
    print("Hardware handle released.")