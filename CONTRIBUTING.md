# 🤝 Как добавить плагин

Конвенции, чтобы репозиторий оставался аккуратным.

## 1. Заведи папку

```
plugins/<имя_плагина>/
├── <имя_плагина>.py       # код (имя файла = имя плагина в config.toml)
├── <имя_плагина>.toml     # пример конфига
└── README.md              # что делает, опции, скрин/фото экрана
```

Проще всего: `cp -r plugins/template plugins/<имя_плагина>` и переименовать.

## 2. Код

- класс наследуется от `pwnagotchi.plugins.Plugin`;
- заполни `__author__`, `__version__`, `__license__`, `__description__`;
- бери только нужные хуки (список — в шаблоне);
- **всегда** снимай свои UI-поля в `on_unload` (иначе зависнут на экране);
- логируй с префиксом `[имя]`, чтобы легко грепать:
  `sudo journalctl -u pwnagotchi -f | grep -i имя`.

## 3. Имена и стиль

- имя плагина — `snake_case`, латиница (оно же — ключ в `config.toml`);
- опции читаем из `self.options.get("ключ", дефолт)`;
- не хардкодь пути к хендшейкам — бери из `agent.config()`
  (`config['bettercap']['handshakes']`); на разных образах путь разный
  (`/home/pi/handshakes` или `/root/handshakes`).

## 4. Проверка на девайсе

```bash
sudo cp plugins/<имя>/<имя>.py /usr/local/share/pwnagotchi/custom-plugins/
# включить в /etc/pwnagotchi/config.toml, затем:
sudo systemctl restart pwnagotchi
sudo journalctl -u pwnagotchi -f | grep -i <имя>
```

## 5. Обнови индексы

Добавь строку в таблицы в [`README.md`](README.md) и [`plugins/README.md`](plugins/README.md),
при желании переведи идею из [`ROADMAP.md`](ROADMAP.md) из 💡 в ✅.

## ⚠️ Этика

Плагины — для своих сетей и авторизованных тестов. Не принимаем то, что заточено
под массовую атаку/слежку за чужими людьми без согласия.
