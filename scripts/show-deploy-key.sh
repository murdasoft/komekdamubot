#!/usr/bin/env bash
# Показать публичный ключ для GitHub → Settings → Deploy keys
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PUB="$ROOT/deploy_key.pub"
if [[ ! -f "$PUB" ]]; then
  echo "Файл deploy_key.pub не найден."
  exit 1
fi
echo "Добавьте этот ключ в GitHub:"
echo "https://github.com/murdasoft/komekdamubot/settings/keys"
echo ""
echo "Title: komek-damu-bot-deploy"
echo "Allow write access: включить (для git push)"
echo ""
cat "$PUB"
