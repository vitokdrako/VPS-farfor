# Готовий білд Event Tool (клієнтський фронт FarforDecorOrenda)

Цей білд звертається до production backend: `https://backrentalhub.farforrent.com.ua`

## Деплой на VPS — 3 команди

```bash
# 1. На VPS, у репо
cd /var/www/farforrent
git pull

# 2. Скопіювати готовий білд у Nginx web root
sudo rm -rf /var/www/event-tool-build
sudo cp -r event-tool-build /var/www/event-tool-build
sudo chown -R www-data:www-data /var/www/event-tool-build

# 3. Підтягнути Nginx конфіг і перезавантажити
sudo cp nginx-rentalhub-unified.conf /etc/nginx/sites-available/farforrent
sudo ln -sf /etc/nginx/sites-available/farforrent /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

## Перевірка

```bash
# Має повернути index.html Event Tool
curl http://173.242.49.48/ | head -3

# Має повернути головний JS бандл
curl -I http://173.242.49.48/static/js/main.694fd7d9.js
```

Відкрий браузер: `http://173.242.49.48/` — побачиш каталог FarforDecorOrenda.

## Що тут лежить

| Файл | Призначення |
|------|-------------|
| `index.html` | Точка входу SPA |
| `static/js/main.694fd7d9.js` | Головний бандл (компільований React) |
| `static/css/main.8068b92a.css` | Стилі |
| `static/js/239.*.chunk.js`, `455.*.chunk.js`, `977.*.chunk.js` | Code-split chunks |
| `static/media/Montserrat-*.woff` | Шрифти |
| `fonts/` | Додаткові шрифти |
| `logo.svg` | Лого FarforDecorOrenda |
| `.env` | Reference (не потрібен у production — змінні запечені у бандлі) |

## API endpoint

Білд жорстко звертається до `https://backrentalhub.farforrent.com.ua/api/...` — це ваш production backend, який вже працює і обробляє замовлення в спільну БД RentalHub.
