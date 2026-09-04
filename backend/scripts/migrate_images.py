#!/usr/bin/env python3
"""
Скрипт для міграції зображень з farforrent.com.ua в локальну папку
"""
import os
import sys
import pymysql
import requests
from pathlib import Path
from urllib.parse import urlparse
import time

# Додати backend в path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402  (після налаштування sys.path)

load_dotenv(BACKEND_DIR / ".env")

from core.security import get_required_env  # noqa: E402

# Конфігурація — усе з environment, жодних credentials у коді.
_ENV_HINT = "Див. backend/.env.example."

EXTERNAL_DOMAIN = os.environ.get(
    "IMAGE_SOURCE_BASE_URL", "https://farforrent.com.ua/image/"
)
LOCAL_IMAGE_DIR = os.environ.get(
    "LOCAL_IMAGE_DIR", str(BACKEND_DIR / "static" / "images" / "products")
)
DB_HOST = get_required_env("RH_DB_HOST", hint=_ENV_HINT)
DB_USER = get_required_env("RH_DB_USERNAME", hint=_ENV_HINT)
DB_PASSWORD = get_required_env("RH_DB_PASSWORD", hint=_ENV_HINT)
DB_NAME = get_required_env("RH_DB_DATABASE", hint=_ENV_HINT)

def connect_db():
    """Підключення до бази даних"""
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset='utf8mb4'
    )

def download_image(url, local_path):
    """Завантажити зображення з URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, timeout=30, stream=True, headers=headers)
        if response.status_code == 200:
            # Створити папки якщо не існують
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # Зберегти файл
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        else:
            print(f"  ⚠️  HTTP {response.status_code}: {url}")
            return False
    except Exception as e:
        print(f"  ❌ Помилка: {e}")
        return False

def migrate_images(dry_run=False, limit=None):
    """Мігрувати всі зображення з products"""
    conn = connect_db()
    cursor = conn.cursor()
    
    # Отримати всі товари з зображеннями
    query = """
        SELECT product_id, sku, name, image_url 
        FROM products 
        WHERE image_url IS NOT NULL AND image_url != ''
    """
    if limit:
        query += f" LIMIT {limit}"
    
    cursor.execute(query)
    products = cursor.fetchall()
    
    print(f"\n📊 Знайдено товарів з зображеннями: {len(products)}")
    
    if dry_run:
        print("🔍 DRY RUN MODE - файли не будуть завантажені")
    
    stats = {
        'total': len(products),
        'downloaded': 0,
        'skipped': 0,
        'failed': 0,
        'updated': 0
    }
    
    for product_id, sku, name, image_url in products:
        if not image_url:
            continue
            
        # Пропустити якщо вже локальний шлях
        if image_url.startswith('static/') or image_url.startswith('/static/'):
            stats['skipped'] += 1
            continue
        
        # Побудувати URL та локальний шлях
        if image_url.startswith('http'):
            full_url = image_url
        else:
            full_url = f"{EXTERNAL_DOMAIN}{image_url}"
        
        # Локальний шлях: зберігаємо структуру папок
        # catalog/products/Skatertyny/file.jpg -> products/Skatertyny/file.jpg
        relative_path = image_url.replace('catalog/products/', '').replace('catalog/', '')
        local_file_path = os.path.join(LOCAL_IMAGE_DIR, relative_path)
        
        # Новий шлях для бази даних
        db_path = f"static/images/products/{relative_path}"
        
        print(f"\n[{stats['downloaded']+stats['failed']+1}/{stats['total']}] {sku} - {name[:40]}")
        print(f"  📥 URL: {full_url}")
        print(f"  💾 Local: {local_file_path}")
        
        # Перевірити чи файл вже існує
        if os.path.exists(local_file_path):
            print(f"  ✅ Файл вже існує, пропускаємо")
            stats['skipped'] += 1
            
            # Оновити БД якщо потрібно
            if not dry_run and image_url != db_path:
                cursor.execute(
                    "UPDATE products SET image_url = %s WHERE product_id = %s",
                    (db_path, product_id)
                )
                stats['updated'] += 1
            continue
        
        if not dry_run:
            # Завантажити файл
            if download_image(full_url, local_file_path):
                print(f"  ✅ Завантажено")
                stats['downloaded'] += 1
                
                # Оновити шлях в базі даних
                cursor.execute(
                    "UPDATE products SET image_url = %s WHERE product_id = %s",
                    (db_path, product_id)
                )
                stats['updated'] += 1
                conn.commit()
            else:
                print(f"  ❌ Не вдалося завантажити")
                stats['failed'] += 1
        else:
            stats['downloaded'] += 1
        
        # Невелика пауза щоб не перевантажити сервер
        time.sleep(0.1)
    
    cursor.close()
    conn.close()
    
    # Підсумок
    print("\n" + "="*60)
    print("📊 ПІДСУМОК МІГРАЦІЇ")
    print("="*60)
    print(f"Всього товарів:        {stats['total']}")
    print(f"✅ Завантажено:        {stats['downloaded']}")
    print(f"⏭️  Пропущено:         {stats['skipped']}")
    print(f"❌ Помилки:            {stats['failed']}")
    print(f"🔄 Оновлено в БД:      {stats['updated']}")
    print("="*60)
    
    return stats

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Міграція зображень товарів')
    parser.add_argument('--dry-run', action='store_true', help='Тестовий режим без завантаження')
    parser.add_argument('--limit', type=int, help='Обмеження кількості товарів')
    
    args = parser.parse_args()
    
    print("🚀 Початок міграції зображень...")
    print(f"📁 Локальна папка: {LOCAL_IMAGE_DIR}")
    print(f"🌐 Зовнішній домен: {EXTERNAL_DOMAIN}")
    
    stats = migrate_images(dry_run=args.dry_run, limit=args.limit)
    
    if not args.dry_run and stats['downloaded'] > 0:
        print("\n✅ Міграція завершена успішно!")
        print("💡 Не забудьте перезапустити backend для застосування змін")
    elif args.dry_run:
        print("\n🔍 DRY RUN завершено. Запустіть без --dry-run для реальної міграції")
