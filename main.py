import asyncio
import logging
import re
import signal
import os
from dotenv import load_dotenv
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

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "7149816130:AAGXHwA8hHaPC0hp5yxaltC9uAZ6qr_0iuo")
API_ID = os.getenv("API_ID", "12380656")
API_HASH = os.getenv("API_HASH", "d927c13beaaf5110f25c505b7c071273")
SESSION_NAME = "forward_bot"

# Validate environment variables
if not all([BOT_TOKEN, API_ID, API_HASH]):
    logger.error("Missing required environment variables (BOT_TOKEN, API_ID, or API_HASH)")
    raise ValueError("Please set BOT_TOKEN, API_ID, and API_HASH in the .env file")

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
        media_types = {
            "photo": (app.send_photo, {"photo": "file"}),
            "video": (app.send_video, {"video": "file"}),
            "document": (app.send_document, {"document": "file"}),
            "audio": (app.send_audio, {"audio": "file"}),
            "sticker": (app.send_sticker, {"sticker": "file"}),
            "animation": (app.send_animation, {"animation": "file"}),
            "voice": (app.send_voice, {"voice": "file"}),
            "video_note": (app.send_video_note, {"video_note": "file"}),
            "contact": (app.send_contact, {"phone_number": "phone_number", "first_name": "first_name"})
        }

        for media_type, (send_func, params) in media_types.items():
            if getattr(message, media_type):
                if media_type == "contact":
                    # Handle contact messages
                    kwargs = {
                        "chat_id": target_chat_id,
                        "phone_number": message.contact.phone_number,
                        "first_name": message.contact.first_name,
                        "last_name": message.contact.last_name or ""
                    }
                else:
                    # Handle media by downloading and re-uploading
                    file = await message.download(in_memory=True)
                    kwargs = {
                        "chat_id": target_chat_id,
                        params[list(params.keys())[0]]: file,
                        "caption": message.caption or "",
                        "parse_mode": ParseMode.MARKDOWN
                    }
                    if media_type != "sticker":  # Stickers don't support captions
                        kwargs["caption"] = message.caption or ""
                return await send_func(**kwargs)

        logger.warning(f"Unsupported media type for message ID {message.id}")
        return None
    except Exception as e:
        logger.error(f"Error handling media: {e}")
        return None

async def forward_message(source_chat_id: str, message_id: int, target_chat_id: int, retries=3, delay=1):
    """Forward or copy a message, handling restricted content with retries."""
    for attempt in range(retries):
        try:
            # Fetch the message
            message = await app.get_messages(source_chat_id, message_id)
            if not message:
                logger.warning(f"Message ID {message_id} not found or inaccessible in {source_chat_id}")
                return "Message not found or bot lacks access to the chat. Ensure the message exists and the bot is a member for private chats."

            # Check for empty messages
            if message.empty:
                logger.warning(f"Message ID {message_id} is empty")
                return "Cannot forward empty messages. The message may have been deleted."

            # Check for unsupported types like polls
            if message.poll:
                logger.warning(f"Message ID {message_id} is a poll")
                return "Cannot forward polls."

            # Log if message is from an anonymous admin
            if message.from_user is None:
                logger.info(f"Message ID {message_id} is from an anonymous admin")

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
                elif message.media or message.contact:
                    # Handle media or contact by downloading and re-uploading
                    result = await handle_media_message(message, target_chat_id)
                    if not result:
                        return "Failed to handle restricted media or contact content."
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
        except FloodWait as e:
            wait_time = e.x * (2 ** attempt)  # Exponential backoff
            logger.warning(f"FloodWait: Sleeping for {wait_time} seconds")
            await asyncio.sleep(wait_time)
        except BadRequest as e:
            logger.error(f"BadRequest error: {e}")
            return f"Failed to forward message: {e}"
        except RPCError as e:
            logger.error(f"RPCError: {e}")
            return f"Telegram API error: {e}"
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return f"An error occurred: {e}"
    return "Max retries exceeded due to flood wait."

@app.on_message(filters.command("forward"))
async def forward_command(client: Client, message: Message):
    """Handle /forward <message-link> [target-chat-id] command."""
    try:
        # Check if message link is provided
        if len(message.command) < 2:
            await message.reply("Usage: /forward <message-link> [target-chat-id]")
            return

        # Extract message link and optional target chat ID
        message_link = message.command[1]
        target_chat_id = message.command[2] if len(message.command) >= 3 else message.chat.id

        # Validate target chat ID
        try:
            target_chat_id = int(target_chat_id) if str(target_chat_id).startswith(("-100", "@")) else message.chat.id
        except ValueError:
            await message.reply("Invalid target chat ID. Use a numeric chat ID (e.g., -100123456789) or @username.")
            return

        # Extract source chat ID and message ID
        source_chat_id, message_id = await extract_message_info(message_link)
        if not source_chat_id or not message_id:
            await message.reply("Invalid message link format. Use: https://t.me/channel/message_id or https://t.me/c/chat_id/message_id")
            return

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
        "Use /forward <message-link> [target-chat-id] to forward a message from any public or private Telegram channel/group, "
        "even if it has forwarding restrictions or is sent anonymously.\n"
        "Example: /forward https://t.me/channel/123\n"
        "For private chats, ensure the bot is a member.\n"
        "Optional: Specify a target chat ID (e.g., /forward https://t.me/channel/123 -100123456789)"
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

def handle_shutdown(signum, frame):
    """Handle shutdown signals."""
    logger.info("Shutting down bot...")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(app.stop())
    loop.close()
    exit(0)

if __name__ == "__main__":
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    # Run the main function in the default event loop
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Bot interrupted by user.")
    finally:
        loop.close()
