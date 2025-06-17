import asyncio
import logging
import re
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import RPCError, FloodWait, BadRequest
from pyrogram.enums import ChatType, ParseMode

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = "7149816130:AAGXHwA8hHaPC0hp5yxaltC9uAZ6qr_0iuo"  # Replace with your bot token
API_ID = "12380656"  # Replace with your API ID
API_HASH = "d927c13beaaf5110f25c505b7c071273"  # Replace with your API Hash
SESSION_NAME = "forward_bot"

# Initialize Pyrogram client
app = Client(
    SESSION_NAME,
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Regular expression to parse Telegram message links
MESSAGE_LINK_REGEX = r"https?://t\.me/(\w+)/(\d+)|https?://t\.me/c/(\d+)/(\d+)"

async def extract_message_info(link: str):
    """Extract chat ID and message ID from a Telegram message link."""
    match = re.match(MESSAGE_LINK_REGEX, link)
    if not match:
        return None, None
    if match.group(1):  # Public channel (t.me/username/message_id)
        chat_id = f"@{match.group(1)}"
        message_id = int(match.group(2))
    else:  # Private channel (t.me/c/chat_id/message_id)
        chat_id = -1000000000000 - int(match.group(3))
        message_id = int(match.group(4))
    return chat_id, message_id

async def handle_media_message(message: Message, target_chat_id: int):
    """Handle media messages by downloading and re-uploading to bypass restrictions."""
    try:
        if message.photo:
            file = await message.download(in_memory=True)
            return await app.send_photo(
                chat_id=target_chat_id,
                photo=file,
                caption=message.caption or "",
                parse_mode=ParseMode.MARKDOWN
            )
        elif message.video:
            file = await message.download(in_memory=True)
            return await app.send_video(
                chat_id=target_chat_id,
                video=file,
                caption=message.caption or "",
                parse_mode=ParseMode.MARKDOWN
            )
        elif message.document:
            file = await message.download(in_memory=True)
            return await app.send_document(
                chat_id=target_chat_id,
                document=file,
                caption=message.caption or "",
                parse_mode=ParseMode.MARKDOWN
            )
        elif message.audio:
            file = await message.download(in_memory=True)
            return await app.send_audio(
                chat_id=target_chat_id,
                audio=file,
                caption=message.caption or "",
                parse_mode=ParseMode.MARKDOWN
            )
        elif message.sticker:
            file = await message.download(in_memory=True)
            return await app.send_sticker(
                chat_id=target_chat_id,
                sticker=file
            )
        else:
            logger.warning(f"Unsupported media type for message ID {message.id}")
            return None
    except Exception as e:
        logger.error(f"Error handling media: {e}")
        return None

async def forward_message(source_chat_id: str, message_id: int, target_chat_id: int):
    """Forward or copy a message, handling restricted content."""
    try:
        # Fetch the message
        message = await app.get_messages(source_chat_id, message_id)
        if not message:
            return "Message not found or inaccessible."

        # Check if message has protected content
        if message.has_protected_content:
            logger.info(f"Handling protected content for message ID {message_id}")
            if message.text:
                # Send text message directly
                await app.send_message(
                    chat_id=target_chat_id,
                    text=message.text,
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=message.disable_web_page_preview
                )
            elif message.media:
                # Handle media by downloading and re-uploading
                result = await handle_media_message(message, target_chat_id)
                if not result:
                    return "Failed to handle restricted media content."
            else:
                return "Unsupported restricted content type."
        else:
            # Use copy for non-protected content
            await message.copy(
                chat_id=target_chat_id,
                caption=message.caption or "",
                parse_mode=ParseMode.MARKDOWN
            )
        return "Message forwarded successfully!"
    except BadRequest as e:
        logger.error(f"BadRequest error: {e}")
        return f"Failed to forward message: {e}"
    except FloodWait as e:
        logger.warning(f"FloodWait: Sleeping for {e.x} seconds")
        await asyncio.sleep(e.x)
        return await forward_message(source_chat_id, message_id, target_chat_id)
    except RPCError as e:
        logger.error(f"RPCError: {e}")
        return f"Telegram API error: {e}"
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return f"An error occurred: {e}"

@app.on_message(filters.command("forward"))
async def forward_command(client: Client, message: Message):
    """Handle /forward <message-link> command."""
    try:
        # Check if message link is provided
        if len(message.command) < 2:
            await message.reply("Usage: /forward <message-link>")
            return

        # Extract message link
        message_link = message.command[1]
        source_chat_id, message_id = await extract_message_info(message_link)
        if not source_chat_id or not message_id:
            await message.reply("Invalid message link format. Use: https://t.me/channel/message_id")
            return

        # Get target chat ID (user's private chat)
        target_chat_id = message.chat.id

        # Forward the message
        result = await forward_message(source_chat_id, message_id, target_chat_id)
        await message.reply(result)
    except Exception as e:
        logger.error(f"Error in forward_command: {e}")
        await message.reply(f"An error occurred: {e}")

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    """Handle /start command."""
    await message.reply(
        "Welcome to the Forward Bot!\n"
        "Use /forward <message-link> to forward a message from any public Telegram channel, "
        "even if it has forwarding restrictions.\n"
        "Example: /forward https://t.me/channel/123"
    )

async def main():
    """Main function to start the bot."""
    logger.info("Starting bot...")
    try:
        # Ensure the client starts in the same event loop
        await app.start()
        logger.info("Bot is running!")
        # Keep the bot running indefinitely
        await asyncio.Event().wait()
    except Exception as e:
        logger.error(f"Error in main: {e}")
    finally:
        # Properly stop the client
        await app.stop()
        logger.info("Bot stopped.")

if __name__ == "__main__":
    # Run the main function in the default event loop
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Bot interrupted by user.")
    finally:
        loop.close()
