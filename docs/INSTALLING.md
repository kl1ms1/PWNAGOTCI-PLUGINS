# 📥 Установка плагина на Pwnagotchi

Проверено на образе jayofelony (Raspberry Pi Zero 2 W).

## 1. Скопировать файл на девайс

По SSH (по USB девайс обычно на `10.0.0.2`):

```bash
# с компа:
scp plugins/<имя>/<имя>.py pi@10.0.0.2:/tmp/

# на девайсе:
sudo mkdir -p /usr/local/share/pwnagotchi/custom-plugins/
sudo mv /tmp/<имя>.py /usr/local/share/pwnagotchi/custom-plugins/
```

## 2. Включить в config.toml

```bash
sudo nano /etc/pwnagotchi/config.toml
```

```toml
main.custom_plugins = "/usr/local/share/pwnagotchi/custom-plugins/"
main.plugins.<имя>.enabled = true
# + опции плагина, если есть
```

Сохрани: `Ctrl+O`, `Enter`, `Ctrl+X`.

## 3. Перезапуск и проверка

```bash
sudo systemctl restart pwnagotchi
sudo journalctl -u pwnagotchi -f | grep -i <имя>
```

Ищи строку `[<имя>] loaded` (или свою из `on_loaded`).

## 🧰 Диагностика

| Симптом | Причина / что делать |
|---|---|
| `plugin not found` | файл не в `custom_plugins` или имя файла ≠ имени в конфиге |
| поле осталось «висеть» на экране | в `on_unload` не вызван `ui.remove_element(...)` |
| `tail: cannot open ...potfile` | не ошибка — файла результатов ещё нет, появится сам |
| плагину нужен интернет, а его нет | `ping -c3 1.1.1.1`; на одном радио Wi-Fi-клиент + охота несовместимы — нужен USB/BT/второй адаптер |
| поле не на том месте | подбери `position=(x, y)` под свой дисплей (V2/V3/V4 разные) |

## 💾 Бэкап конфига

Перед правками:
```bash
sudo cp /etc/pwnagotchi/config.toml /etc/pwnagotchi/config.toml.bak
```
