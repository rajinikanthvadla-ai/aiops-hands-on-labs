#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../k8s"
kubectl apply -f 00-namespace.yaml
kubectl apply -f 01-otel-collector.yaml
kubectl apply -f 02-jaeger.yaml
kubectl apply -f 03-prometheus.yaml
kubectl apply -f 04-simulator.yaml
kubectl apply -f 05-detector.yaml
kubectl apply -f 06-loki.yaml
kubectl apply -f 07-promtail.yaml
kubectl apply -f 08-grafana.yaml
