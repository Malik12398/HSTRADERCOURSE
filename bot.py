import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.base import StorageKey
import sqlite3
import openpyxl
from datetime import datetime


# ===== 1. Setup ===== #
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "7771643202:AAFPydfvyOhe0XMSnNi-Z9U1Z78mhJ1Rmko"
ADMIN_ID = 7765768262
GROUP_CHAT_ID = -1002503753145  # Replace with your real group chat ID

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ===== 2. Database ===== #
conn = sqlite3.connect("/mnt/volume/giveaway.db")
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        quotex_id TEXT,
        tiktok TEXT,
        instagram TEXT,
        join_date TIMESTAMP
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS bot_messages (
        key TEXT PRIMARY KEY,
        value TEXT
    )
''')

default_messages = {
    "start": "🎉 *Welcome To HSTrader Giveaway* 🎉\nClick /join to participate!",
    "join_step1": "🔹 *Step 1:* Create Quotex account:\nhttps://market-qx.pro/?lid=817716\nThen send your Quotex ID:",
    "tiktok_prompt": "✅ *Verified!*\n🔹 *Step 2:* \nSend your TikTok username:",
    "instagram_prompt": "✅ *TikTok saved!*\n🔹 *Step 3:* \nSend your Instagram username:",
    "channels_prompt": "🔹 *Final Step:* Join our channels:\n\n1. https://t.me/HSTraderChannel\n\n2. https://t.me/HSforexCommunity\n\n3. https://www.instagram.com/channel/AbY0RSBUEhl9yMET/\n\n4. https://youtube.com/@hstraderyt?si=JTXao4UkrbopWKuA\n\nPress button after joining:",
    "finish_message": "🎉 *All done!* Here's your invite link:"
}


for key, value in default_messages.items():
    cursor.execute("INSERT OR IGNORE INTO bot_messages VALUES (?, ?)", (key, value))
conn.commit()

# ===== 3. States ===== #
class Form(StatesGroup):
    quotex_id = State()
    tiktok = State()
    instagram = State()
    join_channels = State()

class EditMessages(StatesGroup):
    waiting_for_key = State()
    waiting_for_new_message = State()

# ===== 4. Helper Function ===== #
async def get_message(key: str) -> str:
    cursor.execute("SELECT value FROM bot_messages WHERE key = ?", (key,))
    result = cursor.fetchone()
    return result[0] if result else default_messages.get(key, "Message not found.")

# ===== 5. Handlers ===== #
@dp.message(F.text == '/cleardata')
async def clear_excel(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["User ID", "Username", "Quotex ID", "TikTok", "Instagram", "Join Date"])
        wb.save("users.xlsx")
        await message.answer("🧹 Excel file emptied successfully!")
    else:
        await message.answer("❌ Admin only!")

@dp.message(F.text == '/start')
async def start(message: types.Message):
    start_msg = await get_message("start")
    await message.answer(start_msg, parse_mode="Markdown")

@dp.message(F.text == '/join')
async def join(message: types.Message, state: FSMContext):
    step1_msg = await get_message("join_step1")
    await message.answer(step1_msg, parse_mode="Markdown")
    await state.set_state(Form.quotex_id)

@dp.message(Form.quotex_id)
async def quotex_step(message: types.Message, state: FSMContext):
    if not message.from_user.username:
        await message.answer("❗ Please set your Telegram *username* in Telegram settings and try again.", parse_mode="Markdown")
        return

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Accept", callback_data=f"accept_{message.from_user.id}")],
        [types.InlineKeyboardButton(text="❌ Reject", callback_data=f"reject_{message.from_user.id}")]
    ])

    await bot.send_message(
        ADMIN_ID,
        f"🆔 New Quotex ID:\nUser: @{message.from_user.username}\nID: {message.text}",
        reply_markup=keyboard
    )
    await message.answer("⌛ Verification in progress...")
    await state.update_data(quotex_id=message.text)

@dp.callback_query(F.data.startswith(("accept_", "reject_")))
async def verify_quotex(callback: types.CallbackQuery):
    action, user_id = callback.data.split("_")
    user_id = int(user_id)

    user_key = StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id)
    user_state = FSMContext(storage=storage, key=user_key)

    if action == "accept":
        tiktok_msg = await get_message("tiktok_prompt")
        await bot.send_message(user_id, tiktok_msg, parse_mode="Markdown")
        await user_state.set_state(Form.tiktok)
    else:
        await bot.send_message(user_id, "❌ Rejected! Please register using our official link.")
        await user_state.clear()
    await callback.message.delete()
    await callback.answer()

@dp.message(Form.tiktok)
async def tiktok_step(message: types.Message, state: FSMContext):
    await state.update_data(tiktok=message.text)
    instagram_msg = await get_message("instagram_prompt")
    await message.answer(instagram_msg, parse_mode="Markdown")
    await state.set_state(Form.instagram)

@dp.message(Form.instagram)
async def instagram_step(message: types.Message, state: FSMContext):
    await state.update_data(instagram=message.text)
    channels_msg = await get_message("channels_prompt")
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Joined", callback_data="joined")]
    ])
    await message.answer(channels_msg, reply_markup=keyboard, parse_mode="Markdown")
    await state.set_state(Form.join_channels)

@dp.callback_query(F.data == "joined", Form.join_channels)
async def finish(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cursor.execute(
        "INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?, ?, ?)",
        (
            callback.from_user.id,
            callback.from_user.username,
            data.get('quotex_id'),
            data.get('tiktok'),
            data.get('instagram'),
            datetime.now()
        )
    )
    conn.commit()

    # Generate one-time invite link
    invite_link = await bot.create_chat_invite_link(
        chat_id=GROUP_CHAT_ID,
        member_limit=1,
        creates_join_request=False
    )

    finish_msg = await get_message("finish_message")
    await callback.message.answer(f"{finish_msg}\n\n👉 [Click here to join]({invite_link.invite_link})", parse_mode="Markdown", disable_web_page_preview=True)
    await state.clear()
    await callback.answer()

# ===== 6. Edit Messages Feature ===== #
@dp.message(F.text == '/edit_messages')
async def edit_messages_command(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        keyboard = types.InlineKeyboardMarkup()
        cursor.execute("SELECT key FROM bot_messages")
        for row in cursor.fetchall():
            keyboard.add(types.InlineKeyboardButton(text=row[0], callback_data=f"edit_{row[0]}"))
        await message.answer("📝 Select message to edit:", reply_markup=keyboard)
    else:
        await message.answer("❌ Admin only!")

@dp.callback_query(F.data.startswith("edit_"))
async def select_message_to_edit(callback: types.CallbackQuery, state: FSMContext):
    key = callback.data.split("_")[1]
    await state.update_data(edit_key=key)
    await callback.message.answer(f"✏️ Send new text for `{key}`:")
    await state.set_state(EditMessages.waiting_for_new_message)
    await callback.answer()

@dp.message(EditMessages.waiting_for_new_message)
async def save_new_message(message: types.Message, state: FSMContext):
    data = await state.get_data()
    key = data['edit_key']
    cursor.execute("UPDATE bot_messages SET value = ? WHERE key = ?", (message.text, key))
    conn.commit()
    await message.answer(f"✅ Message `{key}` updated!")
    await state.clear()

# ===== 7. Export & Giveaway ===== #
@dp.message(F.text == '/export')
async def export_data(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        cursor.execute("SELECT * FROM users")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["User ID", "Username", "Quotex ID", "TikTok", "Instagram", "Join Date"])
        for row in cursor.fetchall():
            ws.append(row)
        wb.save("users.xlsx")
        await message.reply_document(types.FSInputFile("users.xlsx"))
    else:
        await message.answer("❌ Admin only!")

@dp.message(F.text == '/giveaway')
async def giveaway(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        cursor.execute("SELECT * FROM users")
        all_users = cursor.fetchall()
        if not all_users:
            await message.answer("❌ No participants found.")
            return
        import random
        winner = random.choice(all_users)
        user_id, username, quotex_id, tiktok, instagram, join_date = winner
        try:
            join_date_formatted = datetime.strptime(join_date, '%Y-%m-%d %H:%M:%S.%f').strftime('%Y-%m-%d %H:%M')
        except Exception:
            join_date_formatted = str(join_date)
        await message.answer(
            f"🎉 *Giveaway Winner!*\n\n"
            f"👤 Username: @{username or 'N/A'}\n"
            f"🆔 Quotex ID: {quotex_id}\n"
            f"📱 TikTok: {tiktok}\n"
            f"📸 Instagram: {instagram}\n"
            f"📅 Joined: {join_date_formatted}", parse_mode="Markdown"
        )
    else:
        await message.answer("❌ Admin only!")

# ===== 8. Bot Runner ===== #
if __name__ == '__main__':
    logging.info("Bot starting...")
    dp.run_polling(bot)
