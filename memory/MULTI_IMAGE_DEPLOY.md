# Multi-Image Deployment Guide

## Що додано (28.05.2026)

### Backend
- ✅ `backend/routes/product_images_multi.py` — новий роутер
  - `GET  /api/products/{id}/images`
  - `POST /api/products/{id}/images` — multi-upload
  - `DELETE /api/product-images/{id}`
  - `PUT  /api/product-images/{id}/primary`
  - `PUT  /api/products/{id}/images/reorder`
- ✅ `backend/import_oc_multi_images.py` — імпорт з OpenCart (oc_product_image)
- ✅ Реєстрація роутера у `server.py`

### Frontend
- ✅ `frontend/src/components/ProductImageGallery.jsx` — drag&drop кількох фото
- ✅ Інтегровано у `CatalogBoard.jsx` (ProductDetailModal)
- ✅ Інтегровано у `ReauditCabinetFull.tsx` (нова вкладка "Фото")

### DB
Таблиця `product_images` (ВЖЕ СТВОРЕНА на VPS):
```sql
id, product_id, image_url, sort_order, is_primary, source, created_at
```

---

## 🚀 Деплой на VPS (one-liner)

```bash
cd /var/www/farforrent && \
git pull origin main && \
cd backend && source venv/bin/activate && pip install -r requirements.txt --quiet && \
cd /var/www/farforrent/frontend && yarn install --silent && \
DANGEROUSLY_DISABLE_HOST_CHECK=true yarn build && \
rm -rf /var/www/farforrent/frontend_build/* && \
cp -r build/* /var/www/farforrent/frontend_build/ && \
systemctl restart rentalhub-backend && \
systemctl reload nginx && \
echo "✅ Deploy complete!"
```

Триватиме ~3-5 хв (фронт-білд найдовше).

## 🖼️ Імпорт фото з OpenCart (одноразово, після деплою)

```bash
cd /var/www/farforrent/backend
source venv/bin/activate
python3 import_oc_multi_images.py
```

Триватиме залежно від кількості (типово 10-30 хв для кількох тисяч фото).

## ✅ Що перевірити після деплою

1. Заходимо на `http://173.242.49.48/`
2. Каталог → відкрити будь-який товар → побачимо нову галерею (з drag&drop)
3. Переоблік → відкрити товар → нова вкладка "Фото"
4. Завантажити кілька фото драгом — мають з'явитись з первинним позначенням ⭐
5. Видалити одне фото — primary має автоматично призначитись новому
