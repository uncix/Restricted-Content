from pyrogram import Client, filters
from pyrogram.types import Message

# Configuration (replace with your own bot token)
API_ID = "12380656"
API_HASH = "d927c13beaaf5110f25c505b7c071273"
BOT_TOKEN = "7149816130:AAGXHwA8hHaPC0hp5yxaltC9uAZ6qr_0iuo"  # Get from @BotFather

# Initialize the client with bot token
app = Client(
    name="forward_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Handler for /forward command
@app.on_message(filters.command("forward"))
async def forward_message(client: Client, message: Message):
    try:
        # Extract message link from command
        if len(message.command) < 2:
            await message.reply("Please provide a message link. Usage: /forward <msg-link>")
            return
        
        msg_link = message.command[1]
        # Validate message link (e.g., https://t.me/channel/123)
        if not msg_link.startswith("https://t.me/"):
            await message.reply("Invalid message link. Please use a valid Telegram message link (e.g., https://t.me/channel/123).")
            return

        # Split the link to get chat and message ID
        parts = msg_link.replace("https://t.me/", "").split("/")
        if len(parts) < 2 or not parts[0] or not parts[1].isdigit():
            await message.reply("Invalid message link format. Use format: https://t.me/channel/message_id")
            return

        chat_identifier = f"@{parts[0]}"  # Public channel username
        message_id = int(parts[1])

        # Fetch the message
        try:
            msg = await client.get_messages(chat_identifier, message_id)
        except Exception as e:
            await message.reply(f"Error fetching message: {str(e)}. Ensure the bot is a member of the channel or the channel is public.")
            return

        # Check if message exists
        if not msg:
            await message.reply("Message not found or inaccessible.")
            return

        # Copy the message to the user who sent the command
        await msg.copy(
            chat_id=message.from_user.id,
            disable_notification=True
        )
        await message.reply("Message forwarded successfully!")

    except Exception as e:
        await message.reply(f"Error: {str(e)}")

# Run the bot
if __name__ == "__main__":
    app.run()
