"""
example_plugin — a Pwnagotchi plugin skeleton.

Copy this folder, rename the file and class, strip the hooks you don't need — and
write your own. Anything under `main.plugins.<name>.*` in config.toml lands in self.options.

Useful hooks (take only what you need):
    on_loaded()                              — plugin loaded, read self.options
    on_config_changed(config)                — config applied
    on_ready(agent)                           — radio in monitor mode, bettercap up
    on_ui_setup(ui) / on_ui_update(ui)        — elements on the e-ink screen
    on_unload(ui)                             — unload (remove elements, close resources)
    on_handshake(agent, filename, ap, cl)     — a handshake was captured
    on_epoch(agent, epoch, epoch_data)        — end of an epoch (every few seconds)
    on_internet_available(agent)              — internet appeared (a moment to upload)
    on_webhook(path, request)                 — your own routes in the web UI on :8080
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

    # --- lifecycle ---------------------------------------------------------
    def on_loaded(self):
        # self.options = everything from main.plugins.example.* in config.toml
        logging.info("[example] loaded, options=%s", self.options)
        self.ready = True

    def on_ready(self, agent):
        logging.info("[example] unit is ready")

    def on_unload(self, ui):
        # always remove your UI elements, otherwise they stay "stuck"
        with ui._lock:
            ui.remove_element("example")
        logging.info("[example] unloaded")

    # --- e-ink screen ------------------------------------------------------
    def on_ui_setup(self, ui):
        ui.add_element(
            "example",
            LabeledValue(
                color=BLACK,
                label="ex",
                value="0",
                # coordinates depend on your display (V2/V3/V4 differ)
                position=(0, 95),
                label_font=fonts.Bold,
                text_font=fonts.Medium,
            ),
        )

    def on_ui_update(self, ui):
        ui.set("example", str(self._handshakes))

    # --- events ------------------------------------------------------------
    def on_handshake(self, agent, filename, access_point, client_station):
        self._handshakes += 1
        ssid = access_point.get("hostname", "?")
        logging.info("[example] handshake #%d from %s (%s)",
                     self._handshakes, ssid, filename)

    def on_internet_available(self, agent):
        # a good moment to upload/sync something
        if not self.ready:
            return
        logging.debug("[example] internet is up — place to upload/sync")

    # --- web route (optional): GET http://<ip>:8080/plugins/example/ -------
    def on_webhook(self, path, request):
        return "Hello from example plugin 🐾"
