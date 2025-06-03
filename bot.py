from telethon.sync import TelegramClient, events
from telethon.sessions import StringSession
import sqlite3
import os
from dotenv import load_dotenv

# Load environment variables from .env (for local testing only)
load_dotenv()

# Get sensitive values from environment
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")
affiliate_bot = "@AffiliatePocketBot"
group_id = int(os.getenv("GROUP_ID"))  # e.g., -1002655615295
admin_id = int(os.getenv("ADMIN_ID"))  # e.g., 7765768262

# Create a Telethon client using bot token (no login/input required)
client = TelegramClient(StringSession(), api_id, api_hash).start(bot_token=bot_token)

# Connect to SQLite DB
db = sqlite3.connect("po_users.db")  # ✅ Your DB file name as discussed
cursor = db.cursor()

# Create users table if not exists
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
        [event.button.text("Join", resize=True)]
    ]
    await event.respond(
        "Welcome to HSTrader Free Course!\nIf you want to join then click the Join button.",
        buttons=buttons
    )

@client.on(events.NewMessage(pattern='Join'))
async def join_handler(event):
    await event.respond(
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
    await asyncio.sleep(5)
    async for msg in client.iter_messages(affiliate_bot, limit=1):
        if "No user found" in msg.text or "not referred" in msg.text:
            await event.respond("It seems like your account is not created with our link. Kindly use this link again:\n"
                                "https://po-ru4.click/register?utm_campaign=820621&utm_source=affiliate&utm_medium=sr&a=XIRNLsVcxXm1M4&ac=freeclasses&code=50START")
            return
        if "$" in msg.text:
            balance = float(msg.text.split("$")[-1].split()[0])
            if balance < 50:
                await event.respond("It seems your balance does not meet the $50 minimum. Deposit $50 and then send your ID again.")
                return
            cursor.execute("INSERT INTO users (user_id, pocket_id) VALUES (?, ?)", (user_id, pocket_id))
            db.commit()
            invite = await client(functions.messages.ExportChatInviteRequest(group_id))
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
            await asyncio.sleep(3)
            async for msg in client.iter_messages(affiliate_bot, limit=1):
                if "No user found" in msg.text:
                    await client.kick_participant(group_id, uid)
                    await client.send_message(uid, "You have been removed from the group because your account was deleted or not valid.")
                    continue
                if "$" in msg.text:
                    balance = float(msg.text.split("$")[-1].split()[0])
                    if balance == 0:
                        days += 1
                        if days >= 7:
                            await client.kick_participant(group_id, uid)
                            await client.send_message(uid, "You were removed from the group due to 7 consecutive days of zero balance.")
                            cursor.execute("DELETE FROM users WHERE user_id = ?", (uid,))
                        else:
                            await client.send_message(uid, f"Your balance is $0. Kindly deposit again to stay in the group. Day {days}/7")
                            cursor.execute("UPDATE users SET zero_balance_days = ? WHERE user_id = ?", (days, uid))
                    else:
                        cursor.execute("UPDATE users SET zero_balance_days = 0 WHERE user_id = ?", (uid,))
            db.commit()
        await asyncio.sleep(86400)  # 24 hours

async def main():
    await client.start(bot_token=bot_token)
    print("Bot is running...")
    await balance_checker()

with client:
    client.loop.run_until_complete(main())
