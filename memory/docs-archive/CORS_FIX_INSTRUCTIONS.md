# 🔧 ВИПРАВЛЕННЯ CORS ПОМИЛКИ

## Проблема
```
Access to fetch at 'https://backrentalhub.farforrent.com.ua/api/...' 
from origin 'https://rentalhub.farforrent.com.ua' 
has been blocked by CORS policy
```

## Рішення

Додайте наступний рядок в файл `.env` на вашому бекенд хостингу:

### Файл: `/home/farforre/farforrent.com.ua/backrentalhub/.env`

```bash
# Додайте цей рядок в кінець файлу:
CORS_ORIGINS=https://rentalhub.farforrent.com.ua,https://www.rentalhub.farforrent.com.ua
```

## Після додавання:

1. **Перезапустіть FastAPI сервер:**
   ```bash
   # Знайдіть процес FastAPI
   ps aux | grep uvicorn
   
   # Убийте процес (замініть PID на реальний)
   kill -9 <PID>
   
   # Або рестарт через systemd/supervisor (якщо використовується)
   sudo systemctl restart rentalhub-backend
   # або
   sudo supervisorctl restart rentalhub-backend
   ```

2. **Перевірте чи працює:**
   - Оновіть сторінку фронтенду
   - CORS помилка має зникнути

## Альтернатива (якщо перше не спрацювало)

Якщо у вас є nginx перед FastAPI, додайте CORS headers в nginx конфігурацію:

```nginx
location /api/ {
    # Додайте ці рядки:
    add_header 'Access-Control-Allow-Origin' 'https://rentalhub.farforrent.com.ua' always;
    add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, PATCH, DELETE, OPTIONS' always;
    add_header 'Access-Control-Allow-Headers' 'Content-Type, Authorization, X-Requested-With, Accept' always;
    add_header 'Access-Control-Allow-Credentials' 'true' always;
    
    if ($request_method = 'OPTIONS') {
        return 204;
    }
    
    # Ваш проксі до FastAPI
    proxy_pass http://localhost:8001;
}
```

Потім:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

## Перевірка

Відкрийте консоль браузера (F12) і спробуйте:
```javascript
fetch('https://backrentalhub.farforrent.com.ua/api/decor-orders/7045')
  .then(r => r.json())
  .then(d => console.log('✅ CORS працює!', d))
  .catch(e => console.log('❌ Помилка:', e))
```

Якщо бачите дані замовлення - CORS налаштовано правильно! ✅
