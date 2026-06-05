#!/usr/bin/env python3
"""
Імпорт додаткових фото товарів з OpenCart (oc_product_image) у RentalHub (product_images).

Запуск (ОДНОРАЗОВО):
    cd /var/www/farforrent/backend
    source venv/bin/activate
    python3 import_oc_multi_images.py

Що робить:
1. Читає всі товари з oc_product_image (додаткові фото) з OpenCart БД
2. Для кожного фото шукає відповідний product_id у RentalHub за SKU або назвою
3. Завантажує файл з сайту OpenCart
4. Створює thumbnails (300x300) і medium (800x800)
5. Записує у product_images з source='opencart'
"""

import os
import sys
import time
import requests
from pathlib import Path
from PIL import Image
import mysql.connector
from dotenv import load_dotenv

# Load .env
SCRIPT_DIR = Path(__file__).parent
load_dotenv(SCRIPT_DIR / ".env")

# Paths
PROD_DIR = "/var/www/farforrent/backend/uploads/products"
LEGACY_DIR = "/home/farforre/farforrent.com.ua/rentalhub/backend/uploads/products"
LOCAL_DIR = "/app/backend/uploads/products"
if os.path.exists(os.path.dirname(PROD_DIR)):
    PRODUCTS_DIR = PROD_DIR
elif os.path.exists(os.path.dirname(LEGACY_DIR)):
    PRODUCTS_DIR = LEGACY_DIR
else:
    PRODUCTS_DIR = LOCAL_DIR

os.makedirs(PRODUCTS_DIR, exist_ok=True)
os.makedirs(os.path.join(PRODUCTS_DIR, "thumbnails"), exist_ok=True)
os.makedirs(os.path.join(PRODUCTS_DIR, "medium"), exist_ok=True)

# OpenCart image base URL
OC_IMAGE_BASE = os.environ.get("OPENCART_IMAGE_BASE", "https://farforrent.com.ua/image/")

# Connect to DBs
oc_db = mysql.connector.connect(
    host=os.environ.get("OC_DB_HOST", "farforre.mysql.tools"),
    port=int(os.environ.get("OC_DB_PORT", "3306")),
    user=os.environ.get("OC_DB_USERNAME"),
    password=os.environ.get("OC_DB_PASSWORD"),
    database=os.environ.get("OC_DB_DATABASE"),
    charset="utf8mb4",
)
rh_db = mysql.connector.connect(
    host=os.environ.get("RH_DB_HOST", "localhost"),
    port=int(os.environ.get("RH_DB_PORT", "3306")),
    user=os.environ.get("RH_DB_USERNAME"),
    password=os.environ.get("RH_DB_PASSWORD"),
    database=os.environ.get("RH_DB_DATABASE"),
    charset="utf8mb4",
)

oc_cur = oc_db.cursor(dictionary=True)
rh_cur = rh_db.cursor(dictionary=True)


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def make_thumb(image_path, size, subdir):
    try:
        img = Image.open(image_path)
        if img.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            bg.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = bg
        img.thumbnail(size, Image.Resampling.LANCZOS)
        out = os.path.join(PRODUCTS_DIR, subdir, os.path.basename(image_path))
        img.save(out, quality=85, optimize=True)
    except Exception as e:
        log(f"  ⚠️ Thumb error {image_path}: {e}")


def download(url, retries=2):
    for i in range(retries):
        try:
            r = requests.get(url, timeout=30, stream=True)
            if r.status_code == 200:
                return r.content
        except Exception as e:
            log(f"  ⚠️ Download error ({i+1}/{retries}) {url}: {e}")
            time.sleep(1)
    return None


def find_rh_product(oc_product_id, oc_sku, oc_model, oc_name):
    """Шукаємо відповідний RH product_id за SKU/model/name"""
    candidates = []
    if oc_sku:
        candidates.append(("sku", oc_sku.strip()))
    if oc_model:
        candidates.append(("sku", oc_model.strip()))
        candidates.append(("name", oc_model.strip()))

    for field, value in candidates:
        rh_cur.execute(
            f"SELECT product_id FROM products WHERE {field} = %s LIMIT 1",
            (value,),
        )
        row = rh_cur.fetchone()
        if row:
            return row["product_id"]
    return None


def main():
    log("🚀 Старт імпорту multi-image з OpenCart…")

    # 1. Збираємо мапу oc_product_id → RH product_id
    oc_cur.execute("""
        SELECT p.product_id, p.sku, p.model, pd.name
        FROM oc_product p
        LEFT JOIN oc_product_description pd ON p.product_id = pd.product_id AND pd.language_id = 2
    """)
    oc_products = oc_cur.fetchall()
    log(f"📦 OC products всього: {len(oc_products)}")

    oc_to_rh = {}
    not_matched = 0
    for p in oc_products:
        rh_id = find_rh_product(p["product_id"], p.get("sku"), p.get("model"), p.get("name"))
        if rh_id:
            oc_to_rh[p["product_id"]] = rh_id
        else:
            not_matched += 1
    log(f"  ✅ Знайдено в RH: {len(oc_to_rh)}, не знайдено: {not_matched}")

    # 2. Беремо всі додаткові фото з OC
    oc_cur.execute("""
        SELECT product_id, image, sort_order
        FROM oc_product_image
        WHERE image IS NOT NULL AND image != ''
        ORDER BY product_id, sort_order
    """)
    oc_images = oc_cur.fetchall()
    log(f"🖼️  Додаткових фото в OC: {len(oc_images)}")

    # 3. Скільки вже імпортовано (щоб не дублювати)
    rh_cur.execute("SELECT COUNT(*) AS c FROM product_images WHERE source = 'opencart'")
    already = rh_cur.fetchone()["c"]
    log(f"  ℹ️  Вже імпортовано з opencart: {already}")

    imported = 0
    skipped = 0
    failed = 0

    for img_row in oc_images:
        oc_pid = img_row["product_id"]
        oc_image_path = img_row["image"].strip()
        sort_order = img_row.get("sort_order") or 0

        rh_pid = oc_to_rh.get(oc_pid)
        if not rh_pid:
            skipped += 1
            continue

        # Перевірка чи це фото вже імпортовано
        rh_cur.execute("""
            SELECT id FROM product_images
            WHERE product_id = %s AND source = 'opencart' AND image_url LIKE %s
            LIMIT 1
        """, (rh_pid, f"%{os.path.basename(oc_image_path)}"))
        if rh_cur.fetchone():
            skipped += 1
            continue

        # Завантажуємо
        url = OC_IMAGE_BASE + oc_image_path
        data = download(url)
        if not data:
            failed += 1
            continue

        # Зберігаємо
        ext = os.path.splitext(oc_image_path)[1].lower() or ".jpg"
        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            ext = ".jpg"
        filename = f"oc_{rh_pid}_{oc_pid}_{sort_order}_{int(time.time())}{ext}"
        file_path = os.path.join(PRODUCTS_DIR, filename)
        try:
            with open(file_path, "wb") as f:
                f.write(data)
            make_thumb(file_path, (300, 300), "thumbnails")
            make_thumb(file_path, (800, 800), "medium")
        except Exception as e:
            log(f"  ⚠️ Save error: {e}")
            failed += 1
            continue

        # Чи це перше фото товара? (Якщо так — primary)
        rh_cur.execute(
            "SELECT COUNT(*) AS c FROM product_images WHERE product_id = %s AND is_primary = 1",
            (rh_pid,),
        )
        has_primary = rh_cur.fetchone()["c"] > 0
        is_primary = 0 if has_primary else 1

        relative_url = f"uploads/products/{filename}"
        rh_cur.execute("""
            INSERT INTO product_images
            (product_id, image_url, sort_order, is_primary, source)
            VALUES (%s, %s, %s, %s, 'opencart')
        """, (rh_pid, relative_url, sort_order, is_primary))

        if is_primary:
            rh_cur.execute(
                "UPDATE products SET image_url = %s WHERE product_id = %s AND (image_url IS NULL OR image_url = '')",
                (relative_url, rh_pid),
            )

        imported += 1
        if imported % 50 == 0:
            rh_db.commit()
            log(f"  📥 Імпортовано {imported}…")

    rh_db.commit()

    log("")
    log("=" * 60)
    log("✅ ІМПОРТ ЗАВЕРШЕНО")
    log("=" * 60)
    log(f"  📥 Імпортовано: {imported}")
    log(f"  ⏭️  Пропущено (вже є / не зматчилось): {skipped}")
    log(f"  ❌ Помилок: {failed}")
    log("=" * 60)


if __name__ == "__main__":
    try:
        main()
    finally:
        oc_cur.close()
        rh_cur.close()
        oc_db.close()
        rh_db.close()
