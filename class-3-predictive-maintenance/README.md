# Class 3: AIOps Predictive Analytics and Predictive Maintenance Lab

This lab teaches how real companies use predictive analytics in AIOps to predict service failure, capacity risk, SLA breach, and resource exhaustion before the production incident happens.

## What students will learn

By the end of this lab, students will understand:

- How predictive analytics is different from normal monitoring and anomaly detection
- How historical metrics are converted into model features
- How a model is trained once and reused for repeated prediction
- How Kubernetes Jobs and CronJobs run AIOps prediction workloads
- How a PVC stores generated metrics and trained ML model files
- How a real-world alert message is generated from prediction output

## Real-world explanation

Normal monitoring tells us what is happening now.

Example:

```text
CPU crossed 90%. Alert now.
```

Anomaly detection tells us something is abnormal compared to normal behavior.

Example:

```text
Latency is not following normal service pattern.
```

Predictive analytics tells us what may happen soon.

Example:

```text
Disk may cross 90% in the next few hours.
Payment service may fail soon because CPU, memory, latency, error rate, and pod restarts are all increasing together.
```

## Production AIOps architecture

In a real company, the architecture looks like this:

```text
Application Pods
  ↓ expose metrics
Prometheus / Datadog / CloudWatch
  ↓ query metrics
Feature Builder
  ↓ convert raw metrics into useful features
Trained ML Model
  ↓ predict risk
Risk Score
  ↓
Slack / PagerDuty / Jira / Auto-remediation
```

## This Killer Koda lab architecture

This lab mimics the same idea in a simple Kubernetes cluster:

```text
Killer Koda Kubernetes Cluster
  ↓
Kubernetes Job generates fake production metrics
  ↓
Kubernetes Job trains Random Forest failure model
  ↓
Model and data are stored in PVC
  ↓
Kubernetes CronJob loads model every 2 minutes
  ↓
Prediction script prints AIOps alert in pod logs
```

## Important concept for students

In real companies, we do not directly throw raw monitoring data into a model.

Raw metrics are converted into useful features first.

Example:

```text
Raw Prometheus metric:
container_cpu_usage_seconds_total

Converted feature:
CPU usage percentage over last 5 minutes
```

Another example:

```text
Raw metric:
http_requests_total

Converted features:
request_rate_per_minute
error_rate_percentage
5xx_error_count
```

For this beginner lab, we generate CSV data to mimic Prometheus or Datadog historical data.

## Training vs Prediction

Training is not done every second.

Training happens occasionally:

```text
Daily
Weekly
Monthly
After major traffic change
After new incident data is available
```

Prediction happens continuously:

```text
Every 1 minute
Every 5 minutes
Every 10 minutes
```

In this lab:

```text
Training runs as a Kubernetes Job.
Prediction runs as a Kubernetes CronJob.
```

## Folder structure

```text
class-3-predictive-maintenance/
├── README.md
├── requirements.txt
├── Dockerfile
├── app/
│   ├── generate_data.py
│   ├── train_model.py
│   └── predict.py
└── k8s/
    ├── namespace.yaml
    ├── pvc.yaml
    ├── train-job.yaml
    ├── predict-job.yaml
    └── predict-cronjob.yaml
```

## Step 1: Clone the repo in Killer Koda

```bash
git clone https://github.com/rajinikanthvadla-ai/aiops-hands-on-labs.git
cd aiops-hands-on-labs/class-3-predictive-maintenance
```

If this lab is still on the feature branch, use:

```bash
git clone -b class-3-predictive-maintenance-lab https://github.com/rajinikanthvadla-ai/aiops-hands-on-labs.git
cd aiops-hands-on-labs/class-3-predictive-maintenance
```

## Step 2: Create namespace and PVC

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/pvc.yaml
```

Check:

```bash
kubectl get ns
kubectl get pvc -n aiops-class-3
```

Expected:

```text
aiops-model-pvc   Bound
```

## Step 3: Create ConfigMap from Python scripts

This command takes the Python files from the `app` folder and mounts them into Kubernetes pods.

```bash
kubectl create configmap aiops-scripts \
  --from-file=app/ \
  -n aiops-class-3 \
  --dry-run=client -o yaml | kubectl apply -f -
```

Check:

```bash
kubectl get configmap -n aiops-class-3
```

## Step 4: Run training Job

The training Job will:

1. Generate fake production metrics
2. Train a Random Forest failure prediction model
3. Save model file to PVC
4. Save feature list to PVC

Run:

```bash
kubectl apply -f k8s/train-job.yaml
```

Watch:

```bash
kubectl get pods -n aiops-class-3 -w
```

When the training pod shows `Completed`, press `CTRL + C`.

Check logs:

```bash
kubectl logs -n aiops-class-3 job/aiops-train-model
```

Expected output:

```text
Metrics data generated successfully
Training model started
Model saved to /workspace/model/failure_model.pkl
Feature file saved to /workspace/model/features.json
```

## Step 5: Run one-time prediction Job

This is useful for demo before starting CronJob.

```bash
kubectl apply -f k8s/predict-job.yaml
```

Check logs:

```bash
kubectl logs -n aiops-class-3 job/aiops-predict-once
```

Expected output:

```text
AIOPS PREDICTIVE MAINTENANCE ALERT
Service: payment-service
Failure Risk: HIGH
Failure Probability: ...
```

## Step 6: Run prediction as Kubernetes CronJob

This mimics real-world AIOps where prediction runs every few minutes.

```bash
kubectl apply -f k8s/predict-cronjob.yaml
```

Check CronJob:

```bash
kubectl get cronjob -n aiops-class-3
```

Wait for a scheduled run, then check pods:

```bash
kubectl get pods -n aiops-class-3
```

Check latest prediction logs:

```bash
POD=$(kubectl get pods -n aiops-class-3 --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1].metadata.name}')
kubectl logs -n aiops-class-3 $POD
```

## Step 7: Clean up

```bash
kubectl delete -f k8s/predict-cronjob.yaml
kubectl delete -f k8s/predict-job.yaml --ignore-not-found=true
kubectl delete -f k8s/train-job.yaml --ignore-not-found=true
kubectl delete configmap aiops-scripts -n aiops-class-3 --ignore-not-found=true
kubectl delete -f k8s/pvc.yaml
kubectl delete -f k8s/namespace.yaml
```

## How to teach this lab to students

Use this exact explanation:

```text
We are simulating a real production payment service.
The service is not fully down yet, but its symptoms are dangerous.
CPU is increasing.
Memory is increasing.
Latency is increasing.
Error rate is increasing.
Pod restarts are increasing.
Disk is growing slowly.

A normal monitoring system waits until the threshold is crossed.
A predictive AIOps system looks at the trend and says failure may happen soon.
```

## What model is used here?

This lab uses Random Forest Classifier.

Input features:

```text
cpu_usage
memory_usage
disk_usage
latency_ms
error_rate
pod_restarts
db_connections
request_count
```

Output:

```text
0 = Normal
1 = Failure Risk
```

## Why Random Forest?

Random Forest is good for teaching because:

- It is easy to understand
- It works well on tabular metrics
- It can handle multiple signals together
- It does not need deep learning setup
- It gives strong results for beginner AIOps labs

## What is saved after training?

Training Job saves:

```text
/workspace/model/failure_model.pkl
/workspace/model/features.json
/workspace/data/predictive_metrics.csv
```

These files are stored inside the PVC.

Prediction Job and CronJob load the same saved model from PVC.

## Why PVC is used?

PVC is used because Kubernetes pods are temporary.

If a pod dies, files inside the pod disappear.

PVC keeps the model and data safe across pods.

```text
Training Pod writes model to PVC.
Prediction Pod reads model from PVC.
```

## Why CronJob is used?

CronJob is used because prediction should run again and again.

Real-world example:

```text
Every 5 minutes:
Pull latest metrics
Convert metrics into features
Load model
Predict risk
Send alert
Exit
```

## Is sidecar needed?

For this lab, sidecar is not required.

Sidecar is useful when you want pod-level local monitoring.

Predictive analytics usually needs cluster-level and historical metrics, so CronJob or long-running Deployment is better.

## Real-world production upgrade

After students understand this lab, upgrade it like this:

```text
Replace generated CSV with Prometheus API
Store model in S3 or MLflow
Send alert to Slack webhook
Create Jira ticket automatically
Trigger safe auto-remediation
Deploy prediction service as FastAPI
```

## Final student memory hook

```text
Past Data + Current Trend + ML Model = Future Risk Prediction
```

Another line:

```text
Monitoring tells what happened.
Predictive AIOps tells what is going to happen.
```
