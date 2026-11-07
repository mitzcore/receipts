#!/usr/bin/env bash
# Switch Gateway helpers for the local Console-managed server.
#   ./switch-api.sh login
#   ./switch-api.sh agent-instructions <clerk|auditor> <file.md>   # sets the agent's "Agent instructions"
#   ./switch-api.sh room-instructions <room-name> <file.md>        # sets the room's instructions
#   ./switch-api.sh rooms | agents
#   ./switch-api.sh create-rooms switch/rooms.yaml                 # rooms, links, members from YAML
# Defaults target the server Switch Console runs on this computer; override with
# SWITCH_API and SWITCH_CORE_ENV (a file with GATEWAY_ADMIN_EMAIL / GATEWAY_ADMIN_PASSWORD).
set -euo pipefail
API="${SWITCH_API:-$(jq -r '"http://localhost:\(.api)"' "$HOME/Library/Application Support/switchdash/local-switch-server/ports.json" 2>/dev/null || echo http://localhost:8000)}"
JAR="${TMPDIR:-/tmp}/receipts-gw.jar"
ENV="${SWITCH_CORE_ENV:-$HOME/Library/Application Support/switchdash/local-switch-server/native/run/switch-core.env}"
login() {
  local e p; e=$(grep '^GATEWAY_ADMIN_EMAIL=' "$ENV" | cut -d= -f2-); p=$(grep '^GATEWAY_ADMIN_PASSWORD=' "$ENV" | cut -d= -f2-)
  curl -fsS -m 10 -c "$JAR" -H 'Content-Type: application/json' -d "$(jq -n --arg e "$e" --arg p "$p" '{email:$e,password:$p}')" $API/gateway/auth/login | jq -c '{logged_in_as: .email}'
}
agent_id() { curl -fsS -m 10 -b "$JAR" $API/gateway/agents | jq -r --arg n "$1" '(.[]? // .agents[]?) | select(.name==$n) | .id'; }
room_id() { curl -fsS -m 10 -b "$JAR" $API/gateway/rooms | jq -r --arg n "$1" '(.[]? // .rooms[]?) | select(.name==$n) | .id'; }
case "${1:-}" in
  login) login ;;
  agents) login >/dev/null; curl -fsS -m 10 -b "$JAR" $API/gateway/agents | jq -r '(.[]? // .agents[]?) | "\(.name)\t\(.id)"' ;;
  rooms) login >/dev/null; curl -fsS -m 10 -b "$JAR" $API/gateway/rooms | jq -r '(.[]? // .rooms[]?) | "\(.name)\t\(.id)"' ;;
  agent-instructions)
    login >/dev/null; id=$(agent_id "$2"); [ -n "$id" ] || { echo "no agent $2"; exit 1; }
    def=$(curl -fsS -m 10 -b "$JAR" $API/gateway/management/agents/$id | jq -c --rawfile ins "$3" '.definition | .instructions=$ins')
    curl -fsS -m 30 -b "$JAR" -X PATCH -H 'Content-Type: application/json' -d "$(jq -n --argjson d "$def" '{definition:$d}')" $API/gateway/management/agents/$id | jq -c '{name, revision, chars: (.definition.instructions|length)}' ;;
  room-instructions)
    login >/dev/null; id=$(room_id "$2"); [ -n "$id" ] || { echo "no room $2"; exit 1; }
    curl -fsS -m 30 -b "$JAR" -X PATCH -H 'Content-Type: application/json' -d "$(jq -n --rawfile ins "$3" '{instructions:$ins}')" $API/gateway/rooms/$id | jq -c '{name, chars: (.instructions|length)}' ;;
  create-rooms)
    login >/dev/null
    curl -fsS -m 60 -b "$JAR" -X POST -H 'Content-Type: text/yaml' --data-binary @"$2" $API/gateway/rooms/from-yaml | jq -c '.' ;;
  *) sed -n 2,10p "$0" ;;
esac
