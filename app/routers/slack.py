import logging
from fastapi import APIRouter, Request, Header
from starlette.responses import Response
from starlette.background import BackgroundTasks
from slack_sdk import WebClient

from app.config.constants import SLACK_TOKEN
from app.utils.file import download_file, encode_image
from app.services.azure_openai import AzureOpenAIService

router = APIRouter()
openai_service = AzureOpenAIService()

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

    # Slack retried event
    if request.headers.get("x-slack-retry-num") and request.headers.get("x-slack-retry-reason") == "http_timeout":
        return Response("ok")

    event = body.get("event", {})
    if not event:
        return Response("no event found")

    channel = event.get("channel", "")
    thread_ts = event.get("thread_ts") or event.get("ts", "")
    user_text = event.get("text", "")
    files = event.get("files", [])

    # Hand off to background tasks so Slack doesn't time out
    background_tasks.add_task(handle_slack_message, channel, thread_ts, user_text, files)
    return Response("ok")


def handle_slack_message(channel: str, thread_ts: str, user_text: str, files: list):
    slack_client = WebClient(token=SLACK_TOKEN)

    try:
        if not files:
            # No attached files, so do standard text
            result = openai_service.process_text(user_text)
        else:
            # We have some files; let's see if at least one is recognized as an image
            image_found = False
            for f in files:
                mime = f.get("mimetype", "")
                if mime.startswith("image/"):
                    # We found an image
                    image_found = True
                    image_url = f.get("url_private", "")
                    raw_bytes = download_file(image_url)
                    if raw_bytes:
                        b64 = encode_image(raw_bytes)
                        result = openai_service.process_image(b64, user_text)
                    else:
                        result = "I couldn't download that image from Slack. Check permissions?"
                    break  # process first image only; or remove break if you want multi-image
            if not image_found:
                # We have files but none is an image
                result = "You attached a file but it's not an image. I'll just respond to text.\n\n" + openai_service.process_text(user_text)

        slack_client.chat_postMessage(channel=channel, text=result, thread_ts=thread_ts)

    except Exception as e:
        logging.exception("Error in handle_slack_message:")
        slack_client.chat_postMessage(
            channel=channel,
            text=f"Error: {e}",
            thread_ts=thread_ts,
        )
