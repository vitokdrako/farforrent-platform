#!/usr/bin/env python3
"""
Сканує /var/www/farforrent/backend/uploads/products/thumbnails/
Витягує product_id з імен файлів формату: oc_{pid}_{pid}_{sort}_{timestamp}.{ext}
Заповнює таблицю product_images та оновлює products.image_url
"""
import os
import re
import sys
from pathlib import Path
from collections import defaultdict
from dotenv import load_dotenv
import pymysql

load_dotenv("/var/www/farforrent/backend/.env")

THUMB_DIR = "/var/www/farforrent/backend/uploads/products/thumbnails"
MEDIUM_DIR = "/var/www/farforrent/backend/uploads/products/medium"

# oc_{product_id}_{any}_{sort_order}_{timestamp}.{ext}
PATTERN = re.compile(r"^oc_(\d+)_\d+_(\d+)_(\d+)\.(jpg|jpeg|png|webp)$", re.IGNORECASE)


def main():
    if not os.path.isdir(THUMB_DIR):
        print(f"❌ {THUMB_DIR} not found")
        sys.exit(1)

    # 1) Збираємо мапу product_id -> [(sort_order, filename), ...]
    pid_files = defaultdict(list)
    total_scanned = 0
    for fname in os.listdir(THUMB_DIR):
        m = PATTERN.match(fname)
        if not m:
            continue
        pid = int(m.group(1))
        sort_order = int(m.group(2))
        pid_files[pid].append((sort_order, fname))
        total_scanned += 1

    print(f"📂 Scanned: {total_scanned} files for {len(pid_files)} products")

    # 2) Підключення до БД
    conn = pymysql.connect(
        host=os.environ["RH_DB_HOST"],
        user=os.environ["RH_DB_USERNAME"],
        password=os.environ["RH_DB_PASSWORD"],
        db=os.environ["RH_DB_DATABASE"],
        charset="utf8mb4",
        autocommit=False,
    )
    cur = conn.cursor()

    # 3) Очистимо таблицю (idempotent перезаповнення)
    cur.execute("DELETE FROM product_images WHERE source = 'thumbnails_scan'")

    # 4) INSERT для кожного product_id
    inserted = 0
    updated_main = 0
    for pid, files in pid_files.items():
        # Сортуємо за sort_order
        files.sort(key=lambda x: x[0])
        for idx, (sort_order, fname) in enumerate(files):
            image_url = f"uploads/products/thumbnails/{fname}"
            is_primary = 1 if idx == 0 else 0
            cur.execute(
                """INSERT INTO product_images
                   (product_id, image_url, sort_order, is_primary, source)
                   VALUES (%s, %s, %s, %s, 'thumbnails_scan')""",
                (pid, image_url, sort_order, is_primary),
            )
            inserted += 1
        # Оновимо products.image_url на primary
        primary_fname = files[0][1]
        cur.execute(
            "UPDATE products SET image_url = %s WHERE product_id = %s",
            (f"uploads/products/thumbnails/{primary_fname}", pid),
        )
        updated_main += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ Inserted {inserted} rows into product_images")
    print(f"✅ Updated products.image_url for {updated_main} products")
    print("Done.")


if __name__ == "__main__":
    main()
