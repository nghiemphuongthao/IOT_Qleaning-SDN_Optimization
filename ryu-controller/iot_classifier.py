def classify_iot_flow(src_ip, dst_ip, l4_proto, sport, dport):
    # Critical sensors
    sensor_critical = ["10.0.0.2", "10.0.0.3"]

    if src_ip in sensor_critical:
        return "CRITICAL"

    if l4_proto == 17:  # UDP
        return "REALTIME"

    if l4_proto == 6:   # TCP
        return "BULK"

    return "NORMAL"
