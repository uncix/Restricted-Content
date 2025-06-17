import os, re, asyncio
from pyrogram import Client, filters, idle
from pyrogram.types import Message
from pyrogram.errors import FloodWait, BadRequest 

# Bot configuration - Replace with your actual credentials
API_ID = "12380656"  # Get from my.telegram.org
API_HASH = "d927c13beaaf5110f25c505b7c071273"  # Get from my.telegram.org
BOT_TOKEN = "7149816130:AAGXHwA8hHaPC0hp5yxaltC9uAZ6qr_0iuo"  # Get from @BotFather

# Initialize the bot
app = Client("forward_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Command handler for /start
@app.on_message(filters.command("start") & (filters.private | filters.group))
async def start(client: Client, message: Message):
    await message.reply_text(
        "Hello! I'm a message forwarder bot. Use /forward <message-link> to forward restricted messages from public channels.\n"
        "Example: /forward https://t.me/channel/123"
    )

# Command handler for /forward
@app.on_message(filters.command("forward") & (filters.private | filters.group))
async def forward_message(client: Client, message: Message):
    try:
        # Check if message link is provided
        if len(message.command) < 2:
            await message.reply_text("Please provide a message link!\nExample: /forward https://t.me/channel/123")
            return

        # Extract the message link
        msg_link = message.command[1]
        
        # Parse the message link
        link_pattern = r"https?://t\.me/(\w+)/(\d+)"
        match = re.match(link_pattern, msg_link)
        
        if not match:
            await message.reply_text("Invalid message link format! Use: https://t.me/channel/message_id")
            return

        channel_username = match.group(1)
        message_id = int(match.group(2))

        # Resolve channel username to chat_id
        try:
            chat = await client.get_chat(f"@{channel_username}")
            chat_id = chat.id
        except BadRequest as e:
            await message.reply_text(f"Error accessing channel: {str(e)}")
            return

        # Attempt to fetch and forward the message
        try:
            msg = await client.get_messages(chat_id, message_id)
            
            if not msg:
                await message.reply_text("Could not find the message!")
                return

            # Forward the message based on its type
            if msg.text:
                await message.reply_text(msg.text, disable_web_page_preview=True)
            elif msg.photo:
                await message.reply_photo(
                    photo=msg.photo.file_id,
                    caption=msg.caption if msg.caption else ""
                )
            elif msg.video:
                await message.reply_video(
                    video=msg.video.file_id,
                    caption=msg.caption if msg.caption else ""
                )
            elif msg.document:
                await message.reply_document(
                    document=msg.document.file_id,
                    caption=msg.caption if msg.caption else ""
                )
            elif msg.audio:
                await message.reply_audio(
                    audio=msg.audio.file_id,
                    caption=msg.caption if msg.caption else ""
                )
            else:
                await message.reply_text("Unsupported message type!")
                
        except FloodWait as e:
            await message.reply_text(f"Flood wait: Please wait {e.x} seconds")
            await asyncio.sleep(e.x)
        except BadRequest as e:
            await message.reply_text(f"Error forwarding message: {str(e)}")
            
    except Exception as e:
        await message.reply_text(f"An unexpected error occurred: {str(e)}")

# Error handler
@app.on_message(filters.private | filters.group)
async def error_handler(client: Client, message: Message):
    await message.reply_text("Invalid command! Use /start or /forward <message-link>")

# Run the bot
if __name__ == "__main__":
    print("Bot is running...")
    app.run()
