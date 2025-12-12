import subprocess
from mininet.log import info


def setup_qos_on_port(
    port_name: str,
    max_rate: int = 10_000_000,
    q0: int = 2_000_000,
    q1: int = 5_000_000,
    q2: int = 10_000_000,
):
    """
    Apply HTB QoS queues on a given OVS port.

    Parameters
    ----------
    port_name : str
        OVS port name (e.g., s0-eth1)
    max_rate : int
        Maximum link rate (bps)
    q0, q1, q2 : int
        Queue max rates (bps)
    """

    cmd = [
        "ovs-vsctl",
        "--", "set", "Port", port_name, "qos=@newqos",
        "--", "--id=@newqos", "create", "QoS", "type=linux-htb",
        f"other-config:max-rate={max_rate}",
        "queues:0=@q0", "queues:1=@q1", "queues:2=@q2",
        "--", "--id=@q0", "create", "Queue", f"other-config:max-rate={q0}",
        "--", "--id=@q1", "create", "Queue", f"other-config:max-rate={q1}",
        "--", "--id=@q2", "create", "Queue", f"other-config:max-rate={q2}",
    ]

    try:
        subprocess.check_call(cmd)
        info(f"*** [QoS] HTB queues applied on {port_name}\n")
    except subprocess.CalledProcessError:
        # QoS may already exist; do not fail experiment
        info(f"*** [QoS] QoS already exists on {port_name} (ignored)\n")
