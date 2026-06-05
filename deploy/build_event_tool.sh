#!/bin/bash
# ============================================================
# Білд Event Tool React фронту на VPS
# Виконує yarn install (якщо треба) + yarn build, кладе в /var/www/event-tool-build
# ============================================================
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO_ROOT/event-tool-source"
TARGET=/var/www/event-tool-build

if [ ! -d "$SRC" ]; then
  echo "❌ Не знайдено $SRC — натисни Save to GitHub і git pull"
  exit 1
fi

echo "📦 Source: $SRC"
echo "📦 Target: $TARGET"

cd "$SRC"

# .env — same origin, ходить на /api свого ж домену
cat > .env <<'EOF'
REACT_APP_BACKEND_URL=
EOF

# Залежності
if [ ! -d node_modules ]; then
  echo "📥 yarn install..."
  yarn install --frozen-lockfile
fi

# Білд
echo "🛠️  yarn build..."
yarn build

# Викладаємо
sudo rm -rf "$TARGET"
sudo cp -r build "$TARGET"
sudo chown -R www-data:www-data "$TARGET"

echo ""
echo "✅ Event Tool білд готовий у $TARGET"
echo "   Перевір: curl -I http://127.0.0.1/ (через Nginx)"
