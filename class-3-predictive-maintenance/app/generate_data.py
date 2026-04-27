import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

DATA_DIR = "/workspace/data"
OUTPUT_FILE = os.path.join(DATA_DIR, "predictive_metrics.csv")


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    np.random.seed(42)

    rows = []
    start_time = datetime.now() - timedelta(hours=240)

    for i in range(240):
        timestamp = start_time + timedelta(hours=i)

        cpu = np.random.normal(45, 8)
        memory = np.random.normal(55, 7)
        disk = 38 + (i * 0.21) + np.random.normal(0, 2)
        latency = np.random.normal(220, 40)
        error_rate = np.random.normal(1, 0.4)
        pod_restarts = np.random.poisson(0.2)
        db_connections = np.random.normal(300, 40)
        request_count = np.random.normal(5000, 500)
        failure = 0

        if i > 170:
            cpu = np.random.normal(84, 6)
            memory = np.random.normal(87, 5)
            latency = np.random.normal(1150, 220)
            error_rate = np.random.normal(7, 2)
            pod_restarts = np.random.poisson(3)
            db_connections = np.random.normal(850, 90)

            if cpu > 80 and memory > 80 and latency > 900 and error_rate > 5:
                failure = 1

        rows.append([
            timestamp.isoformat(timespec="seconds"),
            round(max(cpu, 1), 2),
            round(max(memory, 1), 2),
            round(min(max(disk, 1), 100), 2),
            round(max(latency, 1), 2),
            round(max(error_rate, 0), 2),
            int(pod_restarts),
            round(max(db_connections, 1), 2),
            round(max(request_count, 1), 2),
            failure,
        ])

    df = pd.DataFrame(rows, columns=[
        "timestamp",
        "cpu_usage",
        "memory_usage",
        "disk_usage",
        "latency_ms",
        "error_rate",
        "pod_restarts",
        "db_connections",
        "request_count",
        "failure",
    ])

    df.to_csv(OUTPUT_FILE, index=False)

    print("Metrics data generated successfully")
    print(f"Saved to: {OUTPUT_FILE}")
    print("Last 5 rows:")
    print(df.tail(5).to_string(index=False))


if __name__ == "__main__":
    main()
