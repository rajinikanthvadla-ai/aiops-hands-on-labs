import json
import os
import subprocess
import sys

try:
    import joblib
    import numpy as np
    import pandas as pd
    from sklearn.linear_model import LinearRegression
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "/workspace/app/requirements.txt"])
    import joblib
    import numpy as np
    import pandas as pd
    from sklearn.linear_model import LinearRegression

DATA_FILE = "/workspace/data/predictive_metrics.csv"
MODEL_FILE = "/workspace/model/failure_model.pkl"
FEATURE_FILE = "/workspace/model/features.json"


def find_crossing_hour(values, limit):
    for hour, value in enumerate(values, start=1):
        if value >= limit:
            return hour
    return None


def main():
    if not os.path.exists(DATA_FILE):
        raise FileNotFoundError(f"Missing data file: {DATA_FILE}")
    if not os.path.exists(MODEL_FILE):
        raise FileNotFoundError(f"Missing model file: {MODEL_FILE}. Run training Job first.")
    if not os.path.exists(FEATURE_FILE):
        raise FileNotFoundError(f"Missing feature file: {FEATURE_FILE}. Run training Job first.")

    df = pd.read_csv(DATA_FILE)
    model = joblib.load(MODEL_FILE)

    with open(FEATURE_FILE, "r", encoding="utf-8") as f:
        features = json.load(f)

    latest_metrics = pd.DataFrame([{
        "cpu_usage": 89,
        "memory_usage": 91,
        "disk_usage": 86,
        "latency_ms": 1300,
        "error_rate": 8,
        "pod_restarts": 5,
        "db_connections": 920,
        "request_count": 4200,
    }])

    failure_prediction = model.predict(latest_metrics[features])[0]
    failure_probability = model.predict_proba(latest_metrics[features])[0][1] * 100

    df["hour_index"] = range(len(df))

    disk_model = LinearRegression()
    disk_model.fit(df[["hour_index"]], df["disk_usage"])

    future_hours = np.array(range(len(df), len(df) + 24)).reshape(-1, 1)
    disk_forecast = disk_model.predict(future_hours)
    disk_cross_hour = find_crossing_hour(disk_forecast, 90)

    sla_model = LinearRegression()
    sla_model.fit(df[["hour_index"]], df["latency_ms"])
    latency_forecast = sla_model.predict(future_hours)
    sla_cross_hour = find_crossing_hour(latency_forecast, 500)

    risk_level = "HIGH" if failure_prediction == 1 else "LOW"
    disk_risk = f"After {disk_cross_hour} hour(s)" if disk_cross_hour else "No risk in next 24 hours"
    sla_risk = f"After {sla_cross_hour} hour(s)" if sla_cross_hour else "No breach in next 24 hours"

    alert = f"""
AIOPS PREDICTIVE MAINTENANCE ALERT

Service: payment-service
Environment: production

Current Health Signals:
CPU Usage: {latest_metrics.iloc[0]['cpu_usage']}%
Memory Usage: {latest_metrics.iloc[0]['memory_usage']}%
Disk Usage: {latest_metrics.iloc[0]['disk_usage']}%
Latency: {latest_metrics.iloc[0]['latency_ms']} ms
Error Rate: {latest_metrics.iloc[0]['error_rate']}%
Pod Restarts: {latest_metrics.iloc[0]['pod_restarts']}
DB Connections: {latest_metrics.iloc[0]['db_connections']}
Request Count: {latest_metrics.iloc[0]['request_count']}

Prediction Result:
Failure Risk: {risk_level}
Failure Probability: {round(failure_probability, 2)}%

Resource Forecast:
Disk 90% Risk: {disk_risk}

SLA Forecast:
Latency SLA Breach: {sla_risk}

Possible Root Cause:
High CPU, high memory, increased latency, high error rate, and pod restarts indicate possible service degradation.

Recommended Actions:
1. Check recent deployment for payment-service
2. Check Kubernetes pod logs
3. Check database connection pool
4. Scale replicas using HPA
5. Increase disk volume if disk forecast is risky
6. Check downstream service latency
7. Prepare rollback if issue started after release

Business Impact:
If no action is taken, users may face payment failures or slow checkout experience.
"""

    print(alert)


if __name__ == "__main__":
    main()
