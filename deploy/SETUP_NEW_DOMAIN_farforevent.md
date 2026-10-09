# Підключення нового домену `farforevent.com.ua` до VPS

> Діагноз з пода: `farforevent.com.ua` → **NXDOMAIN на Google DNS 8.8.8.8** (запис відсутній).
> Помилка в браузері `ERR_TUNNEL_CONNECTION_FAILED` означає що проксі/Cloudflare/VPN
> не може встановити upstream-тунель — бо domain нікуди не пов'язаний.

VPS IP (з робочого `farforrent.com.ua`): **185.68.16.68**
(У `server.py` також задокументовано публічний IP `173.242.49.48` — використайте той, що відповідає вашому поточному серверу. Перевіряємо через `dig +short farforrent.com.ua`.)

---

## КРОК 1. DNS-записи у реєстратора домену

Зайдіть у панель де ви придбали `farforevent.com.ua`. Знайдіть розділ **DNS / Manage DNS**.

Додайте записи:

| Type  | Name | Value                       | TTL  |
|-------|------|-----------------------------|------|
| `A`   | `@`  | `185.68.16.68`              | 600  |
| `A`   | `www`| `185.68.16.68`              | 600  |

Якщо є Cloudflare:
- Спершу зробіть proxy = **DNS only** (сіра хмарка) — щоб certbot пройшов validation.
- Після видачі сертифіката можна увімкнути Proxy = **Proxied** і вибрати SSL Mode = **Full (strict)**.

Зачекайте 5–30 хвилин на пропагацію. Перевірити можна тут:
```
https://dnschecker.org/#A/farforevent.com.ua
```
Має показати `185.68.16.68` принаймні у частині регіонів.

---

## КРОК 2. Nginx server_name на VPS

SSH у VPS:
```bash
ssh root@185.68.16.68
sudo nano /etc/nginx/sites-available/farforrent.conf   # або як у вас файл називається
```

Знайдіть існуючий блок `server { listen 443 ssl; server_name farforrent.com.ua ...; }` і додайте:
```nginx
# Новий event-домен
server {
    listen 80;
    listen [::]:80;
    server_name farforevent.com.ua www.farforevent.com.ua;

    # Тимчасово, щоб certbot пройшов
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
    location / {
        return 301 https://$host$request_uri;
    }
}
```

Перевірте та перевантажте:
```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## КРОК 3. HTTPS (Let's Encrypt) для нового домену

```bash
sudo certbot --nginx -d farforevent.com.ua -d www.farforevent.com.ua
```

Після успіху certbot **сам** додасть `listen 443 ssl;` блок з SSL-сертифікатом.

Перевірте `nginx -t` і відкрийте `https://farforevent.com.ua` — має відкритись Event Tool.

---

## КРОК 4. (опційно) Якщо хочете щоб новий домен ВІДКРИВАВ Event Tool, а старий — RentalHub Admin

У Nginx можна налаштувати різні `root` / `proxy_pass`:
```nginx
# farforevent.com.ua → Event Tool (Client App)
server {
    listen 443 ssl http2;
    server_name farforevent.com.ua www.farforevent.com.ua;

    ssl_certificate     /etc/letsencrypt/live/farforevent.com.ua/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/farforevent.com.ua/privkey.pem;

    root /var/www/farforrent/event-tool/build;   # підставте свій шлях
    index index.html;

    location /api/ {
        proxy_pass         http://127.0.0.1:8001;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }

    # WebSocket (для чату)
    location /api/ws/ {
        proxy_pass         http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host $host;
        proxy_read_timeout 86400;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

---

## КРОК 5. Оновити frontend env-и (якщо змінюєте домен)

У `event-tool-source/.env`:
```
REACT_APP_BACKEND_URL=https://farforevent.com.ua
```

Перебудувати:
```bash
cd /var/www/farforrent/event-tool-source
yarn build
```

Або просто `bash deploy/deploy.sh` як зазвичай.

---

## КРОК 6. CORS уже готовий ✅

У `/app/backend/server.py` я вже додав у `default_origins`:
- `https://farforevent.com.ua`
- `https://www.farforevent.com.ua`
- (плюс http-варіанти, якщо встигнете відкрити сайт ще до сертбота)

Тож одразу після DNS+Nginx бекенд прийматиме запити з нового домену **без додаткових змін у коді**.

---

## ШВИДКА ПЕРЕВІРКА (після кроків 1–3)

```bash
# З вашого комп'ютера або з VPS:
dig +short farforevent.com.ua            # має повернути 185.68.16.68
curl -I https://farforevent.com.ua/api/event/health   # має повернути 200
```

Якщо щось не так — пришліть скрін:
- DNS panel у реєстратора (запис A)
- `sudo nginx -t` вивід
- `sudo systemctl status nginx`
- `sudo certbot certificates`
