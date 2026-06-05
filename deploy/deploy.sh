#!/bin/bash
# ============================================================
# Деплой обох аплікацій на VPS
# RentalHub адмінка → http://173.242.49.48:8080
# Event Tool клієнти → http://173.242.49.48
# ============================================================
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "📂 Repo root: $REPO_ROOT"

# ===== 1. Event Tool frontend (статика — вже зібрано) =====
echo "🟢 [1/5] Викладаємо Event Tool білд..."
sudo rm -rf /var/www/event-tool-build
sudo cp -r "$REPO_ROOT/event-tool-build" /var/www/event-tool-build
sudo chown -R www-data:www-data /var/www/event-tool-build

# ===== 2. RentalHub frontend (білдимо з джерел) =====
echo "🟢 [2/5] Білдимо RentalHub адмінку..."
cd "$REPO_ROOT/frontend"
if [ ! -d node_modules ]; then
  yarn install
fi
yarn build
echo "  Білд готовий у $REPO_ROOT/frontend/build"

# ===== 3. Systemd unit-и =====
echo "🟢 [3/5] Встановлюємо systemd unit-и..."
sudo cp "$REPO_ROOT/deploy/rentalhub-backend.service" /etc/systemd/system/
# Event Tool unit — тільки якщо є бекенд директорія
if [ -d /var/www/event-tool/backend ]; then
  sudo cp "$REPO_ROOT/deploy/event-tool-backend.service" /etc/systemd/system/
fi
sudo systemctl daemon-reload

# ===== 4. Nginx конфіги =====
echo "🟢 [4/5] Налаштовуємо Nginx..."
sudo cp "$REPO_ROOT/deploy/nginx-event-tool.conf" /etc/nginx/sites-available/event-tool
sudo cp "$REPO_ROOT/deploy/nginx-rentalhub.conf"  /etc/nginx/sites-available/rentalhub-admin
sudo ln -sf /etc/nginx/sites-available/event-tool      /etc/nginx/sites-enabled/
sudo ln -sf /etc/nginx/sites-available/rentalhub-admin /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx

# ===== 5. Запуск backend-ів =====
echo "🟢 [5/5] Перезапускаємо backend-и..."
sudo systemctl enable rentalhub-backend 2>/dev/null || true
sudo systemctl restart rentalhub-backend || echo "⚠️ rentalhub-backend не стартує — перевір логи: journalctl -u rentalhub-backend -n 50"

if [ -d /var/www/event-tool/backend ]; then
  sudo systemctl enable event-tool-backend 2>/dev/null || true
  sudo systemctl restart event-tool-backend || echo "⚠️ event-tool-backend не стартує — перевір логи: journalctl -u event-tool-backend -n 50"
else
  echo "⚠️ /var/www/event-tool/backend ще не створено — Event Tool backend не запускається."
  echo "   Це ОК, бо готовий білд Event Tool fronту звертається до https://backrentalhub.farforrent.com.ua напряму."
fi

echo ""
echo "✅ Деплой завершено!"
echo ""
echo "Перевір:"
echo "  Event Tool (клієнти):  http://173.242.49.48"
echo "  RentalHub адмінка:     http://173.242.49.48:8080"
echo ""
echo "Логи:"
echo "  sudo journalctl -u rentalhub-backend -f"
echo "  sudo tail -f /var/log/nginx/error.log"
