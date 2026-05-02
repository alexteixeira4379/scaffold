#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ "${1:-}" == "-h" ]] || [[ "${1:-}" == "--help" ]]; then
  echo "Uso: $0 [mensagem de commit]"
  echo "Bump de patch em pyproject.toml, uv lock, git add (exceto .codex), commit, tag e push."
  exit 0
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "Erro: uv não está no PATH."
  exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Erro: não é um repositório git."
  exit 1
fi

CURRENT="$(sed -n 's/^version[[:space:]]*=[[:space:]]*"\(.*\)".*/\1/p' pyproject.toml)"
if [[ -z "$CURRENT" ]] || [[ "$CURRENT" != *.*.* ]]; then
  echo "Erro: não foi possível ler version X.Y.Z em pyproject.toml."
  exit 1
fi

IFS=. read -r MA MI PA <<<"$CURRENT"
if ! [[ "$MA" =~ ^[0-9]+$ && "$MI" =~ ^[0-9]+$ && "$PA" =~ ^[0-9]+$ ]]; then
  echo "Erro: versão atual inválida: $CURRENT"
  exit 1
fi

NEW=$((10#$PA + 1))
NEW_VERSION="${MA}.${MI}.${NEW}"

if git rev-parse -q --verify "refs/tags/$NEW_VERSION" >/dev/null; then
  echo "Erro: a tag '$NEW_VERSION' já existe neste repo."
  exit 1
fi

sed -i "s/^version[[:space:]]*=[[:space:]]*\"[^\"]*\"/version = \"${NEW_VERSION}\"/" pyproject.toml
uv lock

git add --all -- . ":(exclude).codex"
if git diff --cached --quiet; then
  echo "Erro: nada foi preparado para o commit."
  git checkout HEAD -- pyproject.toml uv.lock
  exit 1
fi

MSG="${1:-Release ${NEW_VERSION}.}"
git commit -m "$MSG"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"

git tag -a "$NEW_VERSION" -m "$NEW_VERSION"
git push origin "$BRANCH"
git push origin "$NEW_VERSION"

echo "Feito: $CURRENT -> $NEW_VERSION (push $BRANCH + tag)"
