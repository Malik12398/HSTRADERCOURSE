import sys
import sqlite3
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from config import API_ID, API_HASH, BOT_TOKEN, PO_BOT_USERNAME

# SQLite Database Setup
conn = sqlite3.connect("po_users.db")
cursor = conn.cursor()

# Create Table (if not exists)
cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                tg_username TEXT,
                po_id TEXT PRIMARY KEY,
                balance REAL,
                zero_warnings INTEGER)''')
conn.commit()

# Telethon Client (Bot ke liye)
client = TelegramClient(StringSession(), API_ID, API_HASH).start(bot_token=BOT_TOKEN)

async def check_po_user(po_id):
    """Pocket Option bot se user check kare"""
    async with client.conversation(PO_BOT_USERNAME) as conv:
        await conv.send_message(f"/user {po_id}")
        response = await conv.get_response()
        return response.text

def parse_po_response(text):
    """Response se balance/link extract kare"""
    data = {"balance": 0.0, "valid": False}
    if "Balance: $" in text:
        data["balance"] = float(text.split("Balance: $")[1].split()[0])
    if "Link: https://u3.shortink.io/register" in text:  # Your REF link
        data["valid"] = True
    return data

# Start Command
@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.reply('''Welcome! Send your Pocket Option ID to verify.''')

# PO ID Check
@client.on(events.NewMessage)
async def verify(event):
    if event.text.isdigit():  # PO ID
        po_id = event.text
        tg_username = event.sender.username
        
        # Check if PO ID already used
        cursor.execute("SELECT * FROM users WHERE po_id=?", (po_id,))
        if cursor.fetchone():
            await event.reply("❌ This ID is already used!")
            return
        
        # Verify via PO Bot
        response = await check_po_user(po_id)
        user_data = parse_po_response(response)
        
        if not user_data["valid"]:
            await event.reply("❌ Not registered via our link!\nUse: [REF_LINK]")
        elif user_data["balance"] < 50:
            await event.reply(f"⚠️ Required: $50 (Your Balance: ${user_data['balance']})")
        else:
            cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?)", 
                          (tg_username, po_id, user_data["balance"], 0))
            conn.commit()
            await event.reply("✅ Verified! Group Link: [LINK]")

# Daily Check (24h)
async def daily_check():
    cursor.execute("SELECT * FROM users")
    for user in cursor.fetchall():
        tg_username, po_id, balance, warnings = user
        response = await check_po_user(po_id)
        user_data = parse_po_response(response)
        
        if not user_data["valid"]:
            await client.kick_participant(GROUP_ID, tg_username)
            await client.send_message(tg_username, "🚫 Removed: Invalid account!")
        elif user_data["balance"] == 0:
            warnings += 1
            if warnings >= 7:
                await client.kick_participant(GROUP_ID, tg_username)
                await client.send_message(tg_username, "🚫 Removed: 7 days zero balance!")
            else:
                cursor.execute("UPDATE users SET zero_warnings=? WHERE po_id=?", (warnings, po_id))
                await client.send_message(tg_username, f"⚠️ Warning {warnings}/7: Deposit ASAP!")

# Check if script is run for daily check
if "--daily-check" in sys.argv:
    import asyncio
    asyncio.run(daily_check())
    sys.exit(0)


# Run Bot
client.start()
client.run_until_disconnected()
