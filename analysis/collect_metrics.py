import os
from pathlib import Path
import pandas as pd


def _safe_read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _case_from_name(name: str) -> str | None:
    for p in ["no_sdn", "sdn_traditional", "sdn_qlearning"]:
        if name.startswith(p + "_") or name.startswith(p + "-") or name == p:
            return p
        if name.startswith(p):
            return p
    return None


def _aggregate_sensors(case: str, raw_dir: Path) -> dict:
    files = sorted(raw_dir.glob(f"{case}_h*.csv"))
    if not files:
        return {}

    rows = []
    for f in files:
        df = _safe_read_csv(f)
        if df.empty:
            continue
        df["host"] = f.stem.split("_")[-1]
        rows.append(df)

    if not rows:
        return {}

    df_all = pd.concat(rows, ignore_index=True)

    for c in ["rtt_ms", "lost", "sent", "bps"]:
        if c in df_all.columns:
            df_all[c] = pd.to_numeric(df_all[c], errors="coerce")

    out = {"case": case}

    for traffic_class in ["critical", "telemetry"]:
        df_c = df_all[df_all.get("class") == traffic_class].copy()
        if df_c.empty:
            continue

        sent = df_c["sent"].fillna(0).sum()
        lost = df_c["lost"].fillna(0).sum()
        loss_pct = (lost / sent * 100.0) if sent > 0 else None

        rtt_mean = None
        if "rtt_ms" in df_c.columns:
            rtt_mean = df_c["rtt_ms"].dropna().mean()

        bps_mean = None
        if "bps" in df_c.columns:
            bps_mean = df_c["bps"].dropna().mean()

        out[f"{traffic_class}_loss_pct"] = loss_pct
        out[f"{traffic_class}_rtt_ms"] = rtt_mean
        out[f"{traffic_class}_bps"] = bps_mean

    if "lost" in df_all.columns and "sent" in df_all.columns:
        total_sent = df_all["sent"].fillna(0).sum()
        total_lost = df_all["lost"].fillna(0).sum()
        out["udp_total_loss_pct"] = (total_lost / total_sent * 100.0) if total_sent > 0 else None

    return out


def _aggregate_server(case: str, raw_dir: Path) -> dict:
    f = raw_dir / f"{case}_server.csv"
    df = _safe_read_csv(f)
    if df.empty:
        return {}

    if "bulk_mbps" in df.columns:
        df["bulk_mbps"] = pd.to_numeric(df["bulk_mbps"], errors="coerce")
        bulk_mean = df[df.get("class") == "bulk"]["bulk_mbps"].dropna().mean()
        return {"bulk_throughput_mbps": bulk_mean}

    return {}


def main():
    shared = Path(os.environ.get("SHARED_DIR", "/shared"))
    raw_dir = shared / "raw"
    out_dir = shared / "results"
    out_dir.mkdir(parents=True, exist_ok=True)

    cases = ["no_sdn", "sdn_traditional", "sdn_qlearning"]

    summaries = []
    for case in cases:
        base = {"case": case}
        base.update(_aggregate_sensors(case, raw_dir))
        base.update(_aggregate_server(case, raw_dir))
        summaries.append(base)

    summary_df = pd.DataFrame(summaries)
    summary_path = out_dir / "summary.csv"
    summary_df.to_csv(summary_path, index=False)

    print("Saved:", summary_path)


if __name__ == "__main__":
    main()
