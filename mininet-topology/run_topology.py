import os
import sys

mode = os.getenv("MODE", "baseline").lower()

if mode == "baseline":
    from topology_baseline import main as run_topo
elif mode in ["sdn", "sdn_qlearning"]:
    from topology_sdn import main as run_topo
else:
    print(f"MODE '{mode}' không hợp lệ. Chọn baseline, sdn hoặc sdn_qlearning.")
    sys.exit(1)

run_topo()
