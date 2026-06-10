#!/bin/bash
# ============================================================
# ПОВНИЙ ДЕПЛОЙ на VPS — АРХІТЕКТУРА З ДВОМА ПОРТАМИ
#
#   ┌─────────────────────────────────────────────┐
#   │ ОДИН backend (RentalHub) на :8001           │
#   │ ОДНА БД MySQL `farforrent`                  │
#   └────────────────────┬────────────────────────┘
#                        │ /api/*
#       ┌────────────────┴────────────────┐
#       ▼                                 ▼
#   :80  Event Tool (клієнти)        :8080  RentalHub адмінка
# ============================================================
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "📂 Repo root: $REPO_ROOT"
echo ""

# ===== 0. Тягнемо ОСТАННІЙ код з GitHub (з force-reset, без залежності від upstream) =====
echo "═══ [0/4] Тягнемо останні зміни з GitHub ═══"
cd "$REPO_ROOT"

# Беремо реальний origin URL (на випадок різних remote-конфігів)
ORIGIN_URL=$(git config --get remote.origin.url || echo "")
if [ -z "$ORIGIN_URL" ]; then
  echo "❌ remote.origin не налаштовано. Виконай:"
  echo "   git remote add origin <github_url>"
  exit 1
fi
echo "🔗 origin: $ORIGIN_URL"

# Визначаємо основну вітку: main або master
BRANCH=$(git ls-remote --symref "$ORIGIN_URL" HEAD 2>/dev/null | head -1 | awk '{print $2}' | sed 's@refs/heads/@@')
BRANCH=${BRANCH:-main}
echo "🌿 Branch: $BRANCH"

OLD_HASH=$(git rev-parse --short HEAD 2>/dev/null || echo "none")
git fetch origin "$BRANCH" --depth=50 --quiet || git fetch origin --quiet
git reset --hard "origin/$BRANCH"
NEW_HASH=$(git rev-parse --short HEAD)
COMMIT_MSG=$(git log -1 --pretty=format:'%s' | head -c 80)

if [ "$OLD_HASH" = "$NEW_HASH" ]; then
  echo "ℹ️  Код вже актуальний: $NEW_HASH"
else
  echo "✅ Оновлено: $OLD_HASH → $NEW_HASH"
fi
echo "📝 Останній коміт: $NEW_HASH «$COMMIT_MSG»"
echo ""

# Передаємо хеш у білди як змінну (буде видно у фронті)
export REACT_APP_BUILD_HASH="$NEW_HASH"
export REACT_APP_BUILD_TIME="$(date -u +'%Y-%m-%d %H:%M UTC')"

# ===== 1. Build Event Tool (клієнтський фронт) =====
echo "═══ [1/4] Білдимо Event Tool (клієнтський React) ═══"
bash "$REPO_ROOT/deploy/build_event_tool.sh"
# Запис версії у файл щоб можна було перевірити через curl
echo "$NEW_HASH $REACT_APP_BUILD_TIME" | sudo tee /var/www/event-tool-build/version.txt > /dev/null
echo ""

# ===== 2. Build RentalHub adminку =====
echo "═══ [2/4] Білдимо RentalHub адмінку (на корені, без basename) ═══"
cd "$REPO_ROOT/frontend"
if [ ! -d node_modules ]; then
  yarn install --frozen-lockfile
fi
PUBLIC_URL='' REACT_APP_BACKEND_URL='' REACT_APP_BUILD_HASH="$NEW_HASH" REACT_APP_BUILD_TIME="$REACT_APP_BUILD_TIME" yarn build
sudo rm -rf /var/www/rentalhub-admin-build
sudo cp -r build /var/www/rentalhub-admin-build
sudo chown -R www-data:www-data /var/www/rentalhub-admin-build
echo "$NEW_HASH $REACT_APP_BUILD_TIME" | sudo tee /var/www/rentalhub-admin-build/version.txt > /dev/null
echo "✅ RentalHub білд у /var/www/rentalhub-admin-build"
echo ""

# ===== 3. Nginx конфіги =====
echo "═══ [3/4] Налаштовуємо Nginx (порти 80 + 8080) ═══"
# Очищаємо ВСІ старі симлінки щоб уникнути конфліктів default_server
sudo rm -f /etc/nginx/sites-enabled/default
sudo rm -f /etc/nginx/sites-enabled/farforrent
sudo rm -f /etc/nginx/sites-enabled/event-tool
sudo rm -f /etc/nginx/sites-enabled/rentalhub-admin
sudo rm -f /etc/nginx/sites-enabled/rentalhub

sudo cp "$REPO_ROOT/deploy/nginx-event-tool.conf"  /etc/nginx/sites-available/event-tool
sudo cp "$REPO_ROOT/deploy/nginx-rentalhub.conf"   /etc/nginx/sites-available/rentalhub-admin

sudo ln -sf /etc/nginx/sites-available/event-tool       /etc/nginx/sites-enabled/
sudo ln -sf /etc/nginx/sites-available/rentalhub-admin  /etc/nginx/sites-enabled/

sudo nginx -t
sudo systemctl reload nginx
echo "✅ Nginx OK"
echo ""

# ===== 4. Backend RH (systemd) =====
echo "═══ [4/4] Перезапускаємо RH backend ═══"

# Встановлюємо/оновлюємо Python deps у venv
if [ -d /var/www/farforrent/backend/venv ]; then
  echo "📦 Оновлюємо Python залежності у venv..."
  /var/www/farforrent/backend/venv/bin/pip install -q --upgrade pip
  /var/www/farforrent/backend/venv/bin/pip install -q -r "$REPO_ROOT/backend/requirements.txt" \
    || echo "⚠️ Не вдалося встановити частину залежностей — перевір requirements.txt"
else
  echo "⚠️ venv не знайдено в /var/www/farforrent/backend/venv. Створи його:"
  echo "   python3 -m venv /var/www/farforrent/backend/venv"
  echo "   /var/www/farforrent/backend/venv/bin/pip install -r $REPO_ROOT/backend/requirements.txt"
fi

sudo cp "$REPO_ROOT/deploy/rentalhub-backend.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable rentalhub-backend 2>/dev/null || true

if sudo systemctl list-units --type=service --all | grep -q "rentalhub-backend"; then
  sudo systemctl restart rentalhub-backend || echo "⚠️ Backend не стартує — перевір логи нижче"
else
  echo "ℹ️  Юніт rentalhub-backend ще не активний."
fi
echo ""

# ===== Перевірка =====
echo "═══ Перевірка ═══"
sleep 3
echo "Event Tool   (http://localhost/):"
curl -s -o /dev/null -w "  HTTP %{http_code}\n" http://127.0.0.1/
echo "RentalHub    (http://localhost:8080/):"
curl -s -o /dev/null -w "  HTTP %{http_code}\n" http://127.0.0.1:8080/
echo "Backend API  (http://localhost:8001/docs):"
BACKEND_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8001/docs)
echo "  HTTP $BACKEND_CODE"
if [ "$BACKEND_CODE" = "000" ] || [ "$BACKEND_CODE" = "502" ]; then
  echo "  ❌ Backend не відповідає — діагностика:"
  echo "  ────────── Останні 30 рядків логу: ──────────"
  sudo tail -n 30 /var/log/rentalhub-backend.log 2>/dev/null | sed 's/^/    /'
  echo "  ─────────────────────────────────────────────"
  echo "  ▶ Повний лог: sudo journalctl -u rentalhub-backend -n 100 --no-pager"
fi

# Перевірка чи відкритий порт 8080
echo ""
echo "🔥 Порт 8080 у файрволі:"
if command -v ufw >/dev/null 2>&1; then
  sudo ufw status 2>/dev/null | grep -E "8080|Status" || echo "  (ufw неактивний)"
fi

echo ""
echo "✅ ДЕПЛОЙ ЗАВЕРШЕНО!"
echo ""
echo "🌐 Адреси:"
echo "   Клієнти (Event Tool):   http://173.242.49.48/"
echo "   Адмінка (RentalHub):    http://173.242.49.48:8080/"
echo "   API docs:               http://173.242.49.48:8080/docs"
echo ""
echo "📋 Якщо адмінка на :8080 не відкривається з браузера —"
echo "   перевір що порт 8080 відкритий у файрволі провайдера:"
echo "   sudo ufw allow 8080"
