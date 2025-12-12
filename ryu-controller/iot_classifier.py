from ryu.lib.packet import ipv4, tcp, udp

def classify(pkt, crit_udp=5001, tel_udp=5002, bulk_tcp=5003):
    ip4 = pkt.get_protocol(ipv4.ipv4)
    if not ip4:
        return None
    u = pkt.get_protocol(udp.udp)
    t = pkt.get_protocol(tcp.tcp)
    if u and u.dst_port == crit_udp:
        return "critical"
    if u and u.dst_port == tel_udp:
        return "telemetry"
    if t and t.dst_port == bulk_tcp:
        return "bulk"
    return None
