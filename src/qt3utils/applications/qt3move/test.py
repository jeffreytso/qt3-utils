"""
Test which NIDAQ AO channel (ao0, ao1, ao2) drives which axis on the NV40/3 CLE.
Writes a voltage to each AO in turn so you can watch which X/Y/Z display changes.
Run from the qt3move directory:  python test_piezo_ao_channels.py
"""
import nidaqmx
import time

DEVICE = "Dev1"
AO_CHANNELS = ["ao0", "ao1", "ao2"]
V_LOW = 0.0
V_HIGH = 5.0
SETTLE_S = 2.0   # seconds at each voltage so you can watch the CLE


def write_ao(device: str, ao_channel: str, voltage: float) -> None:
    with nidaqmx.Task() as task:
        task.ao_channels.add_ao_voltage_chan(f"{device}/{ao_channel}")
        task.write(voltage)


def main():
    print("Piezo AO channel test")
    print("Watch the NV40/3 CLE: which axis (X, Y, Z) changes when each channel is driven?\n")
    print(f"Device: {DEVICE}, channels: {AO_CHANNELS}")
    print(f"Will set each channel to {V_LOW}V for {SETTLE_S}s, then {V_HIGH}V for {SETTLE_S}s.\n")

    for ao_ch in AO_CHANNELS:
        print(f"--- Driving {ao_ch} ---")
        write_ao(DEVICE, ao_ch, V_LOW)
        print(f"  {ao_ch} = {V_LOW} V  (watch CLE for {SETTLE_S}s)")
        time.sleep(SETTLE_S)
        write_ao(DEVICE, ao_ch, V_HIGH)
        print(f"  {ao_ch} = {V_HIGH} V  (watch CLE for {SETTLE_S}s)")
        time.sleep(SETTLE_S)
        write_ao(DEVICE, ao_ch, V_LOW)
        print(f"  {ao_ch} back to {V_LOW} V\n")
        time.sleep(0.5)

    print("Done. Which axis moved for ao0? ao1? ao2?")
    print("Set Piezo X write_channel to the AO that moved the X display, etc.")


if __name__ == "__main__":
    main()