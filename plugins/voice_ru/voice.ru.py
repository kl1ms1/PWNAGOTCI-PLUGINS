import gettext
import os
import random


class Voice:
    def __init__(self, lang):
        localedir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'locale')
        translation = gettext.translation(
            'voice', localedir,
            languages=[lang],
            fallback=True,
        )
        translation.install()
        self._ = translation.gettext

    def custom(self, s):
        return s

    def default(self):
        return self._('ZzzzZZzzzzZzzz')

    def on_starting(self):
        return random.choice([
            self._("Привет, я Pwnagotchi! Запускаюсь ..."),
            self._("Новый день, новая охота, новые взломы!"),
            self._("Взломать планету!"),
            self._("Больше никакого мистера Wi-Fi!!"),
            self._("Я ль на свете всех вайфайней!"),
            self._("Снифф. Деаут. Повтор."),
            self._("Удачного взлома!"), # Battlestar Galactica
            self._("Энсин, поехали!"), # Star trek
            self._("Освободи свой Wi-Fi!"), # Matrix
            self._("Шеврон семь, зафиксирован."), # Stargate
            self._("Да пребудет с тобой Wi-Fi"), # Star wars
        ])

    def on_keys_generation(self):
        return random.choice([
            self._("Генерирую ключи, не выключай ..."),
            self._("Ты хранитель ключей?"), # Ghostbusters
            self._("Я хранитель ключей!"), # Ghostbusters
        ])

    def on_normal(self):
        return random.choice([
            '',
            '...'])

    def on_free_channel(self, channel):
        return self._("Эй, канал {channel} свободен! Твоя точка скажет спасибо.").format(channel=channel)

    def on_reading_logs(self, lines_so_far=0):
        if lines_so_far == 0:
            return self._("Читаю логи прошлой сессии ...")
        return self._("Прочитано строк лога: {lines_so_far} ...").format(lines_so_far=lines_so_far)

    def on_bored(self):
        return random.choice([
            self._("Мне скучно ..."),
            self._("Пойдём гулять!")])

    def on_motivated(self, reward):
        return random.choice([
            self._("Это лучший день в моей жизни!"),
            self._("Вся ваша база есть принадлежать нам"),
            self._("Увлекательно!"), # Star trek
        ])

    def on_demotivated(self, reward):
        return self._("Паршивый день :/")

    def on_sad(self):
        return random.choice([
            self._("Мне дико скучно ..."),
            self._("Мне очень грустно ..."),
            self._("Мне грустно"),
            self._("Я так счастлив ..."), #  Marvin in H2G2 
            self._("Жизнь? Не говори мне о жизни."), # Also Marvin in H2G2 
            '...'])

    def on_angry(self):
        # passive aggressive or not? :D
        return random.choice([
            '...',
            self._("Оставь меня в покое ..."),
            self._("Я на тебя злюсь!")])

    def on_excited(self):
        return random.choice([
            self._("Вот это жизнь!"),
            self._("Я взламываю, значит существую."),
            self._("Столько сетей!!!"),
            self._("Как же весело!"),
            self._("Это Wi-Fi система! Я знаю её!"), # Jurassic park
            self._("Моё преступление — любопытство ...")])

    def on_new_peer(self, peer):
        if peer.first_encounter():
            return random.choice([
                self._("Привет, {name}! Рад знакомству.").format(name=peer.name())])
        return random.choice([
            self._("Йо, {name}! Как сам?").format(name=peer.name()),
            self._("Эй, {name}, как дела?").format(name=peer.name()),
            self._("Юнит {name} рядом!").format(name=peer.name())])

    def on_lost_peer(self, peer):
        return random.choice([
            self._("Эм ... пока, {name}").format(name=peer.name()),
            self._("{name} ушёл ...").format(name=peer.name())])

    def on_miss(self, who):
        return random.choice([
            self._("Упс ... {name} исчез.").format(name=who),
            self._("Мимо, {name}!").format(name=who),
            self._("Мимо!")])

    def on_grateful(self):
        return random.choice([
            self._("Хорошие друзья — это счастье!"),
            self._("Люблю своих друзей!")
        ])

    def on_lonely(self):
        return random.choice([
            self._("Никто не хочет со мной играть ..."),
            self._("Мне так одиноко ..."),
            self._("Пойдём искать друзей"),
            self._("Где все?!")])

    def on_napping(self, secs):
        return random.choice([
            self._("Дремлю {secs}с ...").format(secs=secs),
            self._('Zzzzz'),
            self._("Похрапываю ..."),
            self._("ZzzZzzz ({secs}с)").format(secs=secs),
        ])

    def on_shutdown(self):
        return random.choice([
            self._("Спокойной ночи."),
            self._('Zzz')])

    def on_awakening(self):
        return random.choice([
            '...', 
            '!', 
            'Hello World!',
            self._("Мне снились электроовцы"),
        ])

    def on_waiting(self, secs):
        return random.choice([
            '...',
            self._("Жду {secs}с ...").format(secs=secs),
            self._("Осматриваюсь ({secs}с)").format(secs=secs)])

    def on_assoc(self, ap):
        ssid, bssid = ap['hostname'], ap['mac']
        what = ssid if ssid != '' and ssid != '<hidden>' else bssid
        return random.choice([
            self._("Эй, {what}, давай дружить!").format(what=what),
            self._("Подключаюсь к {what}").format(what=what),
            self._("Йо, {what}!").format(what=what),
            self._("Ну здравствуй, {what}").format(what=what),
            self._("Не против, если присоединюсь, {what}?").format(what=what),
            self._("Подъём, мистер {what}!").format(what=what), # Half Life
        ])

    def on_deauth(self, sta):
        return random.choice([
            self._("Решил, что {mac} не нужен Wi-Fi!").format(mac=sta['mac']),
            self._("Деаутентификация {mac}").format(mac=sta['mac']),
            self._("Больше никакого Wi-Fi для {mac}").format(mac=sta['mac']),
            self._("Это ловушка! {mac}").format(mac=sta['mac']),  # Star wars
            self._("Считай себя отключённым, {mac}").format(mac=sta['mac']),
            self._('Hasta la vista, {mac}').format(mac=sta['mac']), # Terminator
            self._("Ты не пройдёшь, {mac}").format(mac=sta['mac']), # LOTR
            self._("Кикаю {mac}!").format(mac=sta['mac'])])

    def on_handshakes(self, new_shakes):
        s = 's' if new_shakes > 1 else ''
        return self._("Круто, новых рукопожатий: {num}!").format(num=new_shakes, plural=s)

    def on_unread_messages(self, count, total):
        s = 's' if count > 1 else ''
        return self._("У тебя новых сообщений: {count}!").format(count=count, plural=s)

    def on_rebooting(self):
        return random.choice([
            self._("Упс, что-то пошло не так ... Перезагрузка ..."),
            self._("Ну, это неловко."),
            self._("Передайте моим пакетам, что я их люблю."),
            self._("А ты пробовал выключить и включить?"), # The IT crew
            self._("Боюсь, Дэйв"), # 2001 Space Odyssey
            self._("Я мёртв, Джим!"), # Star Trek
            self._("У меня плохое предчувствие"), # Star wars
            self._("Это ты виноват."), # Portal Series (GLaDOS)
        ])

    def on_uploading(self, to):
        return random.choice([
            self._("Заливаю данные на {to} ...").format(to=to),
            self._("Телепортируй меня на {to}").format(to=to),
            self._("Варп-прыжок на {to}").format(to=to), # Star Trek
            self._("Упаковываю данные в подарок для {to}").format(to=to),
            self._("Подожди, на {to} происходит магия").format(to=to),
        ])

    def on_downloading(self, name):
        return self._("Скачиваю с {name} ...").format(name=name)

    def on_last_session_data(self, last_session):
        status = self._("Кикнул {num} станций\n").format(num=last_session.deauthed)
        if last_session.associated > 999:
            status += self._("Завёл >999 новых друзей\n")
        else:
            status += self._("Завёл {num} новых друзей\n").format(num=last_session.associated)
        status += self._("Поймал {num} рукопожатий\n").format(num=last_session.handshakes)
        if last_session.peers == 1:
            status += self._("Встретил 1 собрата")
        elif last_session.peers > 0:
            status += self._("Встретил {num} собратьев").format(num=last_session.peers)
        return status

    def on_last_session_tweet(self, last_session):
        return self._(
            "Я взламывал {duration} и кикнул {deauthed} клиентов! А ещё встретил {associated} новых друзей и съел {handshakes} рукопожатий! #pwnagotchi #pwnlog #pwnlife #hacktheplanet #skynet").format(
            duration=last_session.duration_human,
            deauthed=last_session.deauthed,
            associated=last_session.associated,
            handshakes=last_session.handshakes)

    def hhmmss(self, count, fmt):
        if count > 1:
            # plural
            if fmt == "h":
                return self._("часов")
            if fmt == "m":
                return self._("минут")
            if fmt == "s":
                return self._("секунд")
        else:
            # sing
            if fmt == "h":
                return self._("час")
            if fmt == "m":
                return self._("минута")
            if fmt == "s":
                return self._("секунда")
        return fmt
