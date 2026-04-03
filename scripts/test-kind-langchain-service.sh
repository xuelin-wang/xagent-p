#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-xagent}"
NAMESPACE="${NAMESPACE:-xagent}"
APP_NAME="${APP_NAME:-langchain-service}"
IMAGE_NAME="${IMAGE_NAME:-xagent-langchain-service:latest}"
KUSTOMIZE_DIR="${KUSTOMIZE_DIR:-deploy/langchain-service}"
DOCKERFILE_PATH="${DOCKERFILE_PATH:-projects/langchain_service/Dockerfile}"
LOCAL_PORT="${LOCAL_PORT:-8000}"
SERVICE_PORT="${SERVICE_PORT:-80}"
QUERY_TEXT="${QUERY_TEXT:-How should I organize a Polylith repo for agent frameworks?}"
KEEP_CLUSTER="${KEEP_CLUSTER:-1}"
PORT_FORWARD_PID=""

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd" >&2
    exit 1
  fi
}

cleanup() {
  if [[ -n "${PORT_FORWARD_PID}" ]]; then
    kill "${PORT_FORWARD_PID}" >/dev/null 2>&1 || true
    wait "${PORT_FORWARD_PID}" 2>/dev/null || true
  fi

  if [[ "${KEEP_CLUSTER}" == "0" ]]; then
    kind delete cluster --name "${CLUSTER_NAME}" >/dev/null 2>&1 || true
  fi
}

print_failure_context() {
  echo "Deployment did not pass smoke tests. Recent cluster state:" >&2
  kubectl get pods,svc -n "${NAMESPACE}" >&2 || true
  kubectl describe deployment "${APP_NAME}" -n "${NAMESPACE}" >&2 || true
  kubectl logs deployment/"${APP_NAME}" -n "${NAMESPACE}" --tail=200 >&2 || true
}

trap cleanup EXIT
trap 'print_failure_context' ERR

require_cmd docker
require_cmd kind
require_cmd kubectl
require_cmd curl

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "OPENAI_API_KEY must be set for the /query smoke test." >&2
  exit 1
fi

if ! kind get clusters | grep -Fxq "${CLUSTER_NAME}"; then
  kind create cluster --name "${CLUSTER_NAME}"
fi

docker build -t "${IMAGE_NAME}" -f "${DOCKERFILE_PATH}" .
kind load docker-image "${IMAGE_NAME}" --name "${CLUSTER_NAME}"

kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret generic openai-api \
  -n "${NAMESPACE}" \
  --from-literal=OPENAI_API_KEY="${OPENAI_API_KEY}" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -k "${KUSTOMIZE_DIR}"
kubectl rollout status deployment/"${APP_NAME}" -n "${NAMESPACE}" --timeout=180s

kubectl port-forward -n "${NAMESPACE}" svc/"${APP_NAME}" "${LOCAL_PORT}:${SERVICE_PORT}" \
  >/tmp/"${APP_NAME}"-port-forward.log 2>&1 &
PORT_FORWARD_PID=$!
sleep 3

echo "Health response:"
curl --fail --silent --show-error "http://127.0.0.1:${LOCAL_PORT}/healthz"
echo

echo "Query response:"
curl --fail --silent --show-error "http://127.0.0.1:${LOCAL_PORT}/query" \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"${QUERY_TEXT}\"}"
echo

echo "kind deployment smoke test passed for ${APP_NAME} in cluster ${CLUSTER_NAME}."
