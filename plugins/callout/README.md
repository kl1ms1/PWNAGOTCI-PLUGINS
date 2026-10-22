# 📢 callout

pwnagotchi называет жертву деаута **по имени**, а не по MAC.
(Бывший `deauth-announcer`.)

- Было: `Kickbanning A4:83:E7:11:22:33!`
- Стало: `кикаю Apple`

Подменяет `voice.Voice.on_deauth` **в памяти** — файл `voice.py` не трогается,
обновления pwnagotchi это не стирают. Лишней строки на экране нет — меняется
**та самая фраза**, что он произносит.

Имя: `hostname` → `vendor` (OUI) → `dev-XXXX` → `устройство`.

## Веб-морда
`http://<ip>:8080/plugins/callout/`
- **🧪 Тест фразы** — показывает, что он скажет, **не дожидаясь реального деаута**.
- Список последних целей по имени + лог `/root/.callout/log.txt`.

## Установка
```bash
sudo cp callout.py /usr/local/share/pwnagotchi/custom-plugins/
# если ставил старый deauth-announcer — удали его, чтобы не дублировать:
sudo rm -f /usr/local/share/pwnagotchi/custom-plugins/deauth_announcer.py
sudo nano /etc/pwnagotchi/config.toml   # main.plugins.callout.enabled = true (и убери deauth-announcer, если был)
sudo systemctl restart pwnagotchi
```

## Опции
| Ключ | По умолчанию | Описание |
|---|---|---|
| `enabled` | — | включить |
| `phrases` | набор RU | свои фразы, `{name}` = имя |

> Если на e-ink «квадратики» вместо русских букв — шрифт не держит кириллицу,
> задай английские фразы в `phrases`. ⚠️ Только для своих сетей.
