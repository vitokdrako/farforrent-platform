# HTTP/2 tuning for farforevent.com.ua (VPS Nginx)

## Симптом
Після того як новий домен `farforevent.com.ua` запрацював, користувачі бачили помилки
у console DevTools при швидкому скролінгу/перемиканні сторінок каталогу:
```
GET /uploads/products/th_...png  net::ERR_HTTP2_SERVER_REFUSED_STREAM
```

## Корінь
Nginx 1.24 за замовчуванням обмежує `http2_max_concurrent_streams = 128`.
Каталог Event Tool віддає ~100 товарів за раз, кожен ⇒ thumbnail-запит.
Плюс favicons / static / api-запити — легко пробивається ліміт 128.
Браузер при відмові у stream отримує RST_STREAM з кодом `REFUSED_STREAM`,
запит часом не повторюється і картинка не вантажиться.

## Фікс (VPS Nginx)
Створили `/etc/nginx/conf.d/http2-tuning.conf`:
```nginx
http2_max_concurrent_streams 256;
keepalive_requests 1000;
keepalive_timeout  75s;
```

`sudo nginx -t && sudo systemctl reload nginx` — і помилки зникають.

## Чому не у коді
Це чисто транспортний рівень. Бекенд віддає запити нормально, frontend їх
генерує нормально — просто Nginx відмовляв їх паралельно проксити/обслуговувати.
Альтернатива — зменшити кількість одночасних thumbnails на UI (lazy-load з
IntersectionObserver), але це окрема ентерпрайз-задача.

## Майбутнє покращення
- Lazy-load зображень у `ProductCard` (тільки коли в'юпорті) — зменшить
  початкове навантаження вдвічі.
- Або переход на HTTP/3 (QUIC) — у нього multiplexing без stream-лімітів,
  потребує Nginx 1.25+ і `listen 443 quic reuseport;`.
