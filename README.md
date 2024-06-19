README for DALL-E Image Generator Slack Bot

## Overview

This project is a Slack Bot that integrates with OpenAI's DALL-E to generate images based on user prompts. It allows users to request images directly within Slack, where the bot processes these requests, interacts with the OpenAI API, and posts the generated images back into the conversation.

## Features

Image Generation: Users can request images with specific prompts.  
Revised Prompt: Option to send the revised prompt OpenAI creates back to the user.  
Customization: Options for different image sizes, styles, and qualities.  
Retry Logic: Handles API errors and rate limits with a retry mechanism.  
Logging: Errors and information are logged for troubleshooting.

## Requirements

Python 3.x  
Slack Workspace and Bot permissions  
OpenAI API key (for DALL-E)  
PIL (Python Imaging Library)  
Slack Bolt Python SDK  

## Interact with the Bot in Slack:

Mention the bot with a prompt in any channel or direct message.
Use optional flags for image size (--square, --landscape, --portrait), style (--vivid, --natural), and quality (--hd, --standard).

```
@bot_name Generate a landscape of a futuristic city at sunset --landscape --vivid
```

## Variables

```
OPENAI_API_KEY: Your OpenAI API key (no default).
SLACK_BOT_TOKEN: Your Slack Bot User OAuth Token (no default).
SLACK_APP_TOKEN: Your Slack App-Level Token (no default).
OPENAI_DALLE_MODEL: The specific DALL-E model to use (default: "dall-e-3").
OPENAI_RETRY_COUNT: Number of times to retry API call (default: 3).
OPENAI_RETRY_DELAY: Delay between retry attempts (default: 5 seconds).
OPENAI_IMAGE_COUNT: Number of images per prompt (default: 1).
DEFAULT_IMAGE_SIZE: Default size of image (default: 1024x1024)
DEFAULT_IMAGE_QUALITY: Default quality of image. (default: hd)
DEFAULT_IMAGE_STYLE: Default style of image. (default: vivid)
SEND_REVISED_PROMPT: Send the OpenAI generate revised prompt back to user. (default: false)
```

## Running the App on Your Local Machine or AWS Linux instance

* Set variables in config.env
* Create a new Slack app using the manifest.yml file
* Install the app into your Slack workspace
* Retrieve your OpenAI API key at https://platform.openai.com/account/api-keys
* Start the app

```bash
python3 -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt

python3 dall-e-bot.py
```