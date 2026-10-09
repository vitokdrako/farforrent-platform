# 🚀 ДЕПЛОЙ Event Tool (клієнтський фронт) + RentalHub (адмінка)

## Архітектура

```
http://173.242.49.48/                    → Event Tool (клієнти оформляють замовлення)
http://173.242.49.48/admin/              → RentalHub (адмінка, ваші менеджери)
http://173.242.49.48/api/...             → RentalHub backend (порт 8001)
http://173.242.49.48/event-api/api/...   → Event Tool backend (порт 8002)
http://173.242.49.48/uploads/...         → Картинки товарів (спільні)
```

Замовлення клієнтів з Event Tool автоматично потрапляють в спільну БД `farforrent`.

---

## Крок 1. Зібрати Event Tool на VPS

```bash
# 1. Перейти в репо Event Tool на VPS (якщо ще нема — клонуй)
cd /var/www/event-tool

# Якщо репо ще не клоновано:
# git clone <event-tool-repo-url> /var/www/event-tool

git pull

cd frontend

# 2. Створити .env для production
cat > .env <<'EOF'
REACT_APP_BACKEND_URL=/event-api
EOF

# 3. Встановити залежності і зібрати
yarn install
yarn build

# 4. Скопіювати build на місце де Nginx чекає
sudo rm -rf /var/www/event-tool-build
sudo cp -r build /var/www/event-tool-build
sudo chown -R www-data:www-data /var/www/event-tool-build
```

---

## Крок 2. Запустити Event Tool backend на порту 8002

```bash
# 1. Backend код
cd /var/www/event-tool/backend

# 2. venv + залежності
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. .env backend
cat > .env <<'EOF'
RH_DB_HOST=localhost
RH_DB_PORT=3306
RH_DB_USERNAME=farforrent_user
RH_DB_PASSWORD=ВАШ_ПАРОЛЬ_MYSQL
RH_DB_DATABASE=farforrent
JWT_SECRET_KEY=ваш_секретний_ключ_тут
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=30
CORS_ORIGINS=http://173.242.49.48
EOF

# 4. Systemd unit
sudo tee /etc/systemd/system/event-tool-backend.service > /dev/null <<'EOF'
[Unit]
Description=Event Tool Backend (FastAPI on :8002)
After=network.target mysql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/event-tool/backend
Environment="PATH=/var/www/event-tool/backend/venv/bin"
ExecStart=/var/www/event-tool/backend/venv/bin/uvicorn server:app --host 0.0.0.0 --port 8002
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable event-tool-backend
sudo systemctl start event-tool-backend
sudo systemctl status event-tool-backend
```

---

## Крок 3. Зібрати RentalHub адмінку (тільки якщо ще не білдили після останнього git pull)

```bash
cd /var/www/farforrent
git pull
cd frontend
yarn install
yarn build           # БЕЗ PUBLIC_URL — адмінка живе на /admin
```

> ⚠️ Якщо RH адмінка має проблему з шляхами під `/admin/...`, перебілди з `PUBLIC_URL=/admin yarn build`. Якщо без префіксу не працює — додайте `PUBLIC_URL=/admin`.

---

## Крок 4. Налаштувати Nginx

```bash
# Файл /app/nginx-rentalhub-unified.conf з репо містить готовий конфіг
sudo cp /var/www/farforrent/nginx-rentalhub-unified.conf /etc/nginx/sites-available/farforrent
sudo ln -sf /etc/nginx/sites-available/farforrent /etc/nginx/sites-enabled/

# Видалити дефолтний конфіг якщо є
sudo rm -f /etc/nginx/sites-enabled/default

# Перевірити синтаксис і перезавантажити
sudo nginx -t
sudo systemctl reload nginx
```

---

## Крок 5. Перевірка

```bash
# Має повернути HTML Event Tool
curl -I http://173.242.49.48/

# Має повернути HTML RentalHub
curl -I http://173.242.49.48/admin/

# RH API (порт 8001)
curl http://173.242.49.48/api/health || curl http://173.242.49.48/docs

# Event Tool API (порт 8002 через /event-api/)
curl http://173.242.49.48/event-api/api/health || \
  curl -X POST http://173.242.49.48/event-api/api/auth/login \
    -H 'Content-Type: application/json' \
    -d '{"email":"test@test.com","password":"test"}'
```

Відкрий браузер: `http://173.242.49.48/` → побачиш Event Tool каталог як на скріні. Клієнти оформлюють замовлення — воно йде в `farforrent` БД, ви бачите його в адмінці на `/admin/manager`.

---

## Перевірка логів якщо щось не працює

```bash
sudo journalctl -u event-tool-backend -f       # лог Event Tool backend
sudo journalctl -u rentalhub-backend -f        # лог RH backend (якщо такий unit є)
sudo tail -f /var/log/nginx/error.log          # лог Nginx
```
