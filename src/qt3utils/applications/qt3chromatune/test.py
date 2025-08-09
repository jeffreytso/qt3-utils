import nkt_tools.NKTP_DLL as nkt
from nkt_tools.extreme import Extreme
from nkt_tools.NKTP_DLL import P2PPortResultTypes

PORT_NAME = "ETH0"

# 1) Build the P2P descriptor using str, not bytes
p2p = nkt.pointToPointPortData(
    "192.168.0.139", 10001,   # laser IP + TCP port
    "0.0.0.0",     0,       # bind any local interface
    0,             5000     # protocol=TCP, 5 s timeout
)

# 2) Register it
res = nkt.pointToPointPortAdd(PORT_NAME, p2p)
print(P2PPortResultTypes(res))
if P2PPortResultTypes(res) != "0:P2PSuccess":
    raise RuntimeError("Failed to add Ethernet port")

# 3) Open all ports (including our new P2P one)
ports = nkt.getAllPorts()
nkt.openPorts(ports, autoMode=1, liveMode=1)
print("openPorts →", P2PPortResultTypes(res), f"({res})")
print("getOpenPorts →", nkt.getOpenPorts())

# 4) Instantiate and drive
laser = Extreme()
print("Connected to:", laser.idn())
laser.set_wavelength(600.0)
laser.set_emission(True)

# … your scans …

# 5) Clean up
laser.set_emission(False)
laser.disconnect()
nkt.pointToPointPortDel(PORT_NAME)
nkt.closePorts(PORT_NAME)
