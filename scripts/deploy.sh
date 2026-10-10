#!/usr/bin/env bash
# Despliega ScreenPilot en Cloud Run (proyecto mvps-london). Uso: scripts/deploy.sh
# Los flags están explicados en docs/system-architecture.md §8.
set -euo pipefail
cd "$(dirname "$0")/.."
gcloud run deploy screenpilot --project mvps-london --source . --region us-east1 \
  --no-cpu-throttling --min-instances 1 --max-instances 1 --cpu 2 --memory 2Gi --timeout 300 \
  --allow-unauthenticated \
  --set-secrets TEAM_TOKEN=TEAM_TOKEN:latest,OPENROUTER_API_KEY=OPENROUTER_API_KEY:latest \
  --quiet
curl -sf https://screenpilot-934756554303.us-east1.run.app/health && echo " ← health ok"
