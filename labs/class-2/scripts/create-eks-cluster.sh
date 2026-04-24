#!/usr/bin/env bash
set -euo pipefail
REGION="${1:-us-east-1}"
eksctl create cluster --name aiops-lab --region "$REGION" --nodes 2
kubectl config current-context
