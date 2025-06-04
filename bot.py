from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.tl.functions.messages import ExportChatInviteRequest
from telethon.tl.functions.channels import EditBannedRequest
from telethon.tl.types import ChatBannedRights
import asyncio
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")
affiliate_bot = "@AffiliatePocketBot"
group_id = int(os.getenv("GROUP_ID"))
admin_id = int(os.getenv("ADMIN_ID"))

client = TelegramClient(StringSession(), api_id, api_hash).start(bot_token=bot_token)

db = sqlite3.connect("po_users.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    pocket_id TEXT,
    zero_balance_days INTEGER DEFAULT 0
)
""")
db.commit()

@client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    buttons = [
        [Button.inline("Join", b"join_course")]
    ]
    await event.respond(
        "Welcome to HSTrader Free Course!\nIf you want to join then click the Join button.",
        buttons=buttons
    )

@client.on(events.CallbackQuery(pattern=b"join_course"))
async def join_handler(event):
    await event.answer()
    await event.edit(
        "If you want to join this free course then make sure your Pocket Option account is created through our referral link:\n"
        "https://po-ru4.click/register?utm_campaign=820621&utm_source=affiliate&utm_medium=sr&a=XIRNLsVcxXm1M4&ac=freeclasses&code=50START\n"
        "Send your Pocket Option ID for verification."
    )

@client.on(events.NewMessage(pattern='^[0-9]{5,}$'))
async def pocket_id_handler(event):
    user_id = event.sender_id
    pocket_id = event.raw_text.strip()

    cursor.execute("SELECT * FROM users WHERE pocket_id = ?", (pocket_id,))
    duplicate = cursor.fetchone()

    if duplicate:
        await event.respond(f"This Pocket Option ID is already used by user {duplicate[0]}.")
        return

    await event.respond("Verifying your Pocket Option ID...")

    await client.send_message(affiliate_bot, f"/user {pocket_id}")

    try:
        response = await client.wait_for(
            events.NewMessage(from_users=affiliate_bot, incoming=True),
            timeout=10
        )
    except asyncio.TimeoutError:
        await event.respond("No response from affiliate bot. Please try again later.")
        return

    text = response.raw_text.lower()

    if "no user found" in text or "not referred" in text:
        await event.respond("It seems like your account is not created with our link. Kindly use this link again:\n"
                            "https://po-ru4.click/register?utm_campaign=820621&utm_source=affiliate&utm_medium=sr&a=XIRNLsVcxXm1M4&ac=freeclasses&code=50START")
        return

    if "$" in text:
        try:
            balance = float(text.split("$")[-1].split()[0])
        except Exception:
            await event.respond("Could not parse balance. Please try again.")
            return

        if balance < 50:
            await event.respond("It seems your balance does not meet the $50 minimum. Deposit $50 and then send your ID again.")
            return

        cursor.execute("INSERT INTO users (user_id, pocket_id) VALUES (?, ?)", (user_id, pocket_id))
        db.commit()

        invite = await client(ExportChatInviteRequest(group_id))
        await event.respond(f"You're verified! Join the group here: {invite.link}")
        return

@client.on(events.NewMessage(from_users=admin_id, pattern='/export'))
async def export_data(event):
    with open("users_export.csv", "w") as file:
        file.write("user_id,pocket_id,zero_balance_days\n")
        for row in cursor.execute("SELECT * FROM users"):
            file.write(f"{row[0]},{row[1]},{row[2]}\n")
    await client.send_file(admin_id, "users_export.csv")

async def balance_checker():
    while True:
        for row in cursor.execute("SELECT user_id, pocket_id, zero_balance_days FROM users"):
            uid, pid, days = row
            await client.send_message(affiliate_bot, f"/user {pid}")
            try:
                response = await client.wait_for(
                    events.NewMessage(from_users=affiliate_bot, incoming=True),
                    timeout=10
                )
            except asyncio.TimeoutError:
                continue

            text = response.raw_text.lower()

            if "no user found" in text:
                rights = ChatBannedRights(until_date=None, view_messages=True)
                await client(EditBannedRequest(group_id, uid, rights))
                await client.send_message(uid, "You have been removed from the group because your account was deleted or not valid.")
                cursor.execute("DELETE FROM users WHERE user_id = ?", (uid,))
                db.commit()
                continue

            if "$" in text:
                try:
                    balance = float(text.split("$")[-1].split()[0])
                except Exception:
                    continue

                if balance == 0:
                    days += 1
                    if days >= 7:
                        rights = ChatBannedRights(until_date=None, view_messages=True)
                        await client(EditBannedRequest(group_id, uid, rights))
                        await client.send_message(uid, "You were removed from the group due to 7 consecutive days of zero balance.")
                        cursor.execute("DELETE FROM users WHERE user_id = ?", (uid,))
                    else:
                        await client.send_message(uid, f"Your balance is $0. Kindly deposit again to stay in the group. Day {days}/7")
                        cursor.execute("UPDATE users SET zero_balance_days = ? WHERE user_id = ?", (days, uid))
                else:
                    cursor.execute("UPDATE users SET zero_balance_days = 0 WHERE user_id = ?", (uid,))

                db.commit()
        await asyncio.sleep(86400)

async def main():
    print("Bot is running...")
    await balance_checker()

client.loop.create_task(main())
client.run_until_disconnected()
