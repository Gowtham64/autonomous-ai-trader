#!/bin/bash
set -euo pipefail

# GCP Deployment Script for Autonomous AI Trading System
# Provisions a Compute Engine VM with Docker, Docker Compose, and launches the stack.

PROJECT_ID="${GCP_PROJECT_ID:-trading-513714}"
ZONE="${GCP_ZONE:-asia-south1-a}" # Mumbai zone for low latency to Indian markets / Asia
INSTANCE_NAME="${GCP_INSTANCE_NAME:-trader-ai-vm}"
MACHINE_TYPE="${GCP_MACHINE_TYPE:-e2-standard-2}"

if [ -z "$PROJECT_ID" ]; then
    echo "ERROR: GCP_PROJECT_ID is not set and no active gcloud project found."
    echo "Run: gcloud config set project <PROJECT_ID>"
    exit 1
fi

echo "=========================================================="
echo "Deploying Trading AI to GCP Compute Engine"
echo "Project:  ${PROJECT_ID}"
echo "Zone:     ${ZONE}"
echo "Instance: ${INSTANCE_NAME}"
echo "Machine:  ${MACHINE_TYPE}"
echo "=========================================================="

# 1. Create Firewall Rule for API/Dashboard (Port 8000)
echo "[1/4] Ensuring firewall rule for port 8000 exists..."
if ! gcloud compute firewall-rules describe allow-trader-web --project="${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud compute firewall-rules create allow-trader-web \
        --project="${PROJECT_ID}" \
        --allow=tcp:8000 \
        --target-tags=trader-node \
        --description="Allow traffic to Trading Dashboard and API"
fi

# 2. Startup Script for Docker & Docker Compose installation
STARTUP_SCRIPT=$(cat <<'EOF'
#!/bin/bash
set -e
apt-get update
apt-get install -y ca-certificates curl gnupg lsb-release git

# Install Docker
mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

systemctl enable docker
systemctl start docker
EOF
)

# 3. Create or verify Compute Engine VM
echo "[2/4] Provisioning GCE Instance: ${INSTANCE_NAME}..."
if ! gcloud compute instances describe "${INSTANCE_NAME}" --zone="${ZONE}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud compute instances create "${INSTANCE_NAME}" \
        --project="${PROJECT_ID}" \
        --zone="${ZONE}" \
        --machine-type="${MACHINE_TYPE}" \
        --image-family=debian-12 \
        --image-project=debian-cloud \
        --boot-disk-size=50GB \
        --tags=trader-node \
        --metadata=startup-script="${STARTUP_SCRIPT}"
    echo "Instance created. Waiting 30s for startup scripts..."
    sleep 30
else
    echo "Instance ${INSTANCE_NAME} already exists."
fi

# 4. Copy Code & Launch Docker Stack
echo "[3/4] Syncing project files to instance..."
gcloud compute scp --recurse \
    Dockerfile docker-compose.yml pyproject.toml apps core agents database execution guardian market monitoring portfolio risk scanner skills strategy tools .env \
    "${INSTANCE_NAME}:/home/\$USER/trader/" \
    --zone="${ZONE}" \
    --project="${PROJECT_ID}"

echo "[4/4] Starting Docker Compose stack on VM..."
gcloud compute ssh "${INSTANCE_NAME}" \
    --zone="${ZONE}" \
    --project="${PROJECT_ID}" \
    --command="cd ~/trader && sudo docker compose up -d --build"

EXTERNAL_IP=$(gcloud compute instances describe "${INSTANCE_NAME}" --zone="${ZONE}" --project="${PROJECT_ID}" --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo "=========================================================="
echo "DEPLOYMENT COMPLETE!"
echo "Dashboard & API URL: http://${EXTERNAL_IP}:8000"
echo "PostgreSQL running on VM container with volume persistence."
echo "=========================================================="

