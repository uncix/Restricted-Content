7149816130:AAGXHwA8hHaPC0hp5yxaltC9uAZ6qr_0iuo
import logging
import asyncio
import re
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, BadRequest, Forbidden, ChannelInvalid
from pyrogram.types import Message

# Configure logging for debugging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Bot configuration - replace with your values
API_ID = "12380656"
API_HASH = "d927c13beaaf5110f25c505b7c071273"
BOT_TOKEN = "7149816130:AAGXHwA8hHaPC0hp5yxaltC9uAZ6qr_0iuo"  # Example: "123456789:ABCDEF1234567890abcdef"
DESTINATION_CHAT = "-1002856810448"  # Where messages will be forwarded (username or chat ID)

# Initialize Pyrogram client with bot token
# API ID and API hash are not required for bot token authentication in Pyrogram 2.0.106
bot = Client(
    name="forward_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=10  # Adjust based on your needs
)

# Regular expression to parse Telegram message links
MESSAGE_LINK_REGEX = r"https?://t\.me/([^/]+)/(\d+)"  # Matches https://t.me/channel/123

# Handler for /forward command
@bot.on_message(filters.command("forward") & filters.private)
async def forward_command(client: Client, message: Message):
    """
    Handle /forward <msg-link> command to forward a specific message.
    Example: /forward https://t.me/SourceChannel/123
    """
    try:
        # Check if a message link was provided
        if len(message.command) < 2:
            await message.reply_text("Please provide a message link.\nExample: /forward https://t.me/SourceChannel/123")
            logger.info(f"User {message.from_user.id} sent /forward without a link")
            return

        # Extract the message link
        msg_link = message.command[1]
        logger.info(f"Received /forward command with link: {msg_link}")

        # Parse the message link
        match = re.match(MESSAGE_LINK_REGEX, msg_link)
        if not match:
            await message.reply_text("Invalid message link format. Use: https://t.me/channel/message_id")
            logger.error(f"Invalid message link: {msg_link}")
            return

        channel_username, message_id = match.groups()
        channel_identifier = f"@{channel_username}" if not channel_username.startswith("@") else channel_username
        message_id = int(message_id)

        # Verify bot is admin in the source channel
        bot_info = await client.get_me()
        try:
            chat = await bot.get_chat(channel_identifier)
            admins = await bot.get_chat_members(chat_id=chat.id, filter="administrators")
            bot_is_admin = any(admin.user.id == bot_info.id for admin in admins)

            if not bot_is_admin:
                await message.reply_text(f"Bot is not an admin in {channel_identifier}. Please make @{bot_info.username} an admin in that channel.")
                logger.error(f"Bot @{bot_info.username} is not admin in {channel_identifier}")
                return

        except Forbidden:
            await message.reply_text(f"Bot cannot access {channel_identifier}. Ensure it is an admin in the channel.")
            logger.error(f"Bot lacks access to {channel_identifier}")
            return
        except ChannelInvalid:
            await message.reply_text(f"Invalid channel: {channel_identifier}. Check the username.")
            logger.error(f"Invalid channel: {channel_identifier}")
            return

        # Fetch and forward the message
        try:
            source_message = await bot.get_messages(channel_identifier, message_id)
            if not source_message:
                await message.reply_text("Message not found or inaccessible.")
                logger.error(f"Message {message_id} not found in {channel_identifier}")
                return

            forwarded_message = await source_message.forward(DESTINATION_CHAT)
            await message.reply_text(f"Message forwarded to {DESTINATION_CHAT}!")
            logger.info(f"Forwarded message {message_id} from {channel_identifier} to {DESTINATION_CHAT}")

            # Log forwarded message details
            await log_forwarded_message(forwarded_message)

        except FloodWait as e:
            logger.warning(f"FloodWait: Sleeping for {e.value} seconds")
            await asyncio.sleep(e.value)
            await forward_command(client, message)  # Retry after wait

        except Forbidden as e:
            await message.reply_text(f"Error: Cannot forward message. Ensure bot has permission to send messages in {DESTINATION_CHAT}.")
            logger.error(f"Forbidden error: {e}")
            await notify_admin(f"Error: Bot lacks permission in {DESTINATION_CHAT}. Reason: {e}")

        except BadRequest as e:
            await message.reply_text(f"Error: Failed to forward message. Reason: {str(e)}")
            logger.error(f"BadRequest error: {e}")
            await notify_admin(f"Error: Failed to forward message {message_id} from {channel_identifier}. Reason: {e}")

        except Exception as e:
            await message.reply_text(f"Unexpected error: {str(e)}")
            logger.error(f"Unexpected error: {e}")
            await notify_admin(f"Unexpected error while forwarding message {message_id} from {channel_identifier}: {e}")

    except Exception as e:
        await message.reply_text(f"Failed to process command: {str(e)}")
        logger.error(f"Error processing /forward command: {e}")

async def log_forwarded_message(message: Message):
    """
    Log details of the forwarded message for debugging.
    """
    content_type = message.content_type or "unknown"
    logger.info(f"Forwarded message type: {content_type}, ID: {message.id}")
    if message.text:
        logger.info(f"Text: {message.text[:50]}...")
    elif message.caption:
        logger.info(f"Caption: {message.caption[:50]}...")

async def notify_admin(error_message: str):
    """
    Notify the bot admin (destination chat) about errors.
    """
    try:
        await bot.send_message(DESTINATION_CHAT, f"⚠️ {error_message}")
        logger.info("Sent error notification to admin")
    except Exception as e:
        logger.error(f"Failed to send error notification: {e}")

# Command to start the bot
@bot.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    """
    Handle /start command to confirm bot is running.
    """
    await message.reply_text(
        "🚀 Forward Bot is running!\n"
        "Use /forward <msg-link> to forward a message from any channel where I'm an admin.\n"
        "Example: /forward https://t.me/SourceChannel/123"
    )
    logger.info(f"Start command received from user {message.from_user.id}")

# Main function to run the bot
async def main():
    """
    Start the Pyrogram bot and handle startup checks.
    """
    try:
        await bot.start()
        bot_info = await bot.get_me()
        logger.info(f"Bot started: @{bot_info.username}")

        # Keep the bot running
        await asyncio.sleep(float("inf"))

    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

# Run the bot
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
