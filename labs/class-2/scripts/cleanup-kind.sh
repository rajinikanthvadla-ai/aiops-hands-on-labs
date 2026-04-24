#!/usr/bin/env bash
set -euo pipefail
kubectl delete namespace aiops --ignore-not-found
kind delete cluster --name aiops-lab
