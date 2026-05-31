# 🚀 RentalHub — Фінальний пакет для деплою

**Зібрано:** 28.05.2026
**Frontend hash:** `main.c69d3f09.js`

---

## 📁 Структура

```
deploy_final/
├── frontend/                  ← Готовий білд React (статика для nginx)
│   ├── index.html
│   ├── asset-manifest.json
│   └── static/
│       ├── css/main.f1e70bdb.css
│       └── js/main.c69d3f09.js
│
└── backend/                   ← FastAPI бекенд
    ├── server.py              ← Головний файл (67 роутерів)
    ├── database.py            ← OpenCart DB connection
    ├── database_rentalhub.py  ← RentalHub DB (ОСНОВНА)
    ├── requirements.txt       ← Python залежності
    ├── .env.example           ← Шаблон env (перейменувати на .env)
    ├── models.py / models_extended.py / models_sqlalchemy.py
    ├── finance_rules.py
    ├── pdf_generator.py
    ├── config_manager.py
    ├── sync_all.py            ← Cron реверс-синку OpenCart
    ├── auto_sync.sh / setup_cron.sh
    │
    ├── routes/                ← 67 API роутерів (всі підключені у server.py)
    ├── services/              ← doc_engine, email_provider, etc
    ├── config/                ← company_config, damage_pricing
    ├── email_templates/       ← HTML шаблони листів
    └── migrations/            ← SQL міграції
```

---

## 🎨 1. Деплой Frontend

```bash
# На сервері rentalhub.farforrent.com.ua
sudo rm -rf /var/www/rentalhub/*    # або куди налаштовано nginx root
sudo cp -r deploy_final/frontend/* /var/www/rentalhub/
sudo chown -R www-data:www-data /var/www/rentalhub/
sudo nginx -s reload
```

### Перевірка
Відкрийте: `https://rentalhub.farforrent.com.ua/static/js/main.c69d3f09.js`
- ✅ Файл відкривається → новий білд деплоїться
- ❌ 404 → старі файли, перевірити що завантажили в правильну папку

В адмінці має бути 8 вкладок: **Замовлення / Масове редагування / Користувачі / Документи / Категорії / Витрати / Звіти / Налаштування**

---

## 🔧 2. Деплой Backend

```bash
# На сервері backrentalhub.farforrent.com.ua
cd /path/to/backend                            # шлях вашого бекенду
sudo systemctl stop rentalhub-backend          # або pm2 stop backend

# Бекап існуючого
sudo mv /path/to/backend /path/to/backend_bak_$(date +%Y%m%d)

# Залити новий
sudo cp -r deploy_final/backend /path/to/backend
cd /path/to/backend

# .env (тільки якщо немає — НЕ перетирати існуючий!)
cp .env.example .env
nano .env                                      # перевірити паролі/CORS

# Залежності
pip install -r requirements.txt

# Перезапуск
sudo systemctl start rentalhub-backend
# або
pm2 restart backend
```

### Перевірка
```bash
curl https://backrentalhub.farforrent.com.ua/api/health
curl https://backrentalhub.farforrent.com.ua/docs    # Swagger UI
```

---

## ⚙️ 3. ENV — обов'язково перевірити перед запуском

Скопіюйте `backend/.env.example` → `.env` і заповніть **РЕАЛЬНІ** паролі.

**Захищені (не міняти ключі):**
- `DB_*` — OpenCart Laravel DB (для синку клієнтів)
- `RH_DB_*` — RentalHub DB (ОСНОВНА БД)
- `OC_DB_*` — OpenCart DB (для синку товарів)
- `CORS_ORIGINS` — дозволити фронт

---

## 🔥 4. КРИТИЧНІ моменти

### Frontend
- ⚠️ **Завжди очищайте кеш браузера** після деплою (`Ctrl+Shift+R` або інкогніто)
- ⚠️ Якщо є CloudFlare — зробіть Purge Cache
- ✅ Маркер нового білду: `main.c69d3f09.js` у DevTools → Network

### Backend
- ⚠️ **Не запускайте через uvicorn вручну** — лише через systemd/pm2/supervisor
- ⚠️ **CORS_ORIGINS** має містити точний домен фронта (без слешу в кінці)
- ✅ Логи: `sudo journalctl -u rentalhub-backend -f` або `pm2 logs backend`

### Cron (реверс-синк до OpenCart)
```bash
# Налаштування cron для sync_all.py (запускає раз на 15 хв)
cd /path/to/backend
chmod +x setup_cron.sh
./setup_cron.sh
crontab -l    # перевірити що додано
```

---

## 📊 5. Що нового у цьому білді

### Frontend (28.05.2026)
- ✅ Адмін-панель: 8 вкладок (Замовлення, Масове редагування, Користувачі, Документи, Категорії, Витрати, Звіти, Налаштування)
- ✅ Мобільні топ-тулбари адаптовано (ManagerDashboard, PickingListPage)
- ✅ Кнопка "Назад" виправлена (icon на мобільному, smart fallback)
- ✅ Picking List (Лист комплектації) — групування по зонах, kits, інтеграція з тасками
- ✅ Restored Kasa 5-tab Finance UI

### Backend
- ✅ 67 роутерів (нові: `picking_list.py`, `admin_orders.py`, `bulk_products.py`, `cabinet.py`)
- ✅ `sync_all.py` — реверс-синк RentalHub → OpenCart
- ✅ Audit CRUD з auto-SKU та duplicate
- ✅ Manual cash corrections у `fin_payments` / `fin_expenses`

---

## 🆘 Troubleshooting

| Проблема | Рішення |
|----------|---------|
| Стара адмінка все ще показується | F12 → Network → Disable cache → reload. Або інкогніто |
| `main.c69d3f09.js` 404 | Файл не залився на сервер. Перевірте `/var/www/rentalhub/static/js/` |
| CORS error у консолі | Додайте домен фронта у `CORS_ORIGINS` в .env, перезапустіть бекенд |
| Bulk edit не працює | Перевірте чи в server.py включений `bulk_products.router` |
| 502 Bad Gateway | Бекенд не запущений. `sudo systemctl status rentalhub-backend` |

---

## 📞 Контакти

Питання — пиши в Emergent чат до агента.
