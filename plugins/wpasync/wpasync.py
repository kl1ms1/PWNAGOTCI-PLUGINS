"""
wpasync — a "Upload to wpa-sec NOW" button for pwnagotchi.

The built-in `wpa-sec` plugin only uploads when pwnagotchi *detects* internet
(its `on_internet_available` hook). If the device HAS internet — e.g. shared
over USB from your PC — but pwnagotchi hasn't noticed yet, this forces the
wpa-sec plugin to run its upload + download right now.

It first checks that the internet is actually reachable, so it never pokes
wpa-sec offline (which would otherwise mark files as skipped until a restart).

Web:  http://<ip>:8080/plugins/wpasync/
Config:
  main.plugins.wpasync.enabled = true

Own device / your own networks only.
"""

import logging
import pwnagotchi.plugins as plugins

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>wpa-sec sync</title>
<style>
 body{font-family:sans-serif;max-width:520px;margin:24px auto;padding:0 14px}
 a.btn{display:inline-block;background:#2d7;color:#000;text-decoration:none;
       padding:14px 22px;border-radius:10px;font-weight:bold;font-size:18px}
 .msg{margin-top:18px;padding:12px;border-radius:8px;background:#eee;white-space:pre-wrap}
 small{color:#666}
</style></head><body>
<h2>wpa-sec — залить сейчас</h2>
<p>Жми, когда у девайса есть интернет (USB от ПК / телефон). Он заставит
плагин <b>wpa-sec</b> залить новые хэши и скачать взломанные пароли.</p>
<p><a class="btn" href="go">⬆️ Залить на wpa-sec</a></p>
<div class="msg">__MSG__</div>
<p><small>Если «нет интернета» — сначала дай девайсу сеть, потом жми снова.</small></p>
</body></html>"""


class WpaSync(plugins.Plugin):
    __author__ = "you@example.com"
    __version__ = "0.1.0"
    __license__ = "MIT"
    __description__ = "Force the built-in wpa-sec plugin to upload/download now."

    def __init__(self):
        self._agent = None
        self._last = "Готов. Нажми кнопку, когда есть интернет."

    def on_loaded(self):
        logging.info("[wpasync] loaded")

    def on_ready(self, agent):
        self._agent = agent

    # --- helpers ----------------------------------------------------------
    @staticmethod
    def _have_net():
        import socket
        try:
            socket.setdefaulttimeout(3)
            socket.getaddrinfo("wpa-sec.stanev.org", 443)
            return True
        except Exception:
            return False

    def _force(self):
        if self._agent is None:
            return "Агент ещё не готов — подожди минуту после старта."
        wp = plugins.loaded.get("wpa-sec")
        if not wp:
            return "Плагин wpa-sec не загружен (включи main.plugins.wpa-sec.enabled = true)."
        if not getattr(wp, "ready", False):
            return "wpa-sec не готов — проверь api_key в конфиге."
        if not self._have_net():
            return "❌ Нет интернета. Дай девайсу сеть (USB от ПК / телефон) и жми снова."
        try:
            wp.on_internet_available(self._agent)
            return "✅ Отправил сигнал wpa-sec: заливка новых хэшей + скачивание взломанных запущены. Смотри экран/лог."
        except Exception as e:
            logging.exception("[wpasync] force failed")
            return "Ошибка: %s" % e

    # --- web --------------------------------------------------------------
    def on_webhook(self, path, request):
        from flask import make_response
        if path and path.strip("/") == "go":
            self._last = self._force()
        html = PAGE.replace("__MSG__", self._last)
        r = make_response(html)
        r.headers["Content-Type"] = "text/html; charset=utf-8"
        return r
