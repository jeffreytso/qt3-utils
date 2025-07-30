import ctypes
from nkt_tools.extreme import Extreme

class Chromatune(Extreme):
    """
    Full Chromatune wrapper, adding all Optical-Filter registers (§6.22)
    plus System type and Pulse-picker ratio from the main board.
    """
    MAIN_ADDR   = 0x00  # Main board
    FILTER_ADDR = 0x07  # Optical Filter module

    def __init__(self, portname=None):
        super().__init__(portname)

    # ─── Main board extensions ──────────────────────────────────────────────

    def get_system_type(self) -> int:
        """Register 0x61 (U8): should return 0x01 for Chromatune."""
        return self.dll.registerReadU8(self.portname,
                                       Chromatune.MAIN_ADDR,
                                       0x61, 0)

    def get_pulse_picker_ratio(self) -> int:
        """Register 0x34 (U16): the pulse-picker division ratio."""
        return self.dll.registerReadU16(self.portname,
                                        Chromatune.MAIN_ADDR,
                                        0x34, 0)

    # ─── Optical Filter module ──────────────────────────────────────────────

    # Identity & errors
    def get_module_address(self) -> int:
        """Register 0x60 (U8): should return 0x07."""
        return self.dll.registerReadU8(self.portname,
                                       Chromatune.FILTER_ADDR,
                                       0x60, 0)

    def get_module_type(self) -> int:
        """Register 0x61 (U8): should return 0x99."""
        return self.dll.registerReadU8(self.portname,
                                       Chromatune.FILTER_ADDR,
                                       0x61, 0)

    def get_filter_error_code(self) -> int:
        """Register 0x67 (U8): nonzero stops emission."""
        return self.dll.registerReadU8(self.portname,
                                       Chromatune.FILTER_ADDR,
                                       0x67, 0)

    # Shutter
    def set_shutter(self, mode: int):
        """0=closed, 1=open, 2=auto. Register 0x30 (U8)."""
        self.dll.registerWriteU8(self.portname,
                                 Chromatune.FILTER_ADDR,
                                 0x30,
                                 ctypes.c_uint8(mode),
                                 0)

    def get_shutter(self) -> int:
        """Read current shutter mode from 0x30."""
        return self.dll.registerReadU8(self.portname,
                                       Chromatune.FILTER_ADDR,
                                       0x30, 0)

    # Power setup
    def set_power_mode(self, mode: int):
        """
        0=Manual, 1=Max, 2=Passive, 3=Active, 4=Tracker.
        Register 0x31 (U8).
        """
        self.dll.registerWriteU8(self.portname,
                                 Chromatune.FILTER_ADDR,
                                 0x31,
                                 ctypes.c_uint8(mode),
                                 0)

    def get_power_mode(self) -> int:
        """Read current power mode from 0x31."""
        return self.dll.registerReadU8(self.portname,
                                       Chromatune.FILTER_ADDR,
                                       0x31, 0)

    # ND filter attenuation
    def set_nd_attenuation(self, attenuation_dB: float):
        """
        0.001 dB resolution. Register 0x33 (U16).
        """
        reg = int(attenuation_dB * 1000)
        self.dll.registerWriteU16(self.portname,
                                  Chromatune.FILTER_ADDR,
                                  0x33,
                                  ctypes.c_uint16(reg),
                                  0)

    def get_nd_attenuation(self) -> float:
        """Read ND attenuation (dB) from 0x33."""
        raw = self.dll.registerReadU16(self.portname,
                                       Chromatune.FILTER_ADDR,
                                       0x33, 0)
        return raw / 1000.0

    # Filter setting (center, bandwidth, power)
    def set_filter(self, center_nm: float, bw_nm: float, power_nW: int):
        """
        Register 0x32 (array):
          index=0 → center (U16, ×0.1 nm)
          index=1 → bandwidth (U16, ×0.1 nm)
          index=2 → power (U32, nW)
        """
        c = ctypes.c_uint16(int(center_nm * 10))
        b = ctypes.c_uint16(int(bw_nm     * 10))
        p = ctypes.c_uint32(int(power_nW))
        self.dll.registerWriteU16(self.portname, Chromatune.FILTER_ADDR,
                                  0x32, c, 0)
        self.dll.registerWriteU16(self.portname, Chromatune.FILTER_ADDR,
                                  0x32, b, 1)
        self.dll.registerWriteU32(self.portname, Chromatune.FILTER_ADDR,
                                  0x32, p, 2)

    def get_filter(self):
        """
        Read back (center_nm, bw_nm, power_nW) from 0x32.
        """
        c = self.dll.registerReadU16(self.portname,
                                     Chromatune.FILTER_ADDR,
                                     0x32, 0) / 10.0
        b = self.dll.registerReadU16(self.portname,
                                     Chromatune.FILTER_ADDR,
                                     0x32, 1) / 10.0
        p = self.dll.registerReadU32(self.portname,
                                     Chromatune.FILTER_ADDR,
                                     0x32, 2)
        return c, b, p

    # Bandwidth limits
    def get_bandwidth_limits(self):
        """
        Register 0x35 (array):
          index=0 → max BW (U16, ×0.1 nm)
          index=1 → min BW (U16, ×0.1 nm)
        """
        mx = self.dll.registerReadU16(self.portname,
                                      Chromatune.FILTER_ADDR,
                                      0x35, 0) / 10.0
        mn = self.dll.registerReadU16(self.portname,
                                      Chromatune.FILTER_ADDR,
                                      0x35, 1) / 10.0
        return mx, mn

    # Read-only metadata
    def get_firmware_version(self) -> int:
        """Register 0x64 (U16): major/minor firmware version."""
        return self.dll.registerReadU16(self.portname,
                                        Chromatune.FILTER_ADDR,
                                        0x64, 0)
    def get_serial_number(self) -> str:
        """Register 0x65: 8-char ASCII serial number."""
        buf = (ctypes.c_char * 8)()
        self.dll.registerReadString(self.portname,
                                    Chromatune.FILTER_ADDR,
                                    0x65,
                                    buf, len(buf))
        return buf.value.decode('ascii')

    def get_status_bits(self) -> int:
        """Register 0x66 (U32): bitmask of filter‐module status flags."""
        return self.dll.registerReadU32(self.portname,
                                        Chromatune.FILTER_ADDR,
                                        0x66, 0)

    # Power & runtime readouts
    def get_photodiode_power(self) -> int:
        """Register 0x76 (U32): photodiode power in nW."""
        return self.dll.registerReadU32(self.portname,
                                        Chromatune.FILTER_ADDR,
                                        0x76, 0)

    def get_estimated_max_power(self) -> int:
        """Register 0x77 (U32): estimated max power in nW."""
        return self.dll.registerReadU32(self.portname,
                                        Chromatune.FILTER_ADDR,
                                        0x77, 0)

    def get_runtime(self) -> int:
        """Register 0x80 (U32): total runtime in seconds."""
        return self.dll.registerReadU32(self.portname,
                                        Chromatune.FILTER_ADDR,
                                        0x80, 0)

    # Spectral data
    def get_spectrum_pixels(self):
        """
        Register 0xE3 (U16[2]): start/end pixel.
        Returns (start, end).
        """
        raw = self.dll.registerReadArray(self.portname,
                                         Chromatune.FILTER_ADDR,
                                         0xE3, count=2, ctype=ctypes.c_uint16)
        return raw[0], raw[1]

    def read_spectral_amplitude(self):
        """
        Register 0xE4: up to 2048 × U16 mW/nm.
        Uses 0x8F as index pointer.
        Returns list of ints.
        """
        start, end = self.get_spectrum_pixels()
        count = end - start
        amps = []
        for i in range(count):
            # set index
            self.dll.registerWriteU32(self.portname,
                                      Chromatune.FILTER_ADDR,
                                      0x8F,
                                      ctypes.c_uint32(i), 0)
            # read amplitude
            val = self.dll.registerReadU16(self.portname,
                                           Chromatune.FILTER_ADDR,
                                           0xE4, 0)
            amps.append(val)
        return amps

    def read_spectral_wavelength(self):
        """
        Register 0xE5: up to 4096 × U16 (×0.02 nm).
        Uses 0x8F as index pointer.
        Returns list of floats in nm.
        """
        start, end = self.get_spectrum_pixels()
        count = end - start
        wls = []
        for i in range(count):
            self.dll.registerWriteU32(self.portname,
                                      Chromatune.FILTER_ADDR,
                                      0x8F,
                                      ctypes.c_uint32(i), 0)
            raw = self.dll.registerReadU16(self.portname,
                                           Chromatune.FILTER_ADDR,
                                           0xE5, 0)
            wls.append(raw * 0.02)
        return wls

    def get_spectrometer_power(self) -> int:
        """Register 0xEE (U32): spectrometer‐based power in nW."""
        return self.dll.registerReadU32(self.portname,
                                        Chromatune.FILTER_ADDR,
                                        0xEE, 0)

    # User text (240 B ASCII)
    def set_user_text(self, text: str):
        """Write up to 240 ASCII chars into 0x8D via byte-by-byte writes."""
        data = text.encode('ascii')[:240]
        for i, b in enumerate(data):
            self.dll.registerWriteU8(self.portname,
                                     Chromatune.FILTER_ADDR,
                                     0x8D,
                                     ctypes.c_uint8(b),
                                     i)
        # zero-terminate remainder
        for i in range(len(data), 240):
            self.dll.registerWriteU8(self.portname,
                                     Chromatune.FILTER_ADDR,
                                     0x8D,
                                     ctypes.c_uint8(0),
                                     i)

    def get_user_text(self) -> str:
        """Read the 240 B ASCII at 0x8D via byte-by-byte reads."""
        chars = []
        for i in range(240):
            val = self.dll.registerReadU8(self.portname,
                                          Chromatune.FILTER_ADDR,
                                          0x8D,
                                          i)
            if val == 0:
                break
            chars.append(val)
        return bytes(chars).decode('ascii')

    # Scripting
    def start_script(self, bank: int, line: int = 0):
        """
        Register 0xF0 (U16[2]):
          index=0 → bank (0 stops, 1..8 starts)
          index=1 → line (0..499)
        """
        self.dll.registerWriteU16(self.portname,
                                  Chromatune.FILTER_ADDR,
                                  0xF0,
                                  ctypes.c_uint16(bank),
                                  0)
        self.dll.registerWriteU16(self.portname,
                                  Chromatune.FILTER_ADDR,
                                  0xF0,
                                  ctypes.c_uint16(line),
                                  1)

    def stop_script(self):
        """Stop any running script (bank=0)."""
        self.start_script(0, 0)

    def get_script_status(self) -> int:
        """Register 0xF6 (U16): bit0=running, bit15=error."""
        return self.dll.registerReadU16(self.portname,
                                        Chromatune.FILTER_ADDR,
                                        0xF6, 0)

    def get_script_error_code(self) -> int:
        """Register 0xF7 (U8): current scripting error code."""
        return self.dll.registerReadU8(self.portname,
                                       Chromatune.FILTER_ADDR,
                                       0xF7, 0)
