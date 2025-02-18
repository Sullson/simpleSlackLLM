import logging
from fastapi import APIRouter, Request, Header
from starlette.responses import Response
from starlette.background import BackgroundTasks

from app.config.constants import SLACK_TOKEN
from app.services.azure_openai import AzureOpenAIService
from app.utils.file import download_file, encode_image

router = APIRouter()
service = AzureOpenAIService()


@router.post("/events")
async def slack_events(
    request: Request,
    background_tasks: BackgroundTasks,
    headers: Header = None,
):
    """
    Listens for Slack events. 
    For a direct Slack app setup, the user can configure the Request URL to /slack/events
    in Slack's Event Subscriptions settings.
    """
    body = await request.json()

    # Slack challenge verification (when you first enable event subscription):
    if "challenge" in body:
        return Response(content=body["challenge"], media_type="text/plain")

    # Slack might resend events if it times out:
    if request.headers.get("x-slack-retry-num") and request.headers.get("x-slack-retry-reason") == "http_timeout":
        return Response("ok")  # Acknowledge retries silently

    # Main event handling
    event = body.get("event", {})
    if not event:
        return Response("no event found")

    user_text = event.get("text", "")
    files = event.get("files", [])

    channel = event.get("channel", "")
    thread_ts = event.get("thread_ts") or event.get("ts", "")

    # We'll do the actual LLM logic in background tasks, so Slack doesn't time out
    background_tasks.add_task(handle_slack_message, channel, thread_ts, user_text, files)
    return Response("ok")


def handle_slack_message(channel: str, thread_ts: str, user_text: str, files: list):
    """
    Handle Slack logic: 
    - If an image is attached, call `process_image`.
    - Otherwise, do text-based completions.
    """
    from slack_sdk import WebClient
    slack_client = WebClient(token=SLACK_TOKEN)

    try:
        if files:
            # If there's at least one file, assume it's an image; 
            # you may add further checks (like file.get("mimetype").startswith("image/"))
            file_info = files[0]
            image_url = file_info.get("url_private", "")
            raw_image_bytes = download_file(image_url)
            if raw_image_bytes:
                base64_encoded = encode_image(raw_image_bytes)
                llm_response = service.process_image(base64_encoded, user_text)
            else:
                llm_response = "Unable to download the image. Please try again."
        else:
            # No files, text only
            llm_response = service.process_text(user_text)

        # Post the reply to Slack
        slack_client.chat_postMessage(channel=channel, text=llm_response, thread_ts=thread_ts)
        logging.info(f"Slack reply posted to channel={channel}, thread_ts={thread_ts}.")
    except Exception as e:
        logging.exception("Error handling Slack event.")
        slack_client.chat_postMessage(
            channel=channel,
            text=f"Sorry, there was an error: {e}",
            thread_ts=thread_ts,
        )
