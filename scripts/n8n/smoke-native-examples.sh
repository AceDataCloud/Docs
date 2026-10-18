#!/usr/bin/env bash
set -euo pipefail
: "${SERVICE:?set SERVICE to one of the five guide services}"
: "${PACKAGE_VERSION:?set the exact published package version}"
case "$SERVICE:$PACKAGE_VERSION" in
  suno:0.1.2|seedance:0.1.2|happyhorse:0.1.1|gpt-image:0.1.1|nano-banana:0.1.1) ;;
  *) echo 'Unsupported guide service/version pair' >&2; exit 2 ;;
esac
mkdir -p artifacts
docker run --rm \
  -v "$PWD/examples/n8n/read-$SERVICE-task.json:/guide/workflow.json:ro" \
  -e SERVICE -e PACKAGE_VERSION \
  -e N8N_DIAGNOSTICS_ENABLED=false \
  -e N8N_VERSION_NOTIFICATIONS_ENABLED=false \
  -e N8N_TEMPLATES_ENABLED=false \
  --entrypoint sh "${N8N_IMAGE:-n8nio/n8n:2.43.7}" -ec '
    mkdir -p /home/node/.n8n/nodes
    npm install --prefix /home/node/.n8n/nodes --registry=https://registry.npmjs.org \
      --ignore-scripts --legacy-peer-deps --no-audit --no-fund \
      "@acedatacloud/n8n-nodes-$SERVICE@$PACKAGE_VERSION"
    npm ls --prefix /home/node/.n8n/nodes --depth=0
    export NODE_PATH=/usr/local/lib/node_modules/n8n/node_modules
    export N8N_USER_FOLDER=/home/node
    workflow_id="$(node -p "require(\"/guide/workflow.json\").id")"
    n8n --version
    n8n import:workflow --input=/guide/workflow.json
    if n8n execute --id="$workflow_id" >/tmp/execute.log 2>&1; then
      cat /tmp/execute.log >&2
      echo "Expected the placeholder task reader to stop before any API request" >&2
      exit 1
    fi
    cat /tmp/execute.log
    if grep -Eiq "unrecognized node|unknown node|cannot find module|error loading|failed to load" /tmp/execute.log; then
      exit 1
    fi
    grep -Eiq "credential.*(not set|not found|missing|not configured|not available|required)|no credential|does not have any credentials" /tmp/execute.log
    echo "PASS: published package and guide JSON installed/imported in real n8n; no credential/API call"
  ' >"artifacts/n8n-$SERVICE.log" 2>&1 && status=0 || status=$?
cat "artifacts/n8n-$SERVICE.log"
exit "$status"
