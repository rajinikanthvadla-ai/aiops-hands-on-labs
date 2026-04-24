#!/usr/bin/env bash
set -euo pipefail
kind create cluster --name aiops-lab
kubectl cluster-info --context kind-aiops-lab
