import subprocess
import requests
import tempfile

import config
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from outline_vpn.outline_vpn import OutlineVPN # type: ignore

client = OutlineVPN(
    api_url="https://46.151.31.207:34962/Tga-GXHdr3y1ipdxPmEy5w",
    cert_sha256=config.OUTLINE_CERT,
)

bot = telebot.TeleBot(config.TOKEN)


def gen_markup():
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(
        InlineKeyboardButton("Получить OpenVPN конфиг", callback_data="cb_openvpn"),
        InlineKeyboardButton("Получить Outline конфиг", callback_data="cb_outline"),
        InlineKeyboardButton("Получить Telegram Proxy", callback_data="cb_telegram"),
    )
    return markup


@bot.callback_query_handler(func=lambda message: True)
def callback_query(message):
    if message.data in ["cb_openvpn", "cb_outline", "cb_telegram"]:
        globals()[message.data](message)
    elif "cb_openvpn_location_" in message.data:
        type, location = message.data.rsplit('_', 1)
        print(type, location)
        globals()['cb_openvpn_location'](message, location)
    else:
        pass

    bot.answer_callback_query(callback_query_id=message.id, show_alert=False)


@bot.message_handler(commands=["start"])
def message_handler(message):
    bot.send_message(message.chat.id, config.WELCOME_MESSAGE, reply_markup=gen_markup())


@bot.message_handler(commands=["restart"])
def message_handler():
    subprocess.run(["../openvpn_restart.sh"])


def cb_openvpn(message):
    
    buttons = []
    markup = InlineKeyboardMarkup()
    for code, server in config.OPENVPN_SERVERS.items():
        buttons.append(InlineKeyboardButton(server['name'], callback_data=f'cb_openvpn_location_{code}'))

    markup.add(*buttons)

    bot.send_message(
        message.from_user.id, "Выберите локацию", reply_markup=markup
    )


def cb_openvpn_location(message, location):

    bot.answer_callback_query(callback_query_id=message.id, text='Генерируем конфиг...')
    
    server_info = config.OPENVPN_SERVERS[location]

    if server_info['server'] == 'local':
        subprocess.run(
            ["./openvpn-install.sh", "1", str(message.from_user.id)],
            cwd=config.FOLDER,
        )
        print(str(message.from_user.id))
        file_to_send = open(
            f"{config.FOLDER}/vpnconfig/{str(message.from_user.id)}.ovpn", "rb"
        )
        print(type(file_to_send))
        bot.send_message(
            message.from_user.id, config.OPENVPN_MESSAGE, disable_web_page_preview=True
        )
        bot.send_document(message.from_user.id, file_to_send)
        file_to_send.close()
    
    else:
        r = requests.get(
            f'http://{server_info["server"]}/get_config',
            params={
                "user_id": str(message.from_user.id)
            },
            headers={
                "secret": server_info['secret'],
            }
        )

        if r.status_code != 200:
            bot.send_message(
                message.from_user.id, 'Не удалось получить конфиг. Попробуйте позже', disable_web_page_preview=True
            )

        with tempfile.NamedTemporaryFile(delete=True) as file:
            file.write(r.text.encode('utf-8'))
            file.seek(0)
            bot.send_message(
                message.from_user.id, config.OPENVPN_MESSAGE, disable_web_page_preview=True
            )
            bot.send_document(message.from_user.id, file, visible_file_name=f'{message.from_user.id}_{location}.ovpn')
            file.close()



def cb_outline(message):
    for clients in client.get_keys():
        if clients.name == str(message.from_user.id):
            bot.send_message(
                message.from_user.id,
                config.OUTLINE_MESSAGE,
                disable_web_page_preview=True,
            )
            bot.send_message(
                message.from_user.id,
                f"```{clients.access_url}```",
                parse_mode="Markdown",
            )
            bot.answer_callback_query(callback_query_id=message.id, show_alert=False)
            return

    new_key = client.create_key(str(message.from_user.id))
    bot.send_message(
        message.from_user.id, config.OUTLINE_MESSAGE, disable_web_page_preview=True
    )
    bot.send_message(
        message.from_user.id, f"```{new_key.access_url}```", parse_mode="Markdown"
    )


def cb_telegram(message):
    bot.send_message(message.from_user.id, config.TELEGRAM_MESSAGE)


print("Starting bot...")
bot.infinity_polling()
