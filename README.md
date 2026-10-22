# 🐾 pwnagotchi-plugins

Коллекция собственных плагинов для [Pwnagotchi](https://pwnagotchi.org/)
(тестируется на образе **jayofelony**, Raspberry Pi Zero 2 W).

Делаем не «ещё один uploader», а штуки, которых пока ни у кого нет:
жесты, гео-профили без GPS, характер, самодиагностика и красивые отчёты.

> ⚠️ **Только по закону.** Всё здесь — для учёбы и работы со **своими** сетями
> или сетями, на тест которых есть явное письменное разрешение. Перехват чужих
> рукопожатий и подбор чужих паролей без спроса — незаконно.

---

## 📂 Структура репозитория

```
pwnagotchi-plugins/
├── README.md              ← ты здесь
├── ROADMAP.md             ← банк идей + флагманские фичи
├── CONTRIBUTING.md        ← как добавить новый плагин (конвенции)
├── docs/
│   └── INSTALLING.md      ← как поставить любой плагин на девайс
└── plugins/
    ├── README.md          ← индекс готовых плагинов
    └── template/          ← скелет для старта нового плагина
        ├── example_plugin.py
        └── example_plugin.toml
```

## 🚀 Быстрый старт

1. Скопируй `.py` плагина в папку кастомных плагинов на девайсе:
   ```bash
   sudo cp my_plugin.py /usr/local/share/pwnagotchi/custom-plugins/
   ```
2. Укажи путь и включи плагин в `/etc/pwnagotchi/config.toml`:
   ```toml
   main.custom_plugins = "/usr/local/share/pwnagotchi/custom-plugins/"
   main.plugins.my_plugin.enabled = true
   ```
3. Перезапусти: `sudo systemctl restart pwnagotchi`.

📖 Новичку — подробный пошаговый туториал: [`docs/TUTORIAL-SSH.md`](docs/TUTORIAL-SSH.md).
Кратко и с диагностикой — [`docs/INSTALLING.md`](docs/INSTALLING.md).

## 🧩 Плагины

| Плагин | Версия | Статус | Что делает |
|--------|--------|--------|------------|
| [bootlogo](plugins/bootlogo/) | 0.4.7 | ✅ | Кастомное бут-лого: фото в браузере → авто-подгон под e-ink → показ на экране и при включении |
| [pwndex](plugins/pwndex/) | 0.2.0 | ✅ | «Покедекс» сетей: каталог, поиск, пароли; свои сети → в whitelist |
| [callout](plugins/callout/) | 0.3.0 | ✅ | pwnagotchi говорит имя жертвы деаута вместо MAC (+ тест-кнопка) |
| [brain](plugins/brain/) | 0.1.0 | ✅ | ИИ-агент (bandit): учится и выбирает каналы сканирования, лицо `(A_I)` |

История версий — в [`CHANGELOG.md`](CHANGELOG.md). Теги/релизы — на вкладке **Releases** репозитория.

## 💡 Идеи

Банк идей и флагманские фичи — в [`ROADMAP.md`](ROADMAP.md).
Хочешь добавить свою — просто допиши туда.

## 🤝 Вклад

Как оформлять новый плагин — [`CONTRIBUTING.md`](CONTRIBUTING.md).
Шаблон для старта лежит в [`plugins/template/`](plugins/template/).
