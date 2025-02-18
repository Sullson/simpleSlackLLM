import logging
import traceback

from fastapi import APIRouter, Request, Header
from starlette.background import BackgroundTasks
from starlette.responses import Response
from slack_sdk import WebClient

from app.config.constants import SLACK_TOKEN
from app.services.azure_openai import AzureOpenAIService
from app.utils.file import download_file, encode_image

router = APIRouter()
slack_client = WebClient(token=SLACK_TOKEN)

# 1) Detect the bot’s user ID from Slack so we can skip our own messages
#   This is done once at startup so we have a global BOT_USER_ID.
BOT_USER_ID = None
try:
    auth_info = slack_client.auth_test()
    BOT_USER_ID = auth_info["user_id"]  # e.g. "U123ABC..."
    logging.info(f"Slack Bot user ID: {BOT_USER_ID}")
except Exception as e:
    logging.exception("Error calling slack_client.auth_test() to get BOT_USER_ID")

openai_service = AzureOpenAIService()

# 2) We keep placeholders in a set for ignoring
IGNORED_PLACEHOLDER_TEXTS = {
    "Hmm, let me think... 🤔",
    "Checking the image... 👀"
}


@router.post("/events")
async def slack_events(
    request: Request,
    background_tasks: BackgroundTasks,
    headers: Header = None,
):
    """
    Slack event endpoint:
      - Return 200 right away so Slack won't retry
      - Process event in background
    """
    body = await request.json()

    # Slack verification challenge
    if "challenge" in body:
        return Response(content=body["challenge"], media_type="text/plain")

    if request.headers.get("x-slack-retry-num"):
        logging.info("Slack retry header present; returning 200 to avoid repeated calls.")

    event = body.get("event", {})
    background_tasks.add_task(process_slack_event, event)

    return Response("ok", status_code=200)


def process_slack_event(event: dict):
    """
    Background logic for Slack events:
      - If from our own bot user, ignore
      - If text is one of placeholders, ignore
      - Otherwise, post placeholder, do GPT logic, remove placeholder, post final or error
    """
    # 1) Skip if from our own bot
    if BOT_USER_ID and event.get("user") == BOT_USER_ID:
        logging.info("Ignoring event from our own bot user ID.")
        return

    # 2) Skip if Slack sets "bot_id" or "subtype=bot_message"
    #    (some Slack flows set bot_id on events from the app, or external bots)
    if "bot_id" in event or event.get("subtype") == "bot_message":
        logging.info("Ignoring bot message (bot_id or subtype=bot_message).")
        return

    channel = event.get("channel", "")
    thread_ts = event.get("thread_ts") or event.get("ts", "")
    user_text = event.get("text", "")
    files = event.get("files", [])

    # If text is one of our placeholders, skip
    if user_text in IGNORED_PLACEHOLDER_TEXTS:
        logging.info(f"Ignoring our own placeholder text: {user_text}")
        return

    # Step A: post the placeholder
    if files:
        placeholder_text = "Checking the image... 👀"
    else:
        placeholder_text = "Hmm, let me think... 🤔"

    placeholder_resp = slack_client.chat_postMessage(channel=channel, text=placeholder_text)
    placeholder_ts = placeholder_resp["ts"]

    try:
        # Step B: GPT logic
        if not files:
            # purely text
            response_text = openai_service.process_text(user_text)
        else:
            # see if there's an image
            image_found = False
            for f in files:
                mime = f.get("mimetype", "")
                if mime.startswith("image/"):
                    image_found = True
                    url = f.get("url_private", "")
                    raw_bytes = download_file(url)
                    if raw_bytes:
                        encoded = encode_image(raw_bytes)
                        # pass actual Slack mimetype or default to 'image/png'
                        response_text = openai_service.process_image(
                            image_base64=encoded,
                            user_text=user_text,
                            mimetype=mime or "image/png"
                        )
                    else:
                        response_text = "Could not download that image from Slack."
                    break
            if not image_found:
                response_text = (
                    "You attached a non-image file. "
                    "I'll just answer text:\n\n"
                    + openai_service.process_text(user_text)
                )

        # Step C: delete placeholder & post final success
        slack_client.chat_delete(channel=channel, ts=placeholder_ts)
        # Post in normal DM (no thread)
        slack_client.chat_postMessage(channel=channel, text=response_text)

    except Exception as e:
        logging.error("Error in process_slack_event", exc_info=True)

        # short error = last line of exception
        lines = str(e).splitlines()
        short_err = lines[-1] if lines else "Unknown error"

        # remove placeholder
        slack_client.chat_delete(channel=channel, ts=placeholder_ts)

        # post error in a thread
        slack_client.chat_postMessage(
            channel=channel,
            text=f"Error: {short_err}",
            thread_ts=thread_ts
        )
