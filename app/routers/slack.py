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
openai_service = AzureOpenAIService()

# We'll do an auth_test() once to get the bot's own user ID, so we skip self.
BOT_USER_ID = None
try:
    auth_info = slack_client.auth_test()
    BOT_USER_ID = auth_info["user_id"]  # e.g. "UABC123"
    logging.info(f"Slack Bot user ID is {BOT_USER_ID}")
except Exception as e:
    logging.exception("Could not determine BOT_USER_ID via auth_test().")


@router.post("/events")
async def slack_events(
    request: Request,
    background_tasks: BackgroundTasks,
    headers: Header = None,
):
    """
    Slack event handler:
      1. Return 200 immediately -> prevents Slack from retry flood
      2. Kick off background task
    """
    body = await request.json()

    # Slack challenge verification (when first enabling event subscription)
    if "challenge" in body:
        return Response(content=body["challenge"], media_type="text/plain")

    # Always return 200, so Slack doesn't keep retrying
    if request.headers.get("x-slack-retry-num"):
        logging.info("Slack retry header present; returning 200 instantly.")

    event = body.get("event", {})
    background_tasks.add_task(process_slack_event, event)

    return Response("ok", status_code=200)


def process_slack_event(event: dict):
    """
    This runs in background.
    We only proceed if:
      - event["type"] == "message"
      - event.get("subtype") is None (meaning normal user message)
      - event.get("user") is a real user ID, not empty, not our own bot
    Otherwise, ignore it.
    """
    msg_type = event.get("type")
    subtype = event.get("subtype")
    user_id = event.get("user")

    # 1) Must be "message"
    if msg_type != "message":
        logging.info(f"Ignoring event type={msg_type}")
        return

    # 2) Must have specific subtype (defined below)
    allowed_subtypes = [None, "file_share"]
    if subtype not in allowed_subtypes:
        logging.info(f"Ignoring event with subtype={subtype}")
        return

    # 3) Must have a user ID that is not our bot
    if not user_id or user_id == BOT_USER_ID:
        logging.info(f"Ignoring event from user={user_id}")
        return

    # => If we reach here, it's a normal user message

    channel = event.get("channel", "")
    thread_ts = event.get("thread_ts") or event.get("ts", "")
    user_text = event.get("text", "")
    files = event.get("files", [])

    # Start the "placeholder" message logic, if you want that. 
    # If you prefer a simple approach, you can skip placeholders.

    # Example placeholder:
    placeholder_text = "Hmmm, let me think... 🤔"
    placeholder_resp = slack_client.chat_postMessage(channel=channel, text=placeholder_text)
    placeholder_ts = placeholder_resp["ts"]

    try:
        # If user attached images or other files:
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
                        response_text = openai_service.process_image(
                            image_base64=encoded,
                            user_text=user_text,
                            mimetype=mime or "image/png"
                        )
                    else:
                        response_text = "Could not download your image from Slack."
                    break
            if not image_found:
                response_text = (
                    "You attached a file that's not recognized as an image. "
                    "I'll just answer text:\n\n" + openai_service.process_text(user_text)
                )

        # Remove placeholder, post final success
        slack_client.chat_delete(channel=channel, ts=placeholder_ts)
        slack_client.chat_postMessage(channel=channel, text=response_text)

    except Exception as e:
        logging.exception("Error processing Slack event")

        # short error = last line
        lines = str(e).splitlines()
        short_err = lines[-1] if lines else "Unknown error"

        slack_client.chat_delete(channel=channel, ts=placeholder_ts)
        slack_client.chat_postMessage(
            channel=channel,
            text=f"Error: {short_err}",
            thread_ts=thread_ts
        )
