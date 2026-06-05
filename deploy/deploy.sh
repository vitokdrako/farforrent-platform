#!/bin/bash
# ============================================================
# ПОВНИЙ ДЕПЛОЙ на VPS
#
# Архітектура:
#   ┌────────────────────────────────────────┐
#   │ ОДИН backend (RentalHub) на :8001      │
#   │ ОДНА БД MySQL `farforrent`              │
#   └─────┬──────────────────────────┬───────┘
#         │ /api/*                   │ /api/*
#   ┌─────▼─────────────┐    ┌───────▼───────────┐
#   │ http://IP/        │    │ http://IP:8080/   │
#   │ Event Tool        │    │ RentalHub admin   │
#   │ (клієнти)         │    │ (менеджери)       │
#   └───────────────────┘    └───────────────────┘
# ============================================================
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "📂 Repo root: $REPO_ROOT"
echo ""

# ===== 1. Build Event Tool (клієнтський фронт) =====
echo "═══ [1/4] Білдимо Event Tool (клієнтський React) ═══"
bash "$REPO_ROOT/deploy/build_event_tool.sh"
echo ""

# ===== 2. Build RentalHub adminку =====
echo "═══ [2/4] Білдимо RentalHub адмінку ═══"
cd "$REPO_ROOT/frontend"
if [ ! -d node_modules ]; then
  yarn install --frozen-lockfile
fi
yarn build
sudo rm -rf /var/www/rentalhub-admin-build
sudo cp -r build /var/www/rentalhub-admin-build
sudo chown -R www-data:www-data /var/www/rentalhub-admin-build
echo "✅ RentalHub білд у /var/www/rentalhub-admin-build"
echo ""

# ===== 3. Nginx конфіги =====
echo "═══ [3/4] Налаштовуємо Nginx ═══"
sudo cp "$REPO_ROOT/deploy/nginx-event-tool.conf"    /etc/nginx/sites-available/event-tool
sudo cp "$REPO_ROOT/deploy/nginx-rentalhub.conf"     /etc/nginx/sites-available/rentalhub-admin

# Виправляємо шлях у nginx-rentalhub.conf на новий
sudo sed -i 's|/var/www/farforrent/frontend/build|/var/www/rentalhub-admin-build|g' /etc/nginx/sites-available/rentalhub-admin

sudo ln -sf /etc/nginx/sites-available/event-tool       /etc/nginx/sites-enabled/
sudo ln -sf /etc/nginx/sites-available/rentalhub-admin  /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo rm -f /etc/nginx/sites-enabled/farforrent
sudo nginx -t
sudo systemctl reload nginx
echo "✅ Nginx OK"
echo ""

# ===== 4. Backend RH (systemd) =====
echo "═══ [4/4] Перезапускаємо RH backend ═══"
sudo cp "$REPO_ROOT/deploy/rentalhub-backend.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable rentalhub-backend 2>/dev/null || true

# Знайти існуючий unit (raystatest або власна назва) — або просто наш
if sudo systemctl list-units --type=service --all | grep -q "rentalhub-backend"; then
  sudo systemctl restart rentalhub-backend || echo "⚠️ Backend не стартує — перевір логи"
else
  echo "ℹ️  Юніт rentalhub-backend ще не активний. Якщо у тебе власне ім'я — перезапусти його вручну."
fi
echo ""

# ===== Фінальна перевірка =====
echo "═══ Перевірка ═══"
sleep 2
echo "Event Tool   (http://localhost):"
curl -s -o /dev/null -w "  HTTP %{http_code}\n" http://127.0.0.1/ || echo "  ❌ нема відповіді"
echo "RentalHub    (http://localhost:8080):"
curl -s -o /dev/null -w "  HTTP %{http_code}\n" http://127.0.0.1:8080/ || echo "  ❌ нема відповіді"
echo "Backend API  (http://localhost:8001/docs):"
curl -s -o /dev/null -w "  HTTP %{http_code}\n" http://127.0.0.1:8001/docs || echo "  ❌ backend не запущено"

echo ""
echo "✅ ДЕПЛОЙ ЗАВЕРШЕНО!"
echo ""
echo "🌐 Адреси:"
echo "   Клієнти (Event Tool):   http://173.242.49.48"
echo "   Адмінка (RentalHub):    http://173.242.49.48:8080"
echo "   API docs:               http://173.242.49.48:8080/docs"
echo ""
echo "📋 Логи:"
echo "   sudo journalctl -u rentalhub-backend -f"
echo "   sudo tail -f /var/log/nginx/error.log"
