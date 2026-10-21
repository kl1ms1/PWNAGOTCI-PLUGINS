# 📢 deauth-announcer

Показывает, **кого** глушит pwnagotchi — по **имени/вендору**, а не по голому MAC.
`отключаю: Apple ▸ MyWiFi` вместо `deauth A4:83:E7:11:22:33`.

- Строка на **e-ink** (последняя цель деаута).
- **Лог** в `/root/.deauth/log.txt`.
- **Веб-морда** со списком последних: `http://<ip>:8080/plugins/deauth-announcer/` (только чтение).

Имя берётся так: `hostname` → `vendor` (по OUI из bettercap) → `dev-XXXX` (хвост MAC) → `устройство`.

## Установка
```bash
sudo cp deauth_announcer.py /usr/local/share/pwnagotchi/custom-plugins/
sudo nano /etc/pwnagotchi/config.toml   # строки из deauth-announcer.toml (custom_plugins — один раз!)
sudo systemctl restart pwnagotchi
```

## Опции
| Ключ | По умолчанию | Описание |
|---|---|---|
| `enabled` | — | включить |
| `show_ui` | `true` | показывать строку на e-ink |
| `position` | `"0,95"` | позиция строки (x,y) |

> ⚠️ Только для своих сетей / авторизованных тестов.
