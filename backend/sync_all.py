#!/usr/bin/env python3
"""
Master sync script — RentalHub ↔ OpenCart
PRODUCTION VERSION

NEW DIRECTION (Feb 2026):
- FROM OpenCart we ONLY pull new orders (status_id=2) → RentalHub
- TO OpenCart we push everything else: product changes, quantities, photo, name, sizes, color, category/subcategory
- RentalHub is the source of truth for the product catalog

Run via cron every 30 minutes.
"""
import mysql.connector
from datetime import datetime
import time
import os

# Database configurations
OC = {
    'host': 'farforre.mysql.tools',
    'database': 'farforre_db',
    'user': 'farforre_db',
    'password': 'gPpAHTvv',
    'charset': 'utf8mb4'
}

RH = {
    'host': 'farforre.mysql.tools',
    'database': 'farforre_rentalhub',
    'user': 'farforre_rentalhub',
    'password': '-nu+3Gp54L',
    'charset': 'utf8mb4'
}

# Image paths — Production or Local
PRODUCTION_DIR = "/home/farforre/farforrent.com.ua/rentalhub/backend/uploads/products"
LOCAL_DIR = "/app/backend/uploads/products"
PRODUCTS_DIR = PRODUCTION_DIR if os.path.exists(os.path.dirname(PRODUCTION_DIR)) else LOCAL_DIR

# OC image catalog (used when reverse-pushing photos)
OC_IMAGE_BASE_DIR_CANDIDATES = [
    "/home/farforre/farforrent.com.ua/image/catalog/rentalhub",
    "/var/www/farforrent.com.ua/image/catalog/rentalhub",
]
OC_IMAGE_TARGET_DIR = next((p for p in OC_IMAGE_BASE_DIR_CANDIDATES if os.path.exists(os.path.dirname(p))), None)


def log(msg):
    """Log with timestamp"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ============================================================
# CLIENT AUTO-CREATE FROM ORDER
# ============================================================
def ensure_client_from_order(cursor, customer_name, phone, email):
    """Find or create client_users entry. Unique by email."""
    if not customer_name:
        return None
    email = (email or '').strip()
    email_normalized = email.lower().strip() if email else ''
    if not email_normalized or '@' not in email_normalized:
        return None

    cursor.execute(
        "SELECT id FROM client_users WHERE email_normalized = %s LIMIT 1",
        (email_normalized,)
    )
    row = cursor.fetchone()
    if row:
        client_id = row[0] if isinstance(row, tuple) else row['id']
        phone = (phone or '').strip()
        if phone:
            cursor.execute(
                """UPDATE client_users
                   SET phone = COALESCE(NULLIF(phone, ''), %s),
                       last_order_date = CURDATE(), updated_at = NOW()
                   WHERE id = %s""",
                (phone, client_id)
            )
        else:
            cursor.execute(
                "UPDATE client_users SET last_order_date = CURDATE(), updated_at = NOW() WHERE id = %s",
                (client_id,)
            )
        return client_id

    phone = (phone or '').strip()
    cursor.execute("""
        INSERT INTO client_users
        (email, email_normalized, full_name, phone, source, is_active, created_at, updated_at, last_order_date)
        VALUES (%s, %s, %s, %s, 'opencart', 1, NOW(), NOW(), CURDATE())
    """, (email, email_normalized, customer_name, phone or None))

    cursor.execute("SELECT LAST_INSERT_ID()")
    new_id = cursor.fetchone()
    return new_id[0] if new_id else None


# ============================================================
# RH → OC: PUSH QUANTITIES
# ============================================================
def push_quantities_to_opencart():
    """Push quantities FROM RentalHub TO OpenCart (RH = source of truth)"""
    log("📊 Pushing quantities RH → OpenCart...")
    try:
        oc = mysql.connector.connect(**OC)
        rh = mysql.connector.connect(**RH)
        oc_cur = oc.cursor()
        rh_cur = rh.cursor(dictionary=True)

        rh_cur.execute("SELECT product_id, quantity FROM products WHERE product_id IS NOT NULL")
        rh_products = rh_cur.fetchall()
        if not rh_products:
            log("  ✅ No products to push")
            oc_cur.close(); rh_cur.close(); oc.close(); rh.close()
            return 0

        count = 0
        for p in rh_products:
            oc_cur.execute(
                "UPDATE oc_product SET quantity = %s WHERE product_id = %s",
                (p['quantity'] or 0, p['product_id'])
            )
            count += oc_cur.rowcount

        oc.commit()
        log(f"  ✅ Pushed quantities for {count} products")
        oc_cur.close(); rh_cur.close(); oc.close(); rh.close()
        return count
    except Exception as e:
        log(f"  ❌ Error: {e}")
        import traceback; traceback.print_exc()
        return 0


# ============================================================
# RH → OC: PUSH PRODUCT EDITS (name, sizes, color, image, categories)
# ============================================================
def sync_rh_to_opencart_products():
    """
    🔁 REVERSE SYNC: push manager edits FROM RentalHub TO OpenCart.

    Only updates products where `updated_at > last_pushed_to_oc` (recently edited).
    Synced fields: model (sku), name, height/width/depth, color, image, category, subcategory.
    New RH products that don't exist in OC yet are INSERTed with minimal fields
    (status=0 — hidden until admin reviews in OC).
    """
    log("🔁 Pushing RH product edits → OpenCart...")
    updated = inserted = errors = 0
    try:
        oc = mysql.connector.connect(**OC)
        rh = mysql.connector.connect(**RH)
        oc_cur = oc.cursor(dictionary=True)
        rh_cur = rh.cursor(dictionary=True)

        # 1. Pick only changed products
        rh_cur.execute("""
            SELECT product_id, sku, name, color, image_url,
                   height_cm, width_cm, depth_cm,
                   category_name, subcategory_name,
                   price, rental_price, description, quantity, status
            FROM products
            WHERE updated_at IS NOT NULL
              AND (last_pushed_to_oc IS NULL OR last_pushed_to_oc < updated_at)
            ORDER BY updated_at ASC
            LIMIT 500
        """)
        changed = rh_cur.fetchall()
        if not changed:
            log("  ✓ No changes to push")
            oc_cur.close(); rh_cur.close(); oc.close(); rh.close()
            return 0

        log(f"  Found {len(changed)} changed products")

        # Preload category_name → category_id map (OpenCart, lang_id=4)
        oc_cur.execute("""
            SELECT cd.category_id, cd.name
            FROM oc_category_description cd
            WHERE cd.language_id = 4
        """)
        cat_map = {row['name'].strip().lower(): row['category_id'] for row in oc_cur.fetchall()}

        COLOR_ATTR_ID = 13
        LANG_ID = 4
        rh_upd = rh.cursor()

        for p in changed:
            pid = p['product_id']
            try:
                # 2. Check existence in OC
                oc_cur.execute("SELECT product_id, image FROM oc_product WHERE product_id = %s", (pid,))
                oc_row = oc_cur.fetchone()

                # ----- HANDLE IMAGE: copy file from RH uploads to OC catalog ------
                oc_image_value = None
                if p['image_url']:
                    src_rel = p['image_url'].lstrip('/')
                    src_path = src_rel
                    if src_rel.startswith('uploads/'):
                        src_path = os.path.join(os.path.dirname(PRODUCTS_DIR), src_rel.split('uploads/', 1)[1] if '/' in src_rel else src_rel)
                        # Above is a no-op fallback; safer:
                        src_path = '/app/backend/' + src_rel
                        if not os.path.exists(src_path):
                            src_path = os.path.join('/home/farforre/farforrent.com.ua/rentalhub/backend', src_rel)
                    if OC_IMAGE_TARGET_DIR and os.path.exists(src_path):
                        os.makedirs(OC_IMAGE_TARGET_DIR, exist_ok=True)
                        fname = os.path.basename(src_path)
                        dst_path = os.path.join(OC_IMAGE_TARGET_DIR, fname)
                        try:
                            import shutil
                            shutil.copy2(src_path, dst_path)
                            # OC expects relative path inside its image/ folder
                            oc_image_value = f"catalog/rentalhub/{fname}"
                        except Exception as cpe:
                            log(f"    ⚠️ photo copy failed for {pid}: {cpe}")
                            oc_image_value = src_rel[:255]
                    else:
                        # Best-effort: store whatever we have, admin maps the path
                        oc_image_value = src_rel[:255]

                if oc_row:
                    # === UPDATE existing ===
                    sets, params = [], []
                    if p['height_cm'] is not None:
                        sets.append("height = %s"); params.append(float(p['height_cm']))
                    if p['width_cm'] is not None:
                        sets.append("width = %s"); params.append(float(p['width_cm']))
                    if p['depth_cm'] is not None:
                        sets.append("length = %s"); params.append(float(p['depth_cm']))
                    if p['sku']:
                        sets.append("model = %s"); params.append(p['sku'][:64])
                        sets.append("sku = %s");   params.append(p['sku'][:64])
                    if oc_image_value and oc_image_value != (oc_row.get('image') or ''):
                        sets.append("image = %s"); params.append(oc_image_value[:255])
                    if sets:
                        sets.append("date_modified = NOW()")
                        params.append(pid)
                        oc_cur.execute(f"UPDATE oc_product SET {', '.join(sets)} WHERE product_id = %s", tuple(params))

                    # Update description (name) — lang 4
                    if p['name']:
                        oc_cur.execute("""
                            UPDATE oc_product_description
                               SET name = %s
                             WHERE product_id = %s AND language_id = %s
                        """, (p['name'][:255], pid, LANG_ID))
                else:
                    # === INSERT new product (minimal required fields, status=0 — hidden) ===
                    oc_cur.execute("""
                        INSERT INTO oc_product
                            (product_id, model, sku, upc, ean, jan, isbn, mpn, location,
                             quantity, stock_status_id, image, manufacturer_id, shipping,
                             price, points, tax_class_id, date_available, weight, weight_class_id,
                             length, width, height, length_class_id, subtract, minimum,
                             sort_order, status, viewed, noindex, date_added, date_modified, cost)
                        VALUES
                            (%s, %s, %s, '', '', '', '', '', '',
                             %s, 5, %s, 0, 1,
                             %s, 0, 9, CURDATE(), 0, 1,
                             %s, %s, %s, 1, 1, 1,
                             0, 0, 0, 1, NOW(), NOW(), 0)
                    """, (
                        pid, (p['sku'] or f"RH-{pid}")[:64], (p['sku'] or f"RH-{pid}")[:64],
                        int(p['quantity'] or 0), (oc_image_value or '')[:255],
                        float(p['rental_price'] or 0),
                        float(p['depth_cm'] or 0), float(p['width_cm'] or 0), float(p['height_cm'] or 0),
                    ))
                    # Description (4 languages aren't all required; we write only UA=4)
                    oc_cur.execute("""
                        INSERT INTO oc_product_description
                            (product_id, language_id, name, description, description_mini, tag,
                             meta_title, meta_description, meta_keyword, meta_h1)
                        VALUES (%s, %s, %s, %s, '', '', %s, '', '', %s)
                    """, (pid, LANG_ID, (p['name'] or '')[:255], (p['description'] or ''),
                          (p['name'] or '')[:255], (p['name'] or '')[:255]))
                    inserted += 1
                    log(f"  ➕ Inserted new OC product {pid} ({p['sku']}) — status=0 (hidden)")

                # === COLOR attribute ===
                if p['color']:
                    oc_cur.execute("""
                        SELECT 1 FROM oc_product_attribute
                         WHERE product_id = %s AND attribute_id = %s AND language_id = %s
                    """, (pid, COLOR_ATTR_ID, LANG_ID))
                    if oc_cur.fetchone():
                        oc_cur.execute("""
                            UPDATE oc_product_attribute SET text = %s
                             WHERE product_id = %s AND attribute_id = %s AND language_id = %s
                        """, (p['color'][:255], pid, COLOR_ATTR_ID, LANG_ID))
                    else:
                        oc_cur.execute("""
                            INSERT INTO oc_product_attribute (product_id, attribute_id, language_id, text)
                            VALUES (%s, %s, %s, %s)
                        """, (pid, COLOR_ATTR_ID, LANG_ID, p['color'][:255]))

                # === CATEGORIES (replace all) ===
                new_cats = []
                if p['category_name']:
                    cid = cat_map.get(p['category_name'].strip().lower())
                    if cid:
                        new_cats.append((cid, 1))
                    else:
                        log(f"    ⚠️ Category '{p['category_name']}' not in OC (product {pid})")
                if p['subcategory_name']:
                    scid = cat_map.get(p['subcategory_name'].strip().lower())
                    if scid:
                        new_cats.append((scid, 0))
                    else:
                        log(f"    ⚠️ Subcategory '{p['subcategory_name']}' not in OC (product {pid})")
                if new_cats:
                    oc_cur.execute("DELETE FROM oc_product_to_category WHERE product_id = %s", (pid,))
                    for cid, is_main in new_cats:
                        oc_cur.execute("""
                            INSERT INTO oc_product_to_category (product_id, category_id, main_category)
                            VALUES (%s, %s, %s)
                        """, (pid, cid, is_main))

                # Mark as pushed
                rh_upd.execute(
                    "UPDATE products SET last_pushed_to_oc = NOW() WHERE product_id = %s",
                    (pid,)
                )
                if oc_row:
                    updated += 1

            except Exception as item_err:
                errors += 1
                log(f"  ❌ Product {pid}: {item_err}")
                continue

        oc.commit()
        rh.commit()
        log(f"  ✅ Pushed RH→OC: {updated} updated, {inserted} inserted, {errors} errors")
        oc_cur.close(); rh_cur.close(); rh_upd.close(); oc.close(); rh.close()
        return updated + inserted

    except Exception as e:
        log(f"  ❌ Fatal: {e}")
        import traceback; traceback.print_exc()
        return 0


# ============================================================
# OC → RH: PULL NEW ORDERS  (the ONLY direction OC → RH that we keep)
# ============================================================
def sync_orders_from_opencart():
    """
    ✅ Pull NEW orders from OpenCart (order_status_id = 2 "В обробці")
    After import, switch OC status to 29 (Sent to RH).
    """
    log("📋 Syncing NEW orders from OpenCart...")
    try:
        oc_conn = mysql.connector.connect(**OC)
        rh_conn = mysql.connector.connect(**RH)
        oc_cur = oc_conn.cursor(dictionary=True)
        rh_cur = rh_conn.cursor()

        rh_cur.execute("SELECT MAX(order_id) FROM orders")
        last_synced = rh_cur.fetchone()[0] or 0
        log(f"  📍 Last synced order_id: {last_synced}")

        oc_cur.execute("""
            SELECT
                o.order_id, o.order_status_id, o.customer_id,
                o.firstname, o.lastname, o.email, o.telephone,
                o.total, o.date_added, o.comment,
                osf.rent_issue_date, osf.rent_return_date
            FROM oc_order o
            LEFT JOIN oc_order_simple_fields osf ON o.order_id = osf.order_id
            WHERE o.order_status_id = 2
              AND o.order_id > %s
            ORDER BY o.order_id ASC
            LIMIT 50
        """, (last_synced,))
        new_orders = oc_cur.fetchall()
        log(f"  📦 Found {len(new_orders)} new orders with status=2")

        synced_count = 0
        for order in new_orders:
            order_id = order['order_id']
            customer_name = f"{order['firstname']} {order['lastname']}".strip()

            oc_cur.execute("""
                SELECT op.order_product_id, op.product_id, op.name as product_name,
                       op.model as sku, op.quantity, op.price, op.total,
                       p.image, p.ean
                FROM oc_order_product op
                LEFT JOIN oc_product p ON op.product_id = p.product_id
                WHERE op.order_id = %s
            """, (order_id,))
            order_items = oc_cur.fetchall()
            if not order_items:
                log(f"  ⚠️ Order {order_id} has no items, skipping")
                continue

            total_rental = sum(float(item['total'] or 0) for item in order_items)
            total_deposit = 0
            total_loss_value = 0
            for item in order_items:
                ean_value = float(item['ean']) if item.get('ean') else 0
                quantity = int(item['quantity'])
                total_deposit += (ean_value / 2) * quantity
                total_loss_value += ean_value * quantity

            rental_start = order['rent_issue_date'] or order['date_added'].date()
            rental_end = order['rent_return_date'] or order['date_added'].date()
            rental_days = None
            if rental_start and rental_end:
                from datetime import datetime as dt
                if isinstance(rental_start, str):
                    rental_start = dt.strptime(rental_start, '%Y-%m-%d').date()
                if isinstance(rental_end, str):
                    rental_end = dt.strptime(rental_end, '%Y-%m-%d').date()
                rental_days = (rental_end - rental_start).days
                if rental_days < 1:
                    rental_days = 1

            try:
                rh_cur.execute("""
                    INSERT INTO orders (
                        order_id, order_number, customer_id, customer_name,
                        customer_phone, customer_email,
                        rental_start_date, rental_end_date, rental_days,
                        status, total_price, deposit_amount, total_loss_value,
                        notes, created_at, synced_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """, (
                    order_id, f"OC-{order_id}", order['customer_id'], customer_name,
                    order['telephone'], order['email'],
                    rental_start, rental_end, rental_days,
                    'awaiting_customer',
                    total_rental, total_deposit, total_loss_value,
                    order['comment'], order['date_added']
                ))

                for item in order_items:
                    image_url = f"https://www.farforrent.com.ua/image/{item['image']}" if item['image'] else None
                    rh_cur.execute("""
                        INSERT INTO order_items (
                            order_id, product_id, product_name,
                            quantity, price, total_rental, image_url
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        order_id, item['product_id'], item['product_name'],
                        item['quantity'], item['price'], item['total'], image_url
                    ))

                client_comment = order.get('comment', '').strip() if order.get('comment') else ''
                if client_comment:
                    rh_cur.execute("""
                        INSERT INTO order_internal_notes
                            (order_id, user_id, user_name, message, created_at)
                        VALUES (%s, %s, %s, %s, NOW())
                    """, (order_id, None, '💬 Коментар клієнта', client_comment))

                try:
                    client_user_id = ensure_client_from_order(
                        rh_cur, customer_name, order['telephone'], order['email']
                    )
                    if client_user_id:
                        rh_cur.execute(
                            "UPDATE orders SET client_user_id = %s WHERE order_id = %s",
                            (client_user_id, order_id)
                        )
                except Exception as ce:
                    log(f"  ⚠️ Client auto-create error for order {order_id}: {ce}")

                rh_conn.commit()
                synced_count += 1
                log(f"  ✅ Synced order #{order_id} ({customer_name})" + (" + comment" if client_comment else ""))

                # Flip OC status to 29 (sent to RH)
                oc_cur.execute("UPDATE oc_order SET order_status_id = 29 WHERE order_id = %s", (order_id,))
                oc_conn.commit()
                log(f"  ✅ OC #{order_id} → status 29")

            except mysql.connector.IntegrityError:
                log(f"  ⚠️ Order {order_id} already exists")
                continue

        log(f"  ✅ Successfully synced {synced_count} new orders")
        oc_cur.close(); rh_cur.close(); oc_conn.close(); rh_conn.close()
        return synced_count

    except Exception as e:
        log(f"  ❌ Error: {e}")
        import traceback; traceback.print_exc()
        return 0


# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 60)
    print("🔄 RENTALHUB ↔ OPENCART SYNC (RH = source of truth)")
    print("=" * 60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Images dir: {PRODUCTS_DIR}")
    print(f"OC image target: {OC_IMAGE_TARGET_DIR or '(not detected — image paths stored as-is)'}\n")

    total_start = time.time()

    # 1. Pull new orders FROM OpenCart (the only OC→RH direction we keep)
    order_count = sync_orders_from_opencart()

    # 2. Push product edits TO OpenCart (name, sizes, color, image, categories)
    pushed_count = sync_rh_to_opencart_products()

    # 3. Push quantities TO OpenCart
    qty_count = push_quantities_to_opencart()

    total_duration = time.time() - total_start

    print("\n" + "=" * 60)
    print("✅ SYNC COMPLETED")
    print("=" * 60)
    print(f"📦 NEW ORDERS pulled: {order_count}")
    print(f"🔁 RH→OC products pushed: {pushed_count}")
    print(f"📊 Qty rows updated in OC: {qty_count}")
    print(f"Duration: {total_duration:.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
