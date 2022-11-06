import os, re, traceback, json
from collections import defaultdict, namedtuple
from time import time
import asyncio
from aiotg import Bot, Chat

import config
import emoji_flags
from persistent import PickleDict
from admin import setup_admin_commands


class Member(object):
    def __init__(self, name, trip, country, cooldown_limit):
        self.name = name
        self.trip = trip
        self.country = country
        self.cooldown_limit = cooldown_limit

    def __iter__(self):
        return iter([self.name, self.trip, self.country, self.cooldown_limit])

    def __repr__(self):
        return repr(self.__dict__)


class TeleGate(object):
    def __init__(self):
        self.ids = PickleDict('ids')
        self.members = PickleDict('members')
        self.ignored = PickleDict('ignored')
        self.cooldown = defaultdict(lambda: 0)
        self.dialogs = {}
        self.tripmap = {}
        self.bot = Bot(api_token=config.token, default_in_groups=True)
        for content_type in ['photo', 'video', 'audio', 'voice', 'document', 'sticker']:
            self.bot.handle(content_type)(self.handle_chat)
        self.bot.default(self.handle_chat)
        # self.bot.command(r'/set(icon|name|region|cooldown) (.+)')(self.set_user_prefs)
        # self.bot.command('help')(self.help)
        #self.bot.command('setup')(self.setup)
        self.bot.command('initiate')(self.setup)
        self.bot.callback(r"setup-(\w+)")(self.setup_button_clicked)

    async def get_trip_flags(self):
        async with self.bot.session.get(f'https://{config.url}/js/tripflags.js') as s:
            data = await s.text()
            for l in data.splitlines():
                if l.startswith('flags_hover_strings'):
                    self.tripmap[l.split('"')[1]] = l.split('"')[3]

    async def post(self, body, name="Anonymous", convo="General", trip="", file="", country=None):
        if trip:
            name = '{}#{}'.format(name, trip)
        data = {
            'chat': config.board,
            'name': name,
            'trip': trip or '',
            'body': body,
            'convo': convo,
        }
        if country:
            data['country'] = country
        if file:
            data['image'] = open(file, 'rb')
        await self.bot.session.post(
                f'https://{config.url}/chat/{config.board}',
                data=data, cookies={'password_livechan': config.password_livechan}
            )

    async def get_posts(self, last_count=0, limit=30):
        params = {'count': last_count, 'limit': limit}
        async with self.bot.session.get(f'https://{config.url}/last/{config.board}', params=params) as s:
            data = await s.json()
            data.reverse()
            return data

    def send_gif(self, chat, animation, caption="", **options):
        return self.bot.api_call(
            "sendAnimation",
            chat_id=str(chat.id),
            animation=animation,
            caption=caption,
            **options
        )

    def get_member(self, chat):
        default = Member(chat.message['from']['first_name'], config.default_trip, None, config.default_cooldown)
        return Member(*self.members.get(chat.message['from']['id'], default))

    async def updater(self):
        last_count = 0
        post_data = {'count': 0}
        while True:
            try:
                await asyncio.sleep(config.poll_interval)
                group = self.bot.group(config.group_id)
                data = await self.get_posts(last_count)
                for post_data in data:
                    if post_data['identifier'] in self.ignored:
                        continue
                    if post_data['convo'] == 'General' and post_data['count'] not in self.ids:
                        res = None
                        country2 = emoji_flags.get_flag(post_data['country'].split('-')[0])
                        if '-' in post_data['country']:
                            country2 = '{}-{}'.format(country2, post_data['country'].split('-')[1])
                        body = '{} {} {} {}:\n{}'.format(post_data['count'], post_data['name'],
                                                         self.tripmap.get(post_data.get('trip'), ''), country2,
                                                         post_data['body'])
                        image = post_data.get('image')
                        reply_to = self.ids.get(int(post_data['body'].lstrip('>').split()[0]) if post_data['body'].startswith('>>') else None)
                        reply_to = {'reply_to_message_id':str(reply_to)} if reply_to else {}
                        if image:
                            image = 'https://{}{}'.format(config.url, image.split('public', 1)[1])
                            filename = image.split('/')[-1]
                            body = body[:1024]
                            async with self.bot.session.get(image) as f:
                                if f.status == 200:
                                    data = await f.read()
                                    with open('tmp/{}'.format(filename), 'wb') as f:
                                        f.write(data)
                                else:
                                    data = None
                            if data:
                                with open('tmp/{}'.format(filename), 'rb') as f:
                                    ext = os.path.splitext(image)[1]
                                    if ext in ['.png', '.jpg']:
                                        res = await group.send_photo(f, caption=body, **reply_to)
                                    elif ext in ['.gif']:
                                        res = await self.send_gif(group, f, caption=body, **reply_to)

                                    elif ext in ['.mp4']:
                                        res = await group.send_video(f, caption=body, **reply_to)
                                    elif ext in ['.mp3', '.ogg']:
                                        res = await group.send_audio(f, caption=body)
                                    elif ext == '.webm':
                                        body += f'\nhttps://{config.url}/tmp/uploads/' + filename
                                        res = await group.send_text(body, **reply_to)
                                os.unlink('tmp/{}'.format(filename))
                            else:
                                res = await group.send_text(body, **reply_to)
                        elif post_data['body']:
                            res = await group.send_text(body, **reply_to)

                        for st in re.findall(r'\[st\]([\w\d\-\.]+)\[\/st\]', body):
                            path = 'stickers/{}.png'.format(st)
                            if not os.path.exists(path):
                                async with self.bot.session.get(f'https://{config.url}/images/stickers/{st}.png') as f:
                                    if f.status == 200:
                                        data = await f.read()
                                        with open(path, 'wb') as f:
                                            f.write(data)
                                        with open(path, 'rb') as f:
                                            res2 = await group.send_photo(f)
                                            if not res:
                                                res = res2
                        if res:
                            self.ids[post_data['count']] = res['result']['message_id']
                            self.ids[res['result']['message_id']] = post_data['count']
            except Exception as e:
                traceback.print_exc()
            last_count = post_data['count']

    async def handle_chat(self, chat, image):
        if not chat.is_group():
            if chat.message['from']['id'] in self.dialogs:
                await self.setup(chat, image)
            return
        else:
            if chat.message['from']['id'] not in self.members:
                await self.setup(chat, image)
        if type(image) == list:
            image = image[-1]
        if 'file_id' in image:
            cq = chat.message
            text = chat.message.get('caption', '')
        else:
            cq = image
            text = cq['text']
        if 'reply_to_message' in cq:
            id = cq['reply_to_message']['message_id']
            if id in self.ids:
                text = '>>{}\n{}'.format(self.ids[id], text)
        id = image.get('file_id')
        if id:
            info = await self.bot.get_file(id)

            path = 'tmp/{}'.format(info['file_path'].split('/')[-1])
            if path.endswith('.oga'): path = path.replace('.oga', '.ogg')
            async with self.bot.download_file(info['file_path']) as res:
                data = await res.read()
                open(path, 'wb').write(data)
            if path.endswith('.webp'):
                newpath = path.replace('.webp', '.png')
                os.system('convert {} {}'.format(path, newpath))
                path = newpath
            elif path.endswith('.tgs'):
                newpath = 'stickers/{}.gif'.format(image['file_id'])
                if not os.path.exists(newpath):
                    import lottie as tgs
                    from lottie.exporters import gif
                    a=tgs.parsers.tgs.parse_tgs(path)

                    with open(newpath, 'wb') as f:
                        gif.export_gif(a, f)
                os.unlink(path)
                path = newpath
        else:
            path = None
        member = self.get_member(chat)
        if not (time() > self.cooldown[cq['from']['id']] + member.cooldown_limit):
            return
        self.cooldown[cq['from']['id']] = time()
        await self.post(text, name=member.name, trip=member.trip, country=member.country, file=path)
        if path and path.startswith('tmp/'):
            os.unlink(path)
        await chat.delete_message(cq['message_id'])

    # async def set_user_prefs(self, chat, match):
    #     member = self.get_member(chat)
    #     setattr(member, {'name': 'name', 'icon': 'trip', 'region': 'country', 'cooldown': 'cooldown_limit'}[match.group(1)], match.group(2))
    #     if member.trip == 'none':
    #         member.trip = None
    #     if isinstance(member.cooldown_limit, str):
    #         member.cooldown_limit = int(member.cooldown_limit if member.cooldown_limit.isnumeric() else config.default_cooldown)
    #     self.members[chat.message['from']['id']] = member
    #
    # async def help(self, chat, match):
    #     group = self.bot.group(config.group_id)
    #     chat_data = await group.get_chat()
    #     link = chat_data['result'].get('invite_link')
    #     if not link:
    #         await self.bot.api_call("exportChatInviteLink", chat_id=config.group_id)
    #         chat_data = await self.bot.api_call("getChat", chat_id=config.group_id)
    #         link = chat_data['result'].get('invite_link', '')
    #     await chat.reply('''/setup - set name/icon/region
    #     Invite link {}
    #     '''.format(link))
    #     await self.bot.session.get(f'https://map.{config.url}/telegate', params={'link': link})

    async def setup(self, chat, match):
        member = self.get_member(chat)
        id = chat.message['from']['id']
        if chat.is_group():
            chat = self.bot.private(chat.message['from']['id'])
        if id in self.dialogs:
            setattr(member, {'name': 'name', 'icon': 'trip', 'region': 'country'}[self.dialogs[id]], chat.message['text'])
            if member.trip == 'none':
                member.trip = None
            self.members[chat.message['from']['id']] = member
            del self.dialogs[id]

        buttons = []
        for button in ['name', 'icon', 'region']:
            buttons.append({
                "type": "InlineKeyboardButton",
                "text": "Set {}".format(button),
                "callback_data": "setup-{}".format(button),
            })
        markup = {
            "type": "InlineKeyboardMarkup",
            "inline_keyboard": [buttons]
        }
        chat.send_text(f"Name: {member.name}\nIcon: {member.trip}\nRegion: {member.country}", reply_markup=json.dumps(markup))

    def setup_button_clicked(self, chat, cq, match):
        if chat.is_group():
            chat = self.bot.private(chat.message['from']['id'])
        id = chat.message['chat']['id']
        param = match.group(1)
        self.dialogs[id] = param
        example = {
            'name': 'Kot',
            'icon': 'plkot; none for no icon',
            'region': 'PL-77 or RU-47',
        }[param]
        chat.send_text('Send your {}(for example: {})'.format(param, example))

    def run(self):
        loop = asyncio.get_event_loop()
        loop.create_task(self.updater())
        loop.create_task(self.get_trip_flags())
        self.bot.run()


if __name__ == '__main__':
    telegate = TeleGate()
    setup_admin_commands(telegate)

    telegate.run()
