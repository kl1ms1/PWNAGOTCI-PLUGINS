# 📢 deauth-announcer

Делает так, что pwnagotchi **сам говорит имя устройства вместо MAC** при деауте.

- Было: `Kickbanning A4:83:E7:11:22:33!`
- Стало: `кикаю Apple`

Как это работает: плагин **подменяет метод `voice.Voice.on_deauth` в памяти** —
сам файл `voice.py` не трогается, поэтому обновления pwnagotchi это не стирают.
Никаких лишних строк на экране — меняется **та самая фраза**, что он и так произносит.

Имя берётся: `hostname` → `vendor` (OUI) → `dev-XXXX` (хвост MAC) → `устройство`.

Бонус: лог `/root/.deauth/log.txt` + список последних в веб-морде (только чтение):
`http://<ip>:8080/plugins/deauth-announcer/`.

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
| `phrases` | набор RU | свои фразы, `{name}` = имя устройства |

## Если на экране «квадратики» вместо русских букв
Значит шрифт pwnagotchi не рисует кириллицу — задай английские фразы в `phrases`
(напр. `["kicking {name}", "{name} — no WiFi!"]`).

> ⚠️ Только для своих сетей / авторизованных тестов.
