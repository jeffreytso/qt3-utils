import sys

def check_ni_setup():
    print("--- Checking NI-DAQmx Setup ---")
    
    # 1. Check Python Library
    try:
        import nidaqmx
        import nidaqmx.system
        print(f"✅ Python 'nidaqmx' library is installed (Version: {nidaqmx.__version__})")
    except ImportError:
        print("❌ Python 'nidaqmx' library is NOT installed.")
        print("   -> Run: pip install nidaqmx")
        return

    # 2. Check System Driver
    try:
        system = nidaqmx.system.System.local()
        # Trying to read the driver version will fail if the driver isn't installed
        driver_ver = system.driver_version
        print(f"✅ NI-DAQmx System Driver is active (Version: {driver_ver.major_version}.{driver_ver.minor_version})")
        
        # 3. List Connected Devices
        print("\n--- Detected Devices ---")
        if len(system.devices) == 0:
            print("   (No devices connected/detected)")
        else:
            for device in system.devices:
                print(f"   Found: {device.name} ({device.product_type})")

    except nidaqmx.errors.DaqError as e:
        print("❌ NI-DAQmx Driver is missing or corrupted.")
        print(f"   Error: {e}")
    except OSError:
        print("❌ NI-DAQmx Driver (C-Level) is NOT installed on Windows.")
        print("   -> Download 'NI-DAQmx Driver' from ni.com")

if __name__ == "__main__":
    check_ni_setup()