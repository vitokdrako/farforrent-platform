#!/usr/bin/env python3
"""
Скрипт для оновлення полів price та ean в OpenCart БД з Excel файлів
"""
import os
import sys
import pandas as pd
import pymysql
from dotenv import load_dotenv

# Завантажуємо .env
load_dotenv('/app/backend/.env')

# Конфігурація БД
DB_CONFIG = {
    'host': os.getenv('OC_DB_HOST'),
    'port': int(os.getenv('OC_DB_PORT', 3306)),
    'user': os.getenv('OC_DB_USERNAME'),
    'password': os.getenv('OC_DB_PASSWORD'),
    'database': os.getenv('OC_DB_DATABASE'),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

PREFIX = os.getenv('OC_DB_PREFIX', 'oc_')

# Файли для обробки
EXCEL_FILES = [
    '/app/backend/посуд.xlsx',
    '/app/backend/етажерки.xlsx',
    '/app/backend/стільці.xlsx'
]


def read_excel_data(filepath):
    """
    Читає Excel файл та повертає список словників з product_id, price, ean
    """
    print(f"\n📂 Читаю файл: {os.path.basename(filepath)}")
    
    # Читаємо файл, пропускаємо перший порожній рядок
    df = pd.read_excel(filepath, header=None, skiprows=1)
    
    # Другий рядок (індекс 0 після skiprows) - заголовки
    df_headers = pd.read_excel(filepath, header=None, nrows=2)
    headers = df_headers.iloc[1].tolist()
    
    # Встановлюємо заголовки
    df.columns = headers
    
    # Відфільтровуємо рядок заголовків (перший рядок після skiprows)
    df = df[1:]
    
    # Витягуємо потрібні колонки
    data = []
    for idx, row in df.iterrows():
        product_id = row.get('product_id')
        price = row.get('price')
        ean = row.get('ean')
        
        # Пропускаємо рядки без product_id
        if pd.isna(product_id):
            continue
            
        # Конвертуємо product_id в int
        try:
            product_id = int(float(product_id))
        except (ValueError, TypeError):
            print(f"⚠️  Пропускаю рядок з невалідним product_id: {product_id}")
            continue
        
        # Конвертуємо price
        if pd.notna(price):
            try:
                price = float(str(price).replace(',', '.'))
            except (ValueError, TypeError):
                price = None
        else:
            price = None
        
        # Конвертуємо ean
        if pd.notna(ean):
            try:
                ean = str(int(float(ean)))
            except (ValueError, TypeError):
                ean = None
        else:
            ean = None
        
        data.append({
            'product_id': product_id,
            'price': price,
            'ean': ean
        })
    
    print(f"✅ Знайдено {len(data)} продуктів для оновлення")
    return data


def update_database(data_list):
    """
    Оновлює БД OpenCart
    """
    print(f"\n🔄 Підключаюсь до БД: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    
    connection = pymysql.connect(**DB_CONFIG)
    
    try:
        with connection.cursor() as cursor:
            updated_count = 0
            skipped_count = 0
            error_count = 0
            
            for item in data_list:
                product_id = item['product_id']
                price = item['price']
                ean = item['ean']
                
                # Спочатку перевіряємо чи існує продукт
                check_sql = f"SELECT product_id FROM {PREFIX}product WHERE product_id = %s"
                cursor.execute(check_sql, (product_id,))
                result = cursor.fetchone()
                
                if not result:
                    print(f"⚠️  Продукт {product_id} не знайдено в БД")
                    skipped_count += 1
                    continue
                
                # Формуємо UPDATE запит
                updates = []
                params = []
                
                if price is not None:
                    updates.append("price = %s")
                    params.append(price)
                
                if ean is not None:
                    updates.append("ean = %s")
                    params.append(ean)
                
                if not updates:
                    skipped_count += 1
                    continue
                
                # Додаємо product_id для WHERE
                params.append(product_id)
                
                update_sql = f"UPDATE {PREFIX}product SET {', '.join(updates)} WHERE product_id = %s"
                
                try:
                    cursor.execute(update_sql, params)
                    updated_count += 1
                    
                    if updated_count % 50 == 0:
                        print(f"  ⏳ Оновлено {updated_count} продуктів...")
                    
                except Exception as e:
                    print(f"❌ Помилка оновлення продукту {product_id}: {e}")
                    error_count += 1
            
            # Комітимо зміни
            connection.commit()
            
            print(f"\n✅ Оновлення завершено!")
            print(f"   ✔ Оновлено: {updated_count}")
            print(f"   ⚠ Пропущено: {skipped_count}")
            print(f"   ❌ Помилок: {error_count}")
            
    finally:
        connection.close()


def verify_updates(sample_ids):
    """
    Перевіряє кілька оновлених записів
    """
    print(f"\n🔍 Перевіряю оновлення для product_id: {sample_ids}")
    
    connection = pymysql.connect(**DB_CONFIG)
    
    try:
        with connection.cursor() as cursor:
            for product_id in sample_ids:
                sql = f"SELECT product_id, price, ean FROM {PREFIX}product WHERE product_id = %s"
                cursor.execute(sql, (product_id,))
                result = cursor.fetchone()
                
                if result:
                    print(f"  ID {result['product_id']}: price={result['price']}, ean={result['ean']}")
                else:
                    print(f"  ID {product_id}: не знайдено")
    finally:
        connection.close()


def main():
    print("=" * 60)
    print("🚀 ОНОВЛЕННЯ OPENCART БД З EXCEL ФАЙЛІВ")
    print("=" * 60)
    
    # Збираємо всі дані з файлів
    all_data = []
    
    for filepath in EXCEL_FILES:
        if os.path.exists(filepath):
            data = read_excel_data(filepath)
            all_data.extend(data)
        else:
            print(f"⚠️  Файл не знайдено: {filepath}")
    
    if not all_data:
        print("\n❌ Немає даних для оновлення!")
        return
    
    print(f"\n📊 Загальна кількість записів для оновлення: {len(all_data)}")
    
    # Підтвердження
    print("\n⚠️  УВАГА: Зараз будуть оновлені дані в БД OpenCart!")
    response = input("Продовжити? (yes/no): ")
    
    if response.lower() not in ['yes', 'y', 'так', 'т']:
        print("❌ Скасовано користувачем")
        return
    
    # Оновлюємо БД
    update_database(all_data)
    
    # Перевіряємо кілька записів
    sample_ids = [item['product_id'] for item in all_data[:5]]
    verify_updates(sample_ids)
    
    print("\n✅ Готово!")


if __name__ == "__main__":
    main()
