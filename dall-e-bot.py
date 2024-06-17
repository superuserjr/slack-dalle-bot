import os
import logging
import logging.handlers
import openai
import base64
import io
import time
import random
from PIL import Image
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
from slack_sdk.errors import SlackApiError

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Capture all levels of logs
logger.propagate = False

# Define log file size (10MB) and number of backups
log_file_size = 10 * 1024 * 1024  # 10 MB
backup_count = 5

# Debug File Handler
debug_handler = logging.handlers.RotatingFileHandler(
    'debug.log', maxBytes=log_file_size, backupCount=backup_count)
debug_handler.setLevel(logging.DEBUG)
debug_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
debug_handler.setFormatter(debug_format)
logger.addHandler(debug_handler)

# Info File Handler
info_handler = logging.handlers.RotatingFileHandler(
    'info.log', maxBytes=log_file_size, backupCount=backup_count)
info_handler.setLevel(logging.INFO)
info_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
info_handler.setFormatter(info_format)
logger.addHandler(info_handler)

# Error File Handler
error_handler = logging.handlers.RotatingFileHandler(
    'error.log', maxBytes=log_file_size, backupCount=backup_count)
error_handler.setLevel(logging.ERROR)
error_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
error_handler.setFormatter(error_format)
logger.addHandler(error_handler)

# Load environment variables from 'config.env' file
load_dotenv('config.env')


# Function to load configuration from environment variables
def load_config():
    return {
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
        "SLACK_BOT_TOKEN": os.environ.get("SLACK_BOT_TOKEN"),
        "SLACK_APP_TOKEN": os.environ.get("SLACK_APP_TOKEN"),
        "OPENAI_DALLE_MODEL": os.environ.get("OPENAI_DALLE_MODEL", "dall-e-3"),
        "OPENAI_RETRY_COUNT": int(os.getenv("OPENAI_RETRY_COUNT", 3)),
        "OPENAI_RETRY_DELAY": int(os.getenv("OPENAI_RETRY_DELAY", 5)),
        "OPENAI_IMAGE_COUNT": int(os.getenv("OPENAI_IMAGE_COUNT", 1)),
        "DEFAULT_IMAGE_SIZE": os.getenv("DEFAULT_IMAGE_SIZE", "1024x1024"),
        "DEFAULT_IMAGE_QUALITY": os.getenv("DEFAULT_IMAGE_QUALITY", "hd"),
        "DEFAULT_IMAGE_STYLE": os.getenv("DEFAULT_IMAGE_STYLE", "vivid")
    }


# Load configuration
config = load_config()


# Initialize OpenAI API key
openai.api_key = config["OPENAI_API_KEY"]


# Function to generate image using DALL-E with retry logic
def generate_dalle_image(prompt, image_size=config["DEFAULT_IMAGE_SIZE"], image_style=config["DEFAULT_IMAGE_STYLE"], image_quality=config["DEFAULT_IMAGE_QUALITY"]):
    try_count = 0
    while try_count < config["OPENAI_RETRY_COUNT"]:
        try:
            response = openai.Image.create(
                model=config["OPENAI_DALLE_MODEL"],
                prompt=prompt,
                n=config["OPENAI_IMAGE_COUNT"],
                size=image_size,
                style=image_style,
                quality=image_quality,
                response_format='b64_json'
            )

            # Uncomment for detailed OpenAPI response
            # logging.info(f"OpenAI Response: {response}")

            if response and 'data' in response and response['data']:
                b64_data = response['data'][0].get('b64_json')
                if b64_data:
                    return b64_data
                else:
                    raise ValueError("Base64 data is missing in the response.")
            else:
                raise ValueError("Received an empty response from OpenAI.")
        except openai.error.OpenAIError as e:
            if 'safety system' in str(e).lower():
                logger.error(f"Safety system rejection with prompt '{prompt}': {e}")
                return "safety_rejection"
            elif 'content filters' in str(e).lower():
                logger.error(f"Content filter block with prompt '{prompt}': {e}")
                return "content_filter_blocked"
            else:
                logger.error(f"OpenAI API error with prompt '{prompt}': {e}")
        except Exception as e:
            logger.error(f"General error with prompt '{prompt}': {e}")
        finally:
            try_count += 1
            if try_count < config["OPENAI_RETRY_COUNT"]:
                time.sleep(config["OPENAI_RETRY_DELAY"])
            else:
                logger.error("All retry attempts failed.")
                return "retry_failed"


# Function to handle rate limit errors
def handle_rate_limit(e, try_count):
    retry_after = e.headers.get("Retry-After")
    if retry_after:
        logger.info(f"Rate limited. Retrying after {retry_after} seconds.")
        time.sleep(int(retry_after))
    else:
        # Exponential backoff with a maximum of 60 seconds
        backoff = min(60, 2 ** try_count + random.uniform(0, 1))
        logger.info(f"Retrying after backoff: {backoff} seconds.")
        time.sleep(backoff)


# Function to convert base64 string to image
def base64_to_image(b64_string):
    try:
        image_data = base64.b64decode(b64_string)
        return Image.open(io.BytesIO(image_data))
    except Exception as e:
        logger.error(f"Error in converting base64 to image: {e}")
        return None


# Function to handle image generation and response in a thread
def handle_image_generation_and_response(event, client):
    channel_id = event['channel']
    thread_ts = event['ts']

    # Set defaults from config
    image_size = config["DEFAULT_IMAGE_SIZE"]
    image_style = config["DEFAULT_IMAGE_STYLE"]
    image_quality = config["DEFAULT_IMAGE_QUALITY"]

    try:
        client.reactions_add(
            channel=channel_id,
            timestamp=thread_ts,
            name="hourglass-timer"
        )
    except SlackApiError as e:
        logger.error(f"Error adding reaction: {e}")

    # Replace em dash with hyphen in the user input
    user_input = event['text'].replace('—', '--').split('>')[1].strip() if '>' in event['text'] else event['text'].replace('—', '--')
    user_input_parts = user_input.split()

    size_options = {"--square": "1024x1024", "--landscape": "1792x1024", "--portrait": "1024x1792"}
    style_options = {"--vivid", "--natural"}
    quality_options = {"--hd", "--standard"}

    prompt_parts = []
    for part in user_input_parts:
        if part in size_options:
            image_size = size_options[part]
        elif part in style_options:
            image_style = part[2:]  # Remove '--' prefix
        elif part in quality_options:
            image_quality = part[2:]  # Remove '--' prefix
        else:
            prompt_parts.append(part)

    prompt = ' '.join(prompt_parts)

    logger.info(f"Prompt: {prompt}, Size: {image_size}, Style: {image_style}, Quality: {image_quality}")

    image_data = generate_dalle_image(prompt, image_size, image_style, image_quality)

    try:
        client.reactions_remove(
            channel=channel_id,
            timestamp=thread_ts,
            name="hourglass-timer"
        )
    except SlackApiError as e:
        logger.error(f"Error removing reaction: {e}")

    if image_data == "safety_rejection" or image_data == "content_filter_blocked":
        try:
            client.reactions_add(
                channel=channel_id,
                timestamp=thread_ts,
                name="x"
            )
        except SlackApiError as e:
            logger.error(f"Error adding reaction: {e}")
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text="Your request was not processed due to content restrictions. Please try a different prompt."
        )
    elif image_data == "retry_failed":
        try:
            client.reactions_add(
                channel=channel_id,
                timestamp=thread_ts,
                name="x"
            )
        except SlackApiError as e:
            logger.error(f"Error adding reaction: {e}")
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text="Failed to generate image after several attempts. Please try again later."
        )
    elif image_data:
        image = base64_to_image(image_data)
        if image:
            try:
                with io.BytesIO() as image_io:
                    image.save(image_io, format='PNG')
                    image_io.seek(0)
                    client.files_upload_v2(
                        channel=channel_id,
                        file=image_io,
                        filename='generated_image.png',
                        thread_ts=thread_ts
                    )
                client.reactions_add(
                    channel=channel_id,
                    timestamp=thread_ts,
                    name="frame_with_picture"
                )
            except Exception as e:
                logger.error(f"Error uploading to Slack: {e}")
                try:
                    client.reactions_add(
                        channel=channel_id,
                        timestamp=thread_ts,
                        name="x"
                    )
                except SlackApiError as e:
                    logger.error(f"Error adding reaction: {e}")
                client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=thread_ts,
                    text="Failed to upload image to Slack."
                )
        else:
            logger.error("Conversion of base64 data to image failed.")
            try:
                client.reactions_add(
                    channel=channel_id,
                    timestamp=thread_ts,
                    name="x"
                )
            except SlackApiError as e:
                logger.error(f"Error adding reaction: {e}")
            client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text="Failed to convert base64 data to image."
            )


# Initialize Slack app
app = App(token=config["SLACK_BOT_TOKEN"])


@app.event("app_mention")
def handle_app_mention_events(event, client, say):
    handle_image_generation_and_response(event, client)


@app.event("message")
def handle_message_events(event, client, logger):
    if event.get('channel_type') == 'im':
        logger.info("Handling direct message event.")
        handle_image_generation_and_response(event, client)


print("Starting script...")
if __name__ == "__main__":
    if not config["OPENAI_API_KEY"]:
        logger.error("OpenAI API key is not set.")
    elif not config["SLACK_BOT_TOKEN"]:
        logger.error("Slack Bot Token is not set.")
    else:
        print("🎨 Dall-e-bot is up! 🚀")
        handler = SocketModeHandler(app, config["SLACK_APP_TOKEN"])
        handler.start()
