"""
voice_ru — translates ALL of pwnagotchi's spoken phrases to Russian.

Instead of editing voice.py on disk (which pwnagotchi updates overwrite), this
plugin swaps the translator used inside Voice: every phrase goes through
`self._(english)`, so we replace `self._` with a lookup into a Russian dictionary.
One dict covers all ~25 phrase methods — no method is reimplemented.

It patches both:
  • Voice.__init__  — so any Voice created after load speaks Russian;
  • the live view's Voice instance (on_ui_setup) — so the already-running one does too.

Unknown strings fall back to the original English, so a pwnagotchi update that adds
a new phrase simply shows it in English until this dict is extended — nothing breaks.

Note: callout (if enabled) still overrides the deauth phrase on top of this.
"""

import logging

import pwnagotchi.plugins as plugins

# English source string -> Russian. Keys must match voice.py EXACTLY (placeholders
# like {mac}/{secs}/{num} and trailing \n are kept so .format() still works).
RU = {
    # default / sounds are left as-is (not listed) -> fall back to English.

    # on_starting
    "Hi, I'm Pwnagotchi! Starting ...": "Привет, я Pwnagotchi! Запускаюсь ...",
    "New day, new hunt, new pwns!": "Новый день, новая охота, новые взломы!",
    "Hack the Planet!": "Взломать планету!",
    "No more mister Wi-Fi!!": "Больше никакого мистера Wi-Fi!!",
    "Pretty fly 4 a Wi-Fi!": "Я ль на свете всех вайфайней!",
    "Sniff. Deauth. Repeat.": "Снифф. Деаут. Повтор.",
    "Good Pwning!": "Удачного взлома!",
    "Ensign, Engage!": "Энсин, поехали!",
    "Free your Wi-Fi!": "Освободи свой Wi-Fi!",
    "Chevron Seven, locked.": "Шеврон семь, зафиксирован.",
    "May the Wi-fi be with you": "Да пребудет с тобой Wi-Fi",

    # on_keys_generation
    "Generating keys, do not turn off ...": "Генерирую ключи, не выключай ...",
    "Are you the keymaster?": "Ты хранитель ключей?",
    "I am the keymaster!": "Я хранитель ключей!",

    # on_free_channel
    "Hey, channel {channel} is free! Your AP will say thanks.":
        "Эй, канал {channel} свободен! Твоя точка скажет спасибо.",

    # on_reading_logs
    "Reading last session logs ...": "Читаю логи прошлой сессии ...",
    "Read {lines_so_far} log lines so far ...": "Прочитано строк лога: {lines_so_far} ...",

    # on_bored
    "I'm bored ...": "Мне скучно ...",
    "Let's go for a walk!": "Пойдём гулять!",

    # on_motivated
    "This is the best day of my life!": "Это лучший день в моей жизни!",
    "All your base are belong to us": "Вся ваша база есть принадлежать нам",
    "Fascinating!": "Увлекательно!",

    # on_demotivated
    "Shitty day :/": "Паршивый день :/",

    # on_sad
    "I'm extremely bored ...": "Мне дико скучно ...",
    "I'm very sad ...": "Мне очень грустно ...",
    "I'm sad": "Мне грустно",
    "I'm so happy ...": "Я так счастлив ...",
    "Life? Don't talk to me about life.": "Жизнь? Не говори мне о жизни.",

    # on_angry
    "Leave me alone ...": "Оставь меня в покое ...",
    "I'm mad at you!": "Я на тебя злюсь!",

    # on_excited
    "I'm living the life!": "Вот это жизнь!",
    "I pwn therefore I am.": "Я взламываю, значит существую.",
    "So many networks!!!": "Столько сетей!!!",
    "I'm having so much fun!": "Как же весело!",
    "It's a Wi-Fi system! I know this!": "Это Wi-Fi система! Я знаю её!",
    "My crime is that of curiosity ...": "Моё преступление — любопытство ...",

    # on_new_peer
    "Hello {name}! Nice to meet you.": "Привет, {name}! Рад знакомству.",
    "Yo {name}! Sup?": "Йо, {name}! Как сам?",
    "Hey {name} how are you doing?": "Эй, {name}, как дела?",
    "Unit {name} is nearby!": "Юнит {name} рядом!",

    # on_lost_peer
    "Uhm ... goodbye {name}": "Эм ... пока, {name}",
    "{name} is gone ...": "{name} ушёл ...",

    # on_miss
    "Whoops ... {name} is gone.": "Упс ... {name} исчез.",
    "{name} missed!": "Мимо, {name}!",
    "Missed!": "Мимо!",

    # on_grateful
    "Good friends are a blessing!": "Хорошие друзья — это счастье!",
    "I love my friends!": "Люблю своих друзей!",

    # on_lonely
    "Nobody wants to play with me ...": "Никто не хочет со мной играть ...",
    "I feel so alone ...": "Мне так одиноко ...",
    "Let's find friends": "Пойдём искать друзей",
    "Where's everybody?!": "Где все?!",

    # on_napping
    "Napping for {secs}s ...": "Дремлю {secs}с ...",
    "Snoring ...": "Похрапываю ...",
    "ZzzZzzz ({secs}s)": "ZzzZzzz ({secs}с)",

    # on_shutdown
    "Good night.": "Спокойной ночи.",

    # on_awakening
    "I dreamed of electric sheep": "Мне снились электроовцы",

    # on_waiting
    "Waiting for {secs}s ...": "Жду {secs}с ...",
    "Looking around ({secs}s)": "Осматриваюсь ({secs}с)",

    # on_assoc
    "Hey {what} let's be friends!": "Эй, {what}, давай дружить!",
    "Associating to {what}": "Подключаюсь к {what}",
    "Yo {what}!": "Йо, {what}!",
    "Hello there, {what}": "Ну здравствуй, {what}",
    "Mind if I join, {what}?": "Не против, если присоединюсь, {what}?",
    "Rise and Shine Mr. {what}!": "Подъём, мистер {what}!",

    # on_deauth (callout may override this on top)
    "Just decided that {mac} needs no Wi-Fi!": "Решил, что {mac} не нужен Wi-Fi!",
    "Deauthenticating {mac}": "Деаутентификация {mac}",
    "No more Wi-Fi for {mac}": "Больше никакого Wi-Fi для {mac}",
    "It's a trap! {mac}": "Это ловушка! {mac}",
    "Consider yourself unplugged, {mac}": "Считай себя отключённым, {mac}",
    "Hasta la vista, {mac}": "Hasta la vista, {mac}",
    "You shall not pass, {mac}": "Ты не пройдёшь, {mac}",
    "Kickbanning {mac}!": "Кикаю {mac}!",

    # on_handshakes ({plural} is ignored in RU)
    "Cool, we got {num} new handshake{plural}!": "Круто, новых рукопожатий: {num}!",

    # on_unread_messages
    "You have {count} new message{plural}!": "У тебя новых сообщений: {count}!",

    # on_rebooting
    "Oops, something went wrong ... Rebooting ...": "Упс, что-то пошло не так ... Перезагрузка ...",
    "Well, this is awkward.": "Ну, это неловко.",
    "Tell my packets I love them.": "Передайте моим пакетам, что я их люблю.",
    "Have you tried turning it off and on again?": "А ты пробовал выключить и включить?",
    "I'm afraid Dave": "Боюсь, Дэйв",
    "I'm dead, Jim!": "Я мёртв, Джим!",
    "I have a bad feeling about this": "У меня плохое предчувствие",
    "You did this.": "Это ты виноват.",

    # on_uploading
    "Uploading data to {to} ...": "Заливаю данные на {to} ...",
    "Beam me up to {to}": "Телепортируй меня на {to}",
    "Engage warp drive, {to}": "Варп-прыжок на {to}",
    "Gift-wrapping data for {to}": "Упаковываю данные в подарок для {to}",
    "Please wait, magic happening at {to}": "Подожди, на {to} происходит магия",

    # on_downloading
    "Downloading from {name} ...": "Скачиваю с {name} ...",

    # on_last_session_data
    "Kicked {num} stations\n": "Кикнул {num} станций\n",
    "Made >999 new friends\n": "Завёл >999 новых друзей\n",
    "Made {num} new friends\n": "Завёл {num} новых друзей\n",
    "Got {num} handshakes\n": "Поймал {num} рукопожатий\n",
    "Met 1 peer": "Встретил 1 собрата",
    "Met {num} peers": "Встретил {num} собратьев",

    # on_last_session_tweet
    "I've been pwning for {duration} and kicked {deauthed} clients! I've also met {associated} new friends and ate {handshakes} handshakes! #pwnagotchi #pwnlog #pwnlife #hacktheplanet #skynet":
        "Я взламывал {duration} и кикнул {deauthed} клиентов! А ещё встретил {associated} новых друзей и съел {handshakes} рукопожатий! #pwnagotchi #pwnlog #pwnlife #hacktheplanet #skynet",

    # hhmmss
    "hours": "часов", "minutes": "минут", "seconds": "секунд",
    "hour": "час", "minute": "минута", "second": "секунда",
}


def _translate(s):
    return RU.get(s, s)


class VoiceRu(plugins.Plugin):
    __author__ = "you@example.com"
    __version__ = "1.0.0"
    __license__ = "MIT"
    __description__ = "Translates all of pwnagotchi's spoken phrases to Russian (in memory)."

    def on_loaded(self):
        try:
            import pwnagotchi.voice as voice
            if not hasattr(voice.Voice, "_ru_orig_init"):
                voice.Voice._ru_orig_init = voice.Voice.__init__

            def _patched_init(vself, lang):
                voice.Voice._ru_orig_init(vself, lang)
                vself._ = _translate          # override the translator with the RU dict

            voice.Voice.__init__ = _patched_init
            logging.info("[voice_ru] loaded (%d phrases)", len(RU))
        except Exception:
            logging.exception("[voice_ru] could not patch Voice")

    # patch the already-running Voice instance held by the view
    def on_ui_setup(self, ui):
        try:
            v = getattr(ui, "_voice", None)
            if v is not None:
                v._ = _translate
        except Exception:
            pass

    def on_unload(self, ui):
        try:
            import pwnagotchi.voice as voice
            if hasattr(voice.Voice, "_ru_orig_init"):
                voice.Voice.__init__ = voice.Voice._ru_orig_init
            v = getattr(ui, "_voice", None)
            if v is not None and hasattr(v, "_ru_orig_init"):
                pass  # instance keeps RU until restart; harmless
        except Exception:
            pass
