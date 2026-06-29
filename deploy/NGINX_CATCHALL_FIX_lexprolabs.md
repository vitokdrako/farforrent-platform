# Catch-all block для невідомих хостів на VPS

## Симптом
Користувач знайшов сайт **`http://lexprolabs.com`** і він відкриває **наш Event Tool** з повним контентом FarforDecorOrenda.

## Корінь
1. У DNS `lexprolabs.com` стоїть A-запис `→ 173.242.49.48` (наш VPS).
2. У Nginx (`/etc/nginx/sites-available/event-tool`) перший блок має `listen 80 default_server; server_name _;` — це **catch-all** для всіх невідомих host headers.
3. Тому Nginx бачить `Host: lexprolabs.com` → шукає server_name match → не знаходить → потрапляє у default → віддає Event Tool.

Це не злам — просто чужий домен резолвиться на наш IP, і default_server-block не фільтрує.

## Виправлення
Створюємо НОВИЙ `default_server` блок який **відмовляє** на all невідомих хости (444), і прибираємо `default_server` зі старого event-tool блоку.

```bash
sudo tee /etc/nginx/conf.d/00-catch-all-block.conf > /dev/null << 'NGINX_EOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    return 444;
}
server {
    listen 443 ssl default_server;
    listen [::]:443 ssl default_server;
    server_name _;
    ssl_certificate     /etc/letsencrypt/live/farforevent.com.ua/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/farforevent.com.ua/privkey.pem;
    return 444;
}
NGINX_EOF

# Прибрати default_server з існуючого event-tool блоку
sudo sed -i 's/listen 80 default_server;/listen 80;/' /etc/nginx/sites-available/event-tool

sudo nginx -t && sudo systemctl reload nginx
```

## Перевірка
```bash
curl -sI -H "Host: lexprolabs.com" http://173.242.49.48     # очікую: connection closed / empty
curl -sI http://farforevent.com.ua                          # очікую: 301 → 443
curl -sI https://farforevent.com.ua                         # очікую: 200
curl -sI https://farforevent.com.ua/admin/                  # очікую: 200
```

## Подальші кроки
- 🟢 Browser cache + Google: за 1-2 тижні Google викине `lexprolabs.com` з індексу (бо 444).
- 🟡 (опційно) `whois lexprolabs.com` щоб зрозуміти хто власник — можна написати їм виправити DNS.
- 🟡 Розгляньте налаштування HSTS і `Strict-Transport-Security` на головних доменах farforevent — це не пов'язано з lexprolabs, але корисно як hardening.
