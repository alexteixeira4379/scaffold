#!/usr/bin/env bash

USER="$1"
PASSWORD="$2"
BASE_URL="${3:-https://rabbitmq-web-ui-production-089d.up.railway.app}"

if [ -z "$USER" ] || [ -z "$PASSWORD" ]; then
  echo "Uso: ./list_queues.sh <user> <password> [base_url]"
  echo "Exemplo: ./list_queues.sh useralex mypassword"
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "Erro: jq não está instalado."
  echo "Ubuntu/Debian: sudo apt-get install jq -y"
  echo "Mac: brew install jq"
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Erro: python3 não está instalado."
  exit 1
fi

urlencode() {
  python3 -c "import urllib.parse, sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "$1"
}

VHOSTS_RESPONSE=$(curl -s -u "${USER}:${PASSWORD}" "${BASE_URL}/api/vhosts")

if ! echo "$VHOSTS_RESPONSE" | jq -e 'type == "array"' >/dev/null 2>&1; then
  echo "Erro ao consultar vhosts."
  echo "$VHOSTS_RESPONSE"
  exit 1
fi

{
  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
    "VHOST" "QUEUE" "READY" "UNACKED" "TOTAL" "CONSUMERS" "STATE"

  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
    "-----" "-----" "-----" "-------" "-----" "---------" "-----"

  echo "$VHOSTS_RESPONSE" | jq -r '.[].name' | while read -r VHOST; do
    ENCODED_VHOST=$(urlencode "$VHOST")

    QUEUES_RESPONSE=$(curl -s -u "${USER}:${PASSWORD}" \
      "${BASE_URL}/api/queues/${ENCODED_VHOST}?disable_stats=true&enable_queue_totals=true")

    if ! echo "$QUEUES_RESPONSE" | jq -e 'type == "array"' >/dev/null 2>&1; then
      continue
    fi

    echo "$QUEUES_RESPONSE" | jq -r --arg vhost "$VHOST" '
      .[] |
      [
        $vhost,
        .name,
        (.messages_ready // 0),
        (.messages_unacknowledged // 0),
        (.messages // 0),
        (.consumers // 0),
        (.state // "-")
      ] | @tsv
    '
  done
} | column -t -s $'\t'
