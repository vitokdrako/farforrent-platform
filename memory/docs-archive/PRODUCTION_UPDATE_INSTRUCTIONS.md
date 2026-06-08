# 🚀 ІНСТРУКЦІЯ ПО ОНОВЛЕННЮ ПРОДАКШН ВЕРСІЇ

## Проблеми які були виправлені:

### 1. ❌ CORS помилка
**Помилка:** `Access-Control-Allow-Origin header is not present`
**Виправлення:** Додано CORS налаштування

### 2. ❌ 500 Error при відкритті замовлення
**Помилка:** `AttributeError: 'int' object has no attribute 'isoformat'`
**Виправлення:** Виправлено парсинг замовлень з новою схемою БД

### 3. ✅ Синхронізація замовлень працює
10 нових замовлень успішно синхронізовано з OpenCart!

---

## 📦 Файли які потрібно оновити на хостингу:

### 1. Backend файли:

**`/home/farforre/farforrent.com.ua/rentalhub/backend/.env`**
Додайте в кінець файлу:
```bash
CORS_ORIGINS=https://rentalhub.farforrent.com.ua,https://www.rentalhub.farforrent.com.ua
```

**`/home/farforre/farforrent.com.ua/rentalhub/backend/routes/orders.py`**
Замініть цей файл на оновлену версію з `/app/backend/routes/orders.py`

**`/home/farforre/farforrent.com.ua/backrentalhub/sync_all.py`**
Замініть на оновлену версію з `/app/backend/sync_all_production.py`

### 2. Frontend build:

**`/home/farforre/farforrent.com.ua/rentalhub/frontend/build/`**
Замініть всю папку build на нову версію з `/app/frontend/build/`

---

## 🔧 Команди для оновлення:

### Варіант 1: Через FTP/File Manager
1. Завантажте файли через панель хостингу
2. Замініть старі файли на нові
3. Перезапустіть FastAPI сервер

### Варіант 2: Через SSH (якщо є доступ)

```bash
# 1. Зайдіть на сервер
ssh farforre@farforrent.com.ua

# 2. Зробіть backup
cd /home/farforre/farforrent.com.ua/rentalhub
cp -r backend/routes/orders.py backend/routes/orders.py.backup
cp backend/.env backend/.env.backup

# 3. Додайте CORS в .env
echo "CORS_ORIGINS=https://rentalhub.farforrent.com.ua,https://www.rentalhub.farforrent.com.ua" >> backend/.env

# 4. Оновіть orders.py (завантажте новий файл через FTP перед цим)
# або скопіюйте вміст з /app/backend/routes/orders.py

# 5. Оновіть sync скрипт
cp /шлях/до/нового/sync_all_production.py backrentalhub/sync_all.py

# 6. Перезапустіть FastAPI
ps aux | grep uvicorn
kill -9 <PID>
# або
sudo supervisorctl restart rentalhub-backend
```

### 3. Перезапуск сервісів:

```bash
# Перезапустити FastAPI backend
sudo supervisorctl restart rentalhub-backend

# Або якщо через systemd:
sudo systemctl restart rentalhub-backend

# Перевірити статус
sudo supervisorctl status
```

---

## ✅ Перевірка після оновлення:

### 1. Перевірте CORS:
Відкрийте браузер → F12 → Console:
```javascript
fetch('https://backrentalhub.farforrent.com.ua/api/decor-orders/7045')
  .then(r => r.json())
  .then(d => console.log('✅ CORS працює!', d))
  .catch(e => console.log('❌ Помилка:', e))
```

### 2. Перевірте замовлення:
- Зайдіть на https://rentalhub.farforrent.com.ua
- Відкрийте будь-яке замовлення
- Якщо воно завантажується без помилок → ✅ Працює!

### 3. Перевірте синхронізацію:
Подивіться логи cron:
```bash
tail -f /home/farforre/sync.log
```

Має бути:
```
✅ Synced 154 categories
✅ Updated 3792 products
✅ Successfully synced X new orders
```

---

## 🆘 Якщо щось не працює:

### CORS все ще не працює?
1. Перевірте чи .env файл оновлено: `cat backend/.env | grep CORS`
2. Перевірте чи FastAPI перезапущено: `ps aux | grep uvicorn`
3. Подивіться логи: `tail -f /var/log/rentalhub/error.log`

### Замовлення не відкриваються?
1. Перевірте чи orders.py оновлено
2. Подивіться логи FastAPI
3. Перезапустіть сервер ще раз

### Синхронізація не працює?
1. Перевірте чи sync_all.py оновлено
2. Запустіть вручну: `python3.11 backrentalhub/sync_all.py`
3. Подивіться на помилки в output

---

## 📞 Підтримка

Якщо виникли проблеми, збережіть:
1. Логи FastAPI: `/var/log/rentalhub/*.log`
2. Output cron: `/home/farforre/sync.log`
3. Browser console errors (F12)

І надішліть для діагностики.
