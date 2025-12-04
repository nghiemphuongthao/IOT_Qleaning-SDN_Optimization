import argparse
from mininet.log import setLogLevel


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True)
    args = parser.parse_args()

    mode = args.mode.lower()

    if mode == "case1":
        from topologies.case1_static import run
        run()
    elif mode == "case2":
        from topologies.case2_dynamic import run
        run()
    elif mode == "case3":
        from topologies.case3_qos_anomaly import run
        run()
    else:
        print("Invalid mode:", mode)


if __name__ == "__main__":
    setLogLevel("info")
    main()
