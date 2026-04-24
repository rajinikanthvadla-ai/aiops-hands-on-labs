# AIOps Hands-On Labs

## Class 2: Real-Time Data Collection And Anomaly Detection

End state: a small workload runs in Kubernetes, you drive traffic from your machine (Postman or `curl`), telemetry flows through OpenTelemetry into metrics, logs, and traces, and a detector scores anomalies from live Prometheus series.

```text
Postman/curl -> aiops-app -> OTLP -> OpenTelemetry Collector -> Prometheus (metrics)
                                                    |-> Jaeger (traces)
                                                    |-> debug logs (collector)
Pod stdout -> Promtail -> Loki
Grafana -> Prometheus + Loki + Jaeger (one UI)
Prometheus <- anomaly-detector (every ~10s: PromQL + score, prints JSON to stdout)
```

---

## What This Lab Uses And Why

| Piece | Role | Why it is here |
|--------|------|----------------|
| **Kubernetes (`kind` or EKS)** | Runs all services the same way as production | Isolated namespace, networking between pods, realistic deploy model |
| **`aiops-app`** | HTTP API you hit with Postman | Without a real app there is nothing to measure; load and errors come from your requests |
| **OpenTelemetry Collector** | Ingest OTLP, batch, route signals | One standard ingress for metrics, logs, traces instead of many ad-hoc agents |
| **Prometheus** | Time-series store and query API | Industry default for SLO-style metrics and for the detector to read live rates |
| **Jaeger** | Trace storage and UI | See latency and attributes per request (APM view) |
| **Loki** | Log store | Cheap log aggregation aligned with labels (namespace, pod) |
| **Promtail** | Ship container logs to Loki | Kubernetes pods write to node log paths; Promtail tails and pushes |
| **Grafana** | Explore and dashboards | One place to query Prometheus, Loki, and Jaeger without memorizing three UIs |
| **`anomaly-detector`** | Every ~10s: PromQL → River + stats → JSON stdout | Detection runs **next to** the app, not inside each HTTP request; see section below |

---

## Repo Layout

```bash
cd labs/class-2
```

| Path | Purpose |
|------|---------|
| `labs/class-2/k8s/` | All manifests (`00`…`08`) |
| `labs/class-2/scripts/` | `create-kind-cluster.sh`, `create-eks-cluster.sh`, `deploy.sh`, `cleanup-kind.sh` |

---

## Prerequisites

- `kubectl`
- `kind` + Docker (local)
- `curl`

Optional (cloud):

- `aws`, `eksctl`

---

## Run The Entire Lab (kind)

```bash
cd labs/class-2
bash scripts/create-kind-cluster.sh
bash scripts/deploy.sh
kubectl get pods -n aiops -w
```

Wait until every pod in `aiops` is `Running` (Promtail is a DaemonSet: one pod per node).

---

## Run The Entire Lab (EKS)

```bash
cd labs/class-2
bash scripts/create-eks-cluster.sh us-east-1
bash scripts/deploy.sh
kubectl get pods -n aiops -w
```

Same manifests; only the cluster creation differs.

---

## Where detection runs (strict map)

- **Not in `aiops-app`.** The Flask app only counts traffic and sends OTLP metrics (`k8s/04-simulator.yaml`).
- **All of `zscore`, `multivariate`, `ml_score`, `anomaly` are computed in one place:** the inline Python inside **`labs/class-2/k8s/05-detector.yaml`** (container `args`, hereafter “the script”).

| JSON field | Script lines | What it is |
|------------|--------------|------------|
| Inputs `latency`, `error_rate` | 41–42, 28–29 | Two PromQL instant queries against Prometheus; refreshed each loop. |
| `ml_score` | 48–50 | River **HalfSpaceTrees** `score_one` on `x = {latency, error_rate}` then `learn_one` updates the tree. Higher = more “odd” vs what it has seen. |
| `zscore` (`z`) | 52–56 | Z-score of **current latency** vs the last **≤30** latency samples in `lat_hist` (mean/std). |
| `multivariate` (`m`) | 57–65 | Distance of **(latency, error_rate)** from the mean of recent pairs, using **covariance + pseudo-inverse** (Mahalanobis-style). |
| `anomaly` | 66 | `true` if **any** of: `|z|>3`, `m>3.2`, or (after warm-up) `ml_score>0.92`. |
| Output | 67–68 | One `print(json.dumps(...))` per loop → pod **stdout** → Promtail → Loki. |

**“Real time” in this lab:** the script’s `while True` loop: **query Prometheus → update history → score → print → `sleep(10)`** (see lines 39–71). So you see a new decision about every **10s**, after Prometheus has scraped (~15s in `k8s/03-prometheus.yaml`).

**Watch live:** `kubectl logs -n aiops deploy/anomaly-detector -f --tail=20` or Loki `{namespace="aiops",pod=~"anomaly-detector.*"}`. `detector_error` lines (lines 69–70) are bugs inside the script (e.g. SVD/cov edge cases), not HTTP errors from the app.

**Alerts:** this repo does **not** ship Grafana alert rules. The detector does **not** expose its own Prometheus metric; it only prints JSON. Easiest path: **Grafana Alerting → New alert rule → choose Loki** → use a query that fires when a true anomaly appears, for example:

```logql
sum(count_over_time({namespace="aiops",pod=~"anomaly-detector.*"} |= `"anomaly": true` [1m])) > 0
```

Or parse JSON: `{namespace="aiops",pod=~"anomaly-detector.*"} | json | anomaly == true` — alert when that query has results / count > 0 over your window (Grafana: Alerting → New rule → Loki; evaluation ~1m; tune “for” to cut noise).

### Step-by-step: Grafana alert (Loki) → email

**Part A — SMTP (mail server). Without this, email never sends.**

1. Open `labs/class-2/k8s/08-grafana.yaml` → under the `grafana` container `env:`, add your provider’s settings (do **not** commit real passwords to git):

```yaml
            - name: GF_SMTP_ENABLED
              value: "true"
            - name: GF_SMTP_HOST
              value: "smtp.example.com:587"
            - name: GF_SMTP_USER
              value: "smtp-user"
            - name: GF_SMTP_PASSWORD
              value: "smtp-secret"
            - name: GF_SMTP_FROM_ADDRESS
              value: "grafana-lab@example.com"
```

2. `kubectl apply -f k8s/08-grafana.yaml` → `kubectl rollout restart deploy/grafana -n aiops` → wait until the pod is Ready.

**Part B — Contact point (who receives mail)**

3. In Grafana UI: left menu **Alerting** → **Contact points** → **Add contact point**.  
4. **Name:** e.g. `team-email`. **Integration:** **Email**. **Addresses:** team mailbox. **Save**.  
5. Click **Test** (if available). If it fails, SMTP in Part A is still wrong or blocked.

**Part C — Alert rule (what triggers mail)**

6. **Alerting** → **Alert rules** → **New alert rule**.  
7. **Rule name:** e.g. `detector-anomaly`.  
8. **Query A:** datasource **Loki**. Set query type to **Range** (not Instant). Time range **10m**, step **1m**. Paste:

```logql
sum(count_over_time({namespace="aiops",pod=~"anomaly-detector.*"} |= `"anomaly": true` [1m]))
```

9. **Add expression** → **Reduce** → input **A** → function **Last** → mode **Strict** → name it **B**.  
10. **Add expression** → **Threshold** → input **B** → **Is above** `0` → name it **C**. Click **Set as alert condition** on **C**.  
11. **Rule type:** Grafana-managed. **Folder:** pick or create `class-2`.  
12. **Evaluation group:** **New evaluation group** → name `aiops` → interval **1m** (required).  
13. **Pending period:** e.g. `2m` (wait in breach before firing).  
14. **Notifications:** **Contact point** → choose `team-email` (from step 4).  
15. **Save rule** or **Save rule and exit**.

**If it never fires:** In **Explore → Loki**, confirm lines contain exactly `"anomaly": true` (space after `:`). Drive traffic / detector until that appears; widen range to **15m** in query A if needed.

---

## How To Test (Checklist)

Do these in order once the cluster is up.

### 1) Port-forward the app

```bash
kubectl port-forward -n aiops svc/aiops-app 8080:8080
```

Open [http://localhost:8080](http://localhost:8080) for the live app page.
From this page you can:
- send single normal/high/error requests
- run continuous load by setting RPS and duration
- watch live request results in the page output panel

### 2) Generate traffic

**Postman:** `POST` `http://localhost:8080/api/infer`  
Header: `Content-Type: application/json`  
Body examples:

```json
{"load":1}
```

```json
{"load":5}
```

```json
{"load":5,"force_error":true}
```

**Or shell (no Postman):**

```bash
for i in $(seq 1 30); do curl -sS -X POST http://localhost:8080/api/infer -H 'Content-Type: application/json' -d '{"load":3}' ; echo; sleep 0.2; done
```

### 3) Confirm the app and collector see work

```bash
kubectl logs -n aiops deploy/aiops-app --tail=30
kubectl logs -n aiops deploy/otel-collector --tail=40
```

### 4) Prometheus

```bash
kubectl port-forward -n aiops svc/prometheus 9090:9090
```

Open [http://localhost:9090](http://localhost:9090) → Graph → run:

- `rate(requests_total[1m])`
- `rate(request_latency_ms_sum[1m]) / rate(request_latency_ms_count[1m])`
- `rate(request_errors_total[1m]) / rate(requests_total[1m])`

CLI:

```bash
curl --get --data-urlencode 'query=rate(requests_total[1m])' 'http://localhost:9090/api/v1/query'
```

### 5) Jaeger

```bash
kubectl port-forward -n aiops svc/jaeger-query 16686:16686
```

Open [http://localhost:16686](http://localhost:16686) → Service `aiops-app` → Find Traces → open a span and read attributes (`latency_ms`, `error`, `load`).

### 6) Grafana (Prometheus + Loki + Jaeger)

```bash
kubectl port-forward -n aiops svc/grafana 3000:3000
```

Open [http://localhost:3000](http://localhost:3000) — login `admin` / `admin`.

- **Connections → Data sources:** Prometheus, Loki, Jaeger should exist.
- **Explore → Prometheus:** `rate(requests_total[1m])`
- **Explore → Loki:** use **Code** mode, **Last 15 minutes**, and a **line limit** of 2000–5000 so you are not truncated at 1000 lines.
- **Explore → Jaeger:** service `aiops-app`, recent lookback, search.

#### Loki LogQL (copy-paste for class testing)

Generate traffic first: open the app `/` (port-forward `aiops-app` if needed) and use **Send error** or **Start load**, or call **POST** `/api/infer` from Postman with `{"load":3,"force_error":true}` so 500s and `"error": 1` lines exist.

- **Everything in the lab namespace**

```logql
{namespace="aiops"}
```

- **Only `aiops-app` pod stdout**

```logql
{namespace="aiops",pod=~"aiops-app.*"}
```

- **`/api/infer` responses that are 4xx or 5xx** (Werkzeug access log)

```logql
{namespace="aiops",pod=~"aiops-app.*"} |= "/api/infer" |~ " (4[0-9]{2}|5[0-9]{2}) "
```

- **`/api/infer` returned 500**

```logql
{namespace="aiops",pod=~"aiops-app.*"} |= "/api/infer" |= " 500 "
```

- **App JSON log when the handler marked an error** (`"error": 1` in the body)

```logql
{namespace="aiops",pod=~"aiops-app.*"} |= "\"error\": 1"
```

- **Broad text match** (noisy; catches many stack traces / messages)

```logql
{namespace="aiops",pod=~"aiops-app.*"} |~ "(?i)(error|exception|fail|traceback)"
```

- **Anomaly detector pod** (narrow with `|= "detector_error"` when you want only those lines)

```logql
{namespace="aiops",pod=~"anomaly-detector.*"}
```

**Note:** Client-only failures (wrong URL, TLS, connection refused from Postman) never hit the pod, so they **do not** appear in Loki—only server-side logs do.

If Loki shows **no logs**, Promtail is usually not tailing the node: the DaemonSet sets **`HOSTNAME` from `spec.nodeName`** so it matches the `__host__` relabel (pod name alone does not). The `__path__` glob must also match kubelet paths under `/var/log/pods/`.

Apply the Promtail manifest and restart Promtail:

```bash
cd labs/class-2
kubectl apply -f k8s/07-promtail.yaml
kubectl rollout restart ds/promtail -n aiops
kubectl rollout status ds/promtail -n aiops
```

Verify Promtail is actually tailing files (should not spam `no such file` errors):

```bash
kubectl logs -n aiops ds/promtail --tail=80
```

If you only see startup lines and still no Grafana logs, verify the node log paths exist inside Promtail:

```bash
kubectl exec -n aiops ds/promtail -- sh -lc 'ls /var/log/pods | head'
kubectl exec -n aiops ds/promtail -- sh -lc 'ls /var/lib/containerd 2>/dev/null | head; ls /var/lib/docker/containers 2>/dev/null | head'
```

If you only see startup lines and still no Grafana logs, verify Loki actually has labels:

```bash
kubectl port-forward -n aiops svc/loki 3100:3100
```

If `3100` is already used on your laptop, bind a different local port:

```bash
kubectl port-forward -n aiops svc/loki 13100:3100
curl -sS "http://localhost:13100/loki/api/v1/labels"
```

Before port-forward, confirm Loki is actually ready:

```bash
kubectl get pods -n aiops -l app=loki
```

If port-forward prints `connection refused` to pod port `3100`, it means **nothing is listening inside the Loki container yet** (usually still starting/crashloop). Check:

```bash
kubectl logs -n aiops deploy/loki --tail=120
```

If the JSON shows `"data":[]` (empty), Loki has received **no streams** yet. That means Promtail is still not tailing/pushing.

If you only see `{"status":"success"}` and **no `data` field at all**, you are not talking to Loki (wrong local port/process) or Loki is not serving the API you think. Use `curl -i` on the forwarded port and confirm `HTTP/1.1 200`.

Then widen the Grafana time range to **Last 15 minutes** and retry the queries in **Loki LogQL (copy-paste for class testing)** above (start with `{namespace="aiops"}` or `{namespace="aiops",pod=~"aiops-app.*"}`).

If Grafana shows `dial tcp ...:3100: connect: connection refused`, recycle Loki + Promtail so versions/config match:

```bash
cd labs/class-2
kubectl apply -f k8s/06-loki.yaml
kubectl apply -f k8s/07-promtail.yaml
kubectl rollout restart deploy/loki -n aiops
kubectl rollout restart ds/promtail -n aiops
kubectl rollout status deploy/loki -n aiops
kubectl rollout status ds/promtail -n aiops
kubectl get endpoints -n aiops loki
```

If Loki logs show `creating WAL folder at "/wal": mkdir wal: permission denied`, apply the latest `k8s/06-loki.yaml` (WAL is redirected to `/loki/wal` on the mounted volume) and restart Loki again.

### 7) Anomaly detector

```bash
kubectl logs -n aiops deploy/anomaly-detector -f
```

Keep sending requests while you watch; the detector polls Prometheus on an interval.

---

## What To Observe (By Scenario)

| You send | Prometheus | Jaeger | Loki (app pod) | Detector JSON |
|-----------|------------|--------|----------------|-----------------|
| `{"load":1}` | `requests_total` rises; latency histogram near baseline; error ratio near zero | Spans short; `error` mostly 0 | JSON lines with small `latency_ms` | `zscore` small; `anomaly` usually false |
| `{"load":5}` many times | Latency rate up; errors may tick up | Spans longer; `load` high | `latency_ms` higher | `zscore` or `multivariate` or `ml_score` can cross; `anomaly` may flip true |
| `{"load":5,"force_error":true}` | Error ratio jumps on failures | Some traces with `error` 1 | log lines include `"error": 1` style payload | error-related multivariate signal moves |

**Important:** metrics and detector output only move when HTTP traffic exists. If nothing calls `/api/infer`, Prometheus counters stay flat and the detector has little to score.

---

## What You Take Away

- How OTLP enters a collector and splits into metrics vs traces.
- How Promtail labels pod logs into Loki for search in Grafana.
- How PromQL expresses rates and ratios used by detection logic.
- How one request produces three observability views: metric time series, trace timeline, log line.

---

## Cleanup

**kind:**

```bash
cd labs/class-2
bash scripts/cleanup-kind.sh
```

**EKS:**

```bash
kubectl delete namespace aiops
eksctl delete cluster --name aiops-lab --region us-east-1
```
