import json
import os
import subprocess
import sys

try:
    import joblib
    import pandas as pd
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import classification_report
    from sklearn.model_selection import train_test_split
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "/workspace/app/requirements.txt"])
    import joblib
    import pandas as pd
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import classification_report
    from sklearn.model_selection import train_test_split

DATA_FILE = "/workspace/data/predictive_metrics.csv"
MODEL_DIR = "/workspace/model"
MODEL_FILE = os.path.join(MODEL_DIR, "failure_model.pkl")
FEATURE_FILE = os.path.join(MODEL_DIR, "features.json")

FEATURES = [
    "cpu_usage",
    "memory_usage",
    "disk_usage",
    "latency_ms",
    "error_rate",
    "pod_restarts",
    "db_connections",
    "request_count",
]


def main():
    os.makedirs(MODEL_DIR, exist_ok=True)

    if not os.path.exists(DATA_FILE):
        raise FileNotFoundError(f"Data file not found: {DATA_FILE}. Run generate_data.py first.")

    print("Training model started")
    df = pd.read_csv(DATA_FILE)

    X = df[FEATURES]
    y = df["failure"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.25,
        random_state=42,
        stratify=y,
    )

    model = RandomForestClassifier(
        n_estimators=120,
        random_state=42,
        class_weight="balanced",
    )
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    print("Failure Prediction Model Report")
    print(classification_report(y_test, predictions))

    joblib.dump(model, MODEL_FILE)

    with open(FEATURE_FILE, "w", encoding="utf-8") as f:
        json.dump(FEATURES, f, indent=2)

    print(f"Model saved to {MODEL_FILE}")
    print(f"Feature file saved to {FEATURE_FILE}")


if __name__ == "__main__":
    main()
