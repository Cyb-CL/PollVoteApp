#!/bin/bash
set -e

# Navigate to repository root directory
cd "$(dirname "$0")"

# Search and append common Docker Desktop paths if kubectl is missing from PATH
if ! command -v kubectl &> /dev/null && ! command -v kubectl.exe &> /dev/null; then
    for bin_path in \
        "/c/Program Files/Docker/Docker/resources/bin" \
        "/c/Users/$USER/AppData/Local/Programs/DockerDesktop/resources/bin" \
        "$LOCALAPPDATA/Programs/DockerDesktop/resources/bin" \
        "$HOME/AppData/Local/Programs/DockerDesktop/resources/bin"; do
        if [ -d "$bin_path" ]; then
            export PATH="$bin_path:$PATH"
            break
        fi
    done
fi

# Map kubectl and docker to .exe if running on Windows/Git Bash without extension
if ! command -v kubectl &> /dev/null && command -v kubectl.exe &> /dev/null; then
    kubectl() { kubectl.exe "$@"; }
fi
if ! command -v docker &> /dev/null && command -v docker.exe &> /dev/null; then
    docker() { docker.exe "$@"; }
fi

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "Error: kubectl is not installed or not in PATH."
    if grep -qi microsoft /proc/version 2>/dev/null; then
        echo "--> Detected WSL: run './setup.sh' via Git Bash or install kubectl inside WSL."
    fi
    exit 1
fi

# Parse optional arguments
BUILD_IMAGES=false

for arg in "$@"; do
    case "$arg" in
        --build) BUILD_IMAGES=true ;;
        -h|--help)
            echo "Usage: ./setup.sh [--build]"
            echo "  --build      Rebuild Docker images locally before deploying"
            exit 0
            ;;
    esac
done

# Function to start or connect to a local Kubernetes cluster
start_kubernetes() {
    echo "==> Kubernetes is not responding. Attempting to start cluster..."

    # 1. Docker Desktop on Windows (preferred: exposes LoadBalancer services on localhost)
    if [ -f "$LOCALAPPDATA/Programs/DockerDesktop/Docker Desktop.exe" ]; then
        echo "==> Launching Docker Desktop..."
        "$LOCALAPPDATA/Programs/DockerDesktop/Docker Desktop.exe" &
    elif [ -f "/c/Program Files/Docker/Docker/Docker Desktop.exe" ]; then
        echo "==> Launching Docker Desktop..."
        "/c/Program Files/Docker/Docker/Docker Desktop.exe" &
    # 2. Docker Desktop on macOS
    elif [[ "$OSTYPE" == "darwin"* ]] && [ -d "/Applications/Docker.app" ]; then
        echo "==> Launching Docker Desktop on macOS..."
        open -a Docker || true
    # 3. Minikube
    elif command -v minikube &> /dev/null; then
        echo "==> Starting Minikube..."
        minikube start
    # 4. Kind
    elif command -v kind &> /dev/null; then
        echo "==> Starting Kind cluster..."
        kind create cluster --name pollvoteapp || true
    # 5. MicroK8s
    elif command -v microk8s &> /dev/null; then
        echo "==> Starting MicroK8s..."
        microk8s start
    # 6. Docker Desktop via PowerShell (installed in a non-standard location)
    elif command -v powershell.exe &> /dev/null; then
        echo "==> Launching Docker Desktop via PowerShell..."
        powershell.exe -NoProfile -Command "& { if (Test-Path \"`$env:LOCALAPPDATA\Programs\DockerDesktop\Docker Desktop.exe\") { Start-Process \"`$env:LOCALAPPDATA\Programs\DockerDesktop\Docker Desktop.exe\" } elseif (Test-Path \"`$env:ProgramFiles\Docker\Docker\Docker Desktop.exe\") { Start-Process \"`$env:ProgramFiles\Docker\Docker\Docker Desktop.exe\" } }" || true
    # 7. Docker daemon on Linux
    elif command -v systemctl &> /dev/null; then
        echo "==> Starting Docker daemon..."
        systemctl --user start docker-desktop 2>/dev/null || sudo systemctl start docker 2>/dev/null || true
    else
        echo "==> No automated Kubernetes manager found."
    fi

    # Wait for Kubernetes control plane to become ready (up to 90 seconds)
    echo "==> Waiting for Kubernetes cluster to become ready..."
    for i in {1..45}; do
        if kubectl cluster-info &> /dev/null; then
            echo "==> Kubernetes cluster is ready!"
            return 0
        fi
        sleep 2
    done

    echo "Error: Timed out waiting for Kubernetes cluster."
    echo "Please ensure Docker Desktop (with Kubernetes enabled) or Minikube/Kind is running."
    exit 1
}

# Ensure Kubernetes cluster is running
if ! kubectl cluster-info &> /dev/null; then
    start_kubernetes
else
    echo "==> Kubernetes cluster is active."
fi

# Docker registry username and tag (customizable via environment variables)
DOCKER_USER="${DOCKER_USER:-leco26}"
IMAGE_TAG="${IMAGE_TAG:-v1}"

# Rebuild Docker images if requested
if [ "$BUILD_IMAGES" = true ]; then
    if ! command -v docker &> /dev/null; then
        echo "Error: docker is not installed or not in PATH."
        exit 1
    fi

    echo "==> Building Docker images (${DOCKER_USER}/<service>:${IMAGE_TAG})..."
    docker build -t "${DOCKER_USER}/auth-service:${IMAGE_TAG}" ./Containers/AuthService
    docker build -t "${DOCKER_USER}/poll-service:${IMAGE_TAG}" ./Containers/PollService
    docker build -t "${DOCKER_USER}/vote-service:${IMAGE_TAG}" ./Containers/VoteService
    docker build -t "${DOCKER_USER}/frontend:${IMAGE_TAG}" ./Containers/Frontend
fi

# Apply all Kubernetes manifests
echo "==> Applying Kubernetes manifests..."
kubectl apply -f Kubernetes/

# Wait for all deployments to be ready
echo "==> Waiting for all deployments to be ready..."
kubectl rollout status deployment/mongo-deployment --timeout=120s
kubectl rollout status deployment/auth-deployment --timeout=120s
kubectl rollout status deployment/poll-deployment --timeout=120s
kubectl rollout status deployment/vote-deployment --timeout=120s
kubectl rollout status deployment/frontend-deployment --timeout=120s

# Display current cluster status
echo ""
echo "==> Cluster Status:"
kubectl get pods
echo ""
kubectl get svc

# Returns success if something is listening on localhost:<port>
port_is_open() {
    (echo > "/dev/tcp/127.0.0.1/$1") &> /dev/null
}

# Give the cluster a few seconds to expose the LoadBalancer services on localhost
# (Docker Desktop does this; Minikube and Kind do not)
echo ""
echo "==> Checking if services are reachable on localhost..."
for i in {1..10}; do
    port_is_open 9090 && break
    sleep 2
done

# Start a port-forward for every service not already reachable on localhost
FORWARDS=("frontend-service:9090" "auth-service:8003" "poll-service:8001" "vote-service:8002")
FORWARD_STARTED=false

for entry in "${FORWARDS[@]}"; do
    svc="${entry%%:*}"
    port="${entry##*:}"
    if port_is_open "$port"; then
        echo "    localhost:$port already reachable ($svc)"
    else
        echo "    localhost:$port not reachable -> starting port-forward to $svc"
        kubectl port-forward "svc/$svc" "$port:$port" > /dev/null &
        FORWARD_STARTED=true
    fi
done

echo ""
echo "=========================================="
echo " PollVoteApp is ready!"
echo " - Web UI:        http://localhost:9090"
echo "=========================================="


if [ "$FORWARD_STARTED" = true ]; then
    echo ""
    echo " Port-forwarding is active: keep this terminal open."
    echo " Press Ctrl+C to stop (the pods keep running in the cluster)."
    trap 'kill $(jobs -p) 2>/dev/null; exit 0' INT TERM
    wait
fi
