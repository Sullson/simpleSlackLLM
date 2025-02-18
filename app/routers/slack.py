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

BOT_USER_ID = None
try:
    auth_info = slack_client.auth_test()
    BOT_USER_ID = auth_info["user_id"]  # e.g. "UABC123"
    logging.info(f"Slack Bot user ID is {BOT_USER_ID}")
except Exception:
    logging.exception("Could not determine BOT_USER_ID via auth_test().")

@router.post("/events")
async def slack_events(
    request: Request,
    background_tasks: BackgroundTasks,
    headers: Header = None,
):
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
    msg_type = event.get("type")
    subtype = event.get("subtype")
    user_id = event.get("user")

    # 1) Must be "message"
    if msg_type != "message":
        logging.info(f"Ignoring event type={msg_type}")
        return

    # 2) We only allow normal user messages (no subtype) OR file_share subtype
    allowed_subtypes = [None, "file_share"]
    if subtype not in allowed_subtypes:
        logging.info(f"Ignoring event with subtype={subtype}")
        return

    # 3) Must have a user ID that's not our bot
    if not user_id or user_id == BOT_USER_ID:
        logging.info(f"Ignoring event from user={user_id}")
        return

    # => If we reach here, it's a user message or file_share from a human
    channel = event.get("channel", "")
    thread_ts = event.get("thread_ts") or event.get("ts", "")
    user_text = event.get("text", "")
    files = event.get("files", [])

    # (Optional) Post a placeholder message
    placeholder_text = "Hmmm, let me think... 👀"
    placeholder_resp = slack_client.chat_postMessage(channel=channel, text=placeholder_text)
    placeholder_ts = placeholder_resp["ts"]

    try:
        # FETCH THE LAST 6 MESSAGES FOR CONTEXT
        context_messages = fetch_last_messages(channel=channel, limit=6)

        # Decide if there are images
        if not files:
            # purely text
            response_text = openai_service.process_text(
                user_text=user_text,
                context=context_messages
            )
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
                            mimetype=mime or "image/png",
                            context=context_messages
                        )
                    else:
                        response_text = "Could not download your image from Slack."
                    break
            if not image_found:
                # No image recognized, treat as text
                response_text = (
                    "File was not recognized as an image. I'll just answer text:\n\n"
                    + openai_service.process_text(
                        user_text=user_text,
                        context=context_messages
                    )
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


def fetch_last_messages(channel: str, limit: int = 6):
    """
    Fetch the last `limit` messages from Slack in this channel.
    Return them as a list of dicts with roles: 'user' or 'assistant'.
    We skip messages from Slack system, etc.
    """
    try:
        # Slack returns the newest messages first
        response = slack_client.conversations_history(channel=channel, limit=limit)
        messages = response.get("messages", [])

        # Reverse to get them oldest to newest
        messages = list(reversed(messages))

        context_list = []
        for msg in messages:
            # If Slack included a subtype we don't want (like bot_message),
            # we skip. We do allow file_share.
            subtype = msg.get("subtype")
            if subtype not in (None, "file_share"):
                continue

            # Identify if it's the bot or the user
            this_user_id = msg.get("user")
            text = msg.get("text", "")

            if not this_user_id:
                # Possibly system, no user field
                continue

            role = "assistant" if this_user_id == BOT_USER_ID else "user"
            context_list.append({"role": role, "content": text})

        return context_list

    except Exception as e:
        logging.exception("Error fetching channel history")
        return []
