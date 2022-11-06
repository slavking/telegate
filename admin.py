import json

import config


def setup_admin_commands(telegate):
    bot = telegate.bot
    ignored = telegate.ignored
    members = telegate.members

    @bot.command(r'/ignore (\d+)')
    async def ignore(chat, match):
        if chat.message['from']['id'] not in config.mods:
            return
        post_id = int(match.group(1))
        async with bot.session.get(f'https://{config.url}/data/{config.board}') as s:
            data = await s.json()
            for post_data in data:
                if post_id == post_data['count']:
                    ignored[post_data['identifier']] = 1
                    await chat.reply('Ignored {} {}'.format(post_data['identifier'], post_data['name']))
                    await chat.reply('Ignore: {}'.format(', '.join(ignored.keys())))
                    return
        await chat.reply('Post not found')


    @bot.command('unignore')
    async def unignore(chat, match):
        if chat.message['from']['id'] not in config.mods:
            return
        await chat.reply('Ignore: {}'.format(', '.join(ignored.keys())))
        for k in list(ignored.keys()):
            del ignored[k]
        await chat.reply('Ignore: {}'.format(', '.join(ignored.keys())))


    @bot.command(r'/ban (\d+)')
    async def ban(chat, match):
        if chat.message['from']['id'] not in config.mods:
            return
        post_id = int(match.group(1))
        async with bot.session.post(f'https://{config.url}/ban', data={'password': config.mod_password, 'board': config.board, 'id': post_id}) as s:
            data = await s.json()
            chat.reply(repr(data))


    @bot.command(r'/set_cooldown (\d+)')
    async def set_cooldown(chat, match):
        if chat.message['from']['id'] not in config.mods:
            return
        member = telegate.get_member(chat)
        member.cooldown_limit = int(match.group(1))
        telegate.members[chat.message['from']['id']] = member
        chat.reply(repr(member))


    @bot.command('unban')
    async def unban(chat, match):
        if chat.message['from']['id'] not in config.mods:
            return
        async with bot.session.post(f'https://{config.url}/unban', data={'password': config.mod_password}) as s:
            data = await s.json()
            chat.reply(repr(data))


    # @bot.command('member_data')
    # async def member_data(chat, match):
    #     if chat.message['from']['id'] not in config.mods:
    #         return
    #     buttons = [
    #         {
    #             "type": "KeyboardButton",
    #             "text": "/member_data",
    #             "request_location": True,
    #         }
    #     ]
    #     markup = {
    #         "type": "ReplyKeyboardMarkup",
    #         "keyboard": [buttons],
    #         "one_time_keyboard": True,
    #     }
    #     chat.send_text(repr(members), reply_markup=json.dumps(markup))

