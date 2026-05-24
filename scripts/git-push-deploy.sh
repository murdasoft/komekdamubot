#!/usr/bin/env bash
# Push to GitHub using deploy key (read/write).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KEY="$ROOT/deploy_key"
if [[ ! -f "$KEY" ]]; then
  echo "Нет файла deploy_key. Сначала: ssh-keygen -t ed25519 -f deploy_key -N \"\" -C \"murdasoft@gmail.com-komek-damu-bot-deploy\""
  exit 1
fi
chmod 600 "$KEY"
export GIT_SSH_COMMAND="ssh -F /dev/null -i $KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
cd "$ROOT"
git push git@github.com:murdasoft/komekdamubot.git "${1:-main}"
