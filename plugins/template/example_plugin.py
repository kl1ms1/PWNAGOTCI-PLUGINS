"""
example_plugin — скелет плагина Pwnagotchi.

Скопируй эту папку, переименуй файл и класс, выпили ненужные хуки — и пиши своё.
Всё, что лежит под `main.plugins.<имя>.*` в config.toml, прилетает в self.options.

Полезные хуки (бери только нужные):
    on_loaded()                              — плагин загружен, читаем self.options
    on_config_changed(config)                — применён конфиг
    on_ready(agent)                           — железо в monitor mode, bettercap поднят
    on_ui_setup(ui) / on_ui_update(ui)        — поля на e-ink экране
    on_unload(ui)                             — выгрузка (снять поля, закрыть ресурсы)
    on_handshake(agent, filename, ap, cl)     — поймано рукопожатие
    on_epoch(agent, epoch, epoch_data)        — конец эпохи (раз в несколько секунд)
    on_internet_available(agent)              — появился интернет (момент для выгрузки)
    on_webhook(path, request)                 — свои ручки в веб-морде :8080
"""

import logging

import pwnagotchi.plugins as plugins
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK


class ExamplePlugin(plugins.Plugin):
    __author__ = "you@example.com"
    __version__ = "0.1.0"
    __license__ = "MIT"
    __description__ = "Skeleton plugin — copy me to start a new one."

    def __init__(self):
        self.ready = False
        self._handshakes = 0

    # --- жизненный цикл ----------------------------------------------------
    def on_loaded(self):
        # self.options = всё из main.plugins.example.* в config.toml
        logging.info("[example] loaded, options=%s", self.options)
        self.ready = True

    def on_ready(self, agent):
        logging.info("[example] unit is ready")

    def on_unload(self, ui):
        # обязательно снимаем свои UI-поля, иначе останутся «висеть»
        with ui._lock:
            ui.remove_element("example")
        logging.info("[example] unloaded")

    # --- экран e-ink -------------------------------------------------------
    def on_ui_setup(self, ui):
        ui.add_element(
            "example",
            LabeledValue(
                color=BLACK,
                label="ex",
                value="0",
                # координаты подбираются под твой дисплей (V2/V3/V4 отличаются)
                position=(0, 95),
                label_font=fonts.Bold,
                text_font=fonts.Medium,
            ),
        )

    def on_ui_update(self, ui):
        ui.set("example", str(self._handshakes))

    # --- события -----------------------------------------------------------
    def on_handshake(self, agent, filename, access_point, client_station):
        self._handshakes += 1
        ssid = access_point.get("hostname", "?")
        logging.info("[example] handshake #%d from %s (%s)",
                     self._handshakes, ssid, filename)

    def on_internet_available(self, agent):
        # хороший момент, чтобы что-то выгрузить/синхронизировать
        if not self.ready:
            return
        logging.debug("[example] internet is up — place to upload/sync")

    # --- веб-ручка (опционально): GET http://<ip>:8080/plugins/example/ ----
    def on_webhook(self, path, request):
        return "Hello from example plugin 🐾"
