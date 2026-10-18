# 📖 Туториал: установка плагина через SSH

Пошагово, для новичка. На примере плагина **bootlogo**, но **любой плагин из этой
репы ставится точно так же** — меняется только имя файла и строки в конфиге.

> Нужно: pwnagotchi включён и подключён к компу по USB. По USB девайс обычно
> доступен по адресу **10.0.0.2** (логин `pi`, пароль по умолчанию `raspberry`).

---

## Шаг 1. Подключиться по SSH

**Windows / Mac / Linux** — в терминале (на Windows — PowerShell):
```bash
ssh pi@10.0.0.2
```
Первый раз спросит «Are you sure…?» → напиши `yes`. Введи пароль (он не отображается — это нормально).

**С телефона** — приложение вроде *Termius* (iOS/Android): новый host `10.0.0.2`, user `pi`.

---

## Шаг 2. Бэкап конфига (на всякий случай)
```bash
sudo cp /etc/pwnagotchi/config.toml /etc/pwnagotchi/config.toml.bak
```

---

## Шаг 3. Скачать плагин на девайс

Если на девайсе есть интернет — качаем прямо из репы:
```bash
sudo mkdir -p /usr/local/share/pwnagotchi/custom-plugins/
sudo wget -O /usr/local/share/pwnagotchi/custom-plugins/bootlogo.py \
  https://raw.githubusercontent.com/kl1ms1/PWNAGOTCI-PLUGINS/main/plugins/bootlogo/bootlogo.py
```

**Нет интернета на девайсе?** Тогда скачай файл на комп и закинь по `scp`
(команду запускай **на компе**, не внутри SSH):
```bash
scp bootlogo.py pi@10.0.0.2:/tmp/
# потом обратно в SSH-сессии девайса:
sudo mkdir -p /usr/local/share/pwnagotchi/custom-plugins/
sudo mv /tmp/bootlogo.py /usr/local/share/pwnagotchi/custom-plugins/
```

---

## Шаг 4. Включить плагин в конфиге
```bash
sudo nano /etc/pwnagotchi/config.toml
```
Добавь строки (для bootlogo):
```toml
main.custom_plugins = "/usr/local/share/pwnagotchi/custom-plugins/"
main.plugins.bootlogo.enabled = true
main.plugins.bootlogo.path = "/root/pwnagotchi-bootlogo.png"
```
Сохранить: **Ctrl+O**, **Enter**, выйти: **Ctrl+X**.

> `main.custom_plugins` достаточно прописать один раз — для всех кастомных плагинов.

---

## Шаг 5. Перезапустить pwnagotchi
```bash
sudo systemctl restart pwnagotchi
```

---

## Шаг 6. Проверить, что плагин поднялся
```bash
sudo journalctl -u pwnagotchi -f | grep -i bootlogo
```
Ищи строку вида `[bootlogo] loaded`. Выйти из лога — **Ctrl+C**.

---

## Шаг 7. Открыть веб-морду плагина
В браузере на компе/телефоне:
```
http://10.0.0.2:8080/plugins/bootlogo/
```
Логин/пароль — как у веб-морды pwnagotchi (по умолчанию `changeme` / `changeme`,
если не менял). Дальше: загрузи фото → покрути настройки → **«Сохранить как бут-лого»**.

---

## 🧰 Если что-то не так

| Симптом | Что делать |
|---|---|
| `ssh: connect ... timed out` | девайс не на 10.0.0.2 — проверь USB-подключение / адрес |
| `Permission denied` при копировании | добавь `sudo` перед командой |
| веб-страница 404 | проверь `main.custom_plugins` и что файл называется `bootlogo.py` |
| `plugin not found` в логе | имя файла ≠ имя в конфиге (`bootlogo.py` ↔ `main.plugins.bootlogo`) |
| сломался конфиг | откат: `sudo cp /etc/pwnagotchi/config.toml.bak /etc/pwnagotchi/config.toml` |

---

## ♻️ Обновить плагин позже
Просто перекачай свежий файл (Шаг 3) поверх старого и перезапусти (Шаг 5).

> ⚠️ Только для своих устройств.
