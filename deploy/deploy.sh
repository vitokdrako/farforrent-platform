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
# Очищаємо PUBLIC_URL щоб білд був на корені (порт :8080)
unset PUBLIC_URL
PUBLIC_URL='' yarn build
sudo rm -rf /var/www/rentalhub-admin-build
sudo cp -r build /var/www/rentalhub-admin-build
sudo chown -R www-data:www-data /var/www/rentalhub-admin-build
echo "✅ RentalHub білд у /var/www/rentalhub-admin-build"
echo ""

# ===== 3. Nginx конфіги =====
echo "═══ [3/4] Налаштовуємо Nginx ═══"
# Очищаємо ВСІ старі симлінки щоб уникнути конфліктів default_server
sudo rm -f /etc/nginx/sites-enabled/default
sudo rm -f /etc/nginx/sites-enabled/farforrent
sudo rm -f /etc/nginx/sites-enabled/event-tool
sudo rm -f /etc/nginx/sites-enabled/rentalhub-admin
sudo rm -f /etc/nginx/sites-enabled/rentalhub

sudo cp "$REPO_ROOT/deploy/nginx-event-tool.conf"    /etc/nginx/sites-available/event-tool
sudo cp "$REPO_ROOT/deploy/nginx-rentalhub.conf"     /etc/nginx/sites-available/rentalhub-admin

sudo ln -sf /etc/nginx/sites-available/event-tool       /etc/nginx/sites-enabled/
sudo ln -sf /etc/nginx/sites-available/rentalhub-admin  /etc/nginx/sites-enabled/

sudo nginx -t
sudo systemctl reload nginx
echo "✅ Nginx OK"
echo ""

# ===== 4. Backend RH (systemd) =====
echo "═══ [4/4] Перезапускаємо RH backend ═══"

# Встановлюємо/оновлюємо Python deps у venv (на випадок нових пакетів)
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

# Знайти існуючий unit (raystatest або власна назва) — або просто наш
if sudo systemctl list-units --type=service --all | grep -q "rentalhub-backend"; then
  sudo systemctl restart rentalhub-backend || echo "⚠️ Backend не стартує — перевір логи"
else
  echo "ℹ️  Юніт rentalhub-backend ще не активний. Якщо у тебе власне ім'я — перезапусти його вручну."
fi
echo ""

# ===== Фінальна перевірка =====
echo "═══ Перевірка ═══"
sleep 3
echo "Event Tool   (http://localhost):"
curl -s -o /dev/null -w "  HTTP %{http_code}\n" http://127.0.0.1/ || echo "  ❌ нема відповіді"
echo "RentalHub    (http://localhost:8080):"
curl -s -o /dev/null -w "  HTTP %{http_code}\n" http://127.0.0.1:8080/ || echo "  ❌ нема відповіді"
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
