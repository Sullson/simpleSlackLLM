# app/routers/slack.py

import logging
import time
import hashlib
import hmac
import json
import threading  # For running the Azure OpenAI call in the background
from fastapi import APIRouter, Request, Header, HTTPException
from starlette.background import BackgroundTasks
from starlette.responses import Response
from slack_sdk import WebClient

from app.config.constants import SLACK_TOKEN, SLACK_SIGNING_SECRET
from app.services.azure_openai import AzureOpenAIService
from app.utils.file import download_file, encode_image
from app.utils.md_to_slack import markdown_to_slack

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


def verify_slack_signature(raw_body: bytes, headers):
    """
    Validate that this request is actually from Slack by checking:
      - x-slack-signature
      - x-slack-request-timestamp
      - HMAC SHA256 using our SLACK_SIGNING_SECRET
    """
    slack_signature = headers.get("x-slack-signature")
    slack_timestamp = headers.get("x-slack-request-timestamp")

    # If either header is missing, fail
    if not slack_signature or not slack_timestamp:
        raise HTTPException(status_code=400, detail="Missing Slack signature headers")

    # Guard against replay attacks: only allow if < 5 minutes old
    if abs(time.time() - int(slack_timestamp)) > 60 * 5:
        raise HTTPException(status_code=400, detail="Slack request timestamp is too old.")

    # Construct the signature base string
    body_str = raw_body.decode("utf-8")
    basestring = f"v0:{slack_timestamp}:{body_str}"

    # Compute our own HMAC SHA256 signature
    my_signature = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode("utf-8"),
        basestring.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    # Compare ours vs Slack’s
    if not hmac.compare_digest(my_signature, slack_signature):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")


@router.post("/events")
async def slack_events(
    request: Request,
    background_tasks: BackgroundTasks,
    headers: Header = None,
):
    """
    Main endpoint Slack calls for event subscriptions.
    """
    # 1) Read the raw body once
    raw_body = await request.body()

    # 2) Verify Slack signature (HMAC)
    verify_slack_signature(raw_body, request.headers)

    # 3) Parse JSON from that same raw body
    body = json.loads(raw_body.decode("utf-8"))

    # 4) Slack "url_verification" challenge
    if body.get("type") == "url_verification":
        # Just return the challenge text as Slack expects
        return Response(content=body["challenge"], media_type="text/plain")

    # (Alternatively, if you want to check for "challenge" in the body
    #  instead of "type":)
    # if "challenge" in body:
    #     return Response(content=body["challenge"], media_type="text/plain")

    # Return 200 quickly if Slack is retrying
    if request.headers.get("x-slack-retry-num"):
        logging.info("Slack retry header present; returning 200 instantly.")

    # Otherwise, handle a normal Slack event
    event = body.get("event", {})
    background_tasks.add_task(process_slack_event, event)

    return Response("ok", status_code=200)


def process_slack_event(event: dict):
    """
    Runs in a background task.
    """
    msg_type = event.get("type")
    subtype = event.get("subtype")
    user_id = event.get("user")

    # Must be "message"
    if msg_type != "message":
        logging.info(f"Ignoring event type={msg_type}")
        return

    # Only allow normal user messages or file_share
    if subtype not in [None, "file_share"]:
        logging.info(f"Ignoring event with subtype={subtype}")
        return

    # Must have a user ID that's not our bot
    if not user_id or user_id == BOT_USER_ID:
        logging.info(f"Ignoring event from user={user_id}")
        return

    # => It's a user message or file_share from a human
    channel = event.get("channel", "")
    thread_ts = event.get("thread_ts") or event.get("ts", "")
    user_text = event.get("text", "")
    files = event.get("files", [])

    # 1) Fetch the last 6 messages for context
    context_messages = fetch_last_messages(channel=channel, limit=6)

    # 2) Post placeholders to rotate every few seconds
    placeholder_messages = [
        "Hmmm, let me think... 👀",
        "Stirring data... 🍵",
        "Sorting bits... 🗂️",
        "Calibrating thoughts... 🧠",
        "Spinning circuits... 🔄",
        "Reticulating splines... ⚙️",
        "That is a hard one... 🤖",
        "Tuning AI... 🎛️",
        "Nearly there... ⏳",
        "Just a bit more......"
    ]

    placeholder_resp = slack_client.chat_postMessage(
        channel=channel,
        text=placeholder_messages[0]
    )
    placeholder_ts = placeholder_resp["ts"]

    # 3) Run the Azure OpenAI call in a separate thread
    result_holder = {}

    def generate_response():
        """
        Does the actual Azure OpenAI calls.
        Stores final text or error in `result_holder`.
        """
        try:
            if not files:
                # If no files, treat as text
                final_resp = openai_service.process_text(
                    user_text=user_text,
                    context=context_messages
                )
            else:
                # Check if at least one file is an image
                image_found = False
                for f in files:
                    mime = f.get("mimetype", "")
                    if mime.startswith("image/"):
                        image_found = True
                        url = f.get("url_private", "")
                        raw_bytes = download_file(url)
                        if raw_bytes:
                            encoded = encode_image(raw_bytes)
                            final_resp = openai_service.process_image(
                                image_base64=encoded,
                                user_text=user_text,
                                mimetype=mime,
                                context=context_messages
                            )
                        else:
                            final_resp = "Could not download your image from Slack."
                        break

                if not image_found:
                    final_resp = (
                        "File was not recognized as an image. "
                        "I'll just answer text:\n\n"
                        + openai_service.process_text(
                            user_text=user_text,
                            context=context_messages
                        )
                    )

            # Convert final text from Markdown to Slack markup
            result_holder["text"] = markdown_to_slack(final_resp)

        except Exception as e:
            logging.exception("Error generating OpenAI response")
            result_holder["error"] = str(e)

    t = threading.Thread(target=generate_response)
    t.start()

    # 4) Rotate placeholder text every few seconds until done or we run out
    for idx in range(1, len(placeholder_messages)):
        time.sleep(3)
        if not t.is_alive():
            break
        next_placeholder = placeholder_messages[idx]
        try:
            slack_client.chat_update(
                channel=channel,
                ts=placeholder_ts,
                text=next_placeholder
            )
        except Exception:
            logging.exception("Failed updating placeholder text")

    # Wait for the thread to finish if still alive
    t.join()

    # 5) Remove the placeholder
    try:
        slack_client.chat_delete(channel=channel, ts=placeholder_ts)
    except Exception:
        logging.exception("Failed to delete placeholder message")

    # 6) Post final response
    is_dm = channel.startswith("D")
    if "error" in result_holder:
        short_err = result_holder["error"].splitlines()[-1]
        if is_dm:
            # If it's a DM, no thread_ts
            slack_client.chat_postMessage(channel=channel, text=f"Error: {short_err}")
        else:
            # In channels, post error in thread
            slack_client.chat_postMessage(
                channel=channel,
                text=f"Error: {short_err}",
                thread_ts=thread_ts
            )
    else:
        final_text = result_holder.get("text", "No response.")
        # For success: always top-level
        slack_client.chat_postMessage(
            channel=channel,
            text=final_text
        )


def fetch_last_messages(channel: str, limit: int = 6):
    """
    Fetch the last `limit` messages from Slack in this channel.
    Return them as a list of dicts with roles: 'user' or 'assistant'.
    """
    try:
        response = slack_client.conversations_history(channel=channel, limit=limit)
        messages = response.get("messages", [])
        messages = list(reversed(messages))  # oldest to newest

        context_list = []
        for msg in messages:
            subtype = msg.get("subtype")
            if subtype not in (None, "file_share"):
                continue

            this_user_id = msg.get("user")
            text = msg.get("text", "")

            if not this_user_id:
                continue

            role = "assistant" if this_user_id == BOT_USER_ID else "user"
            context_list.append({"role": role, "content": text})

        return context_list

    except Exception as e:
        logging.exception("Error fetching channel history")
        return []
