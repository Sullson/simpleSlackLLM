import logging
import time
import hashlib
import hmac
import threading  # <-- NEW import for threading
from fastapi import APIRouter, Request, Header, HTTPException
from starlette.background import BackgroundTasks
from starlette.responses import Response
from slack_sdk import WebClient

from app.config.constants import SLACK_TOKEN, SLACK_SIGNING_SECRET
from app.services.azure_openai import AzureOpenAIService
from app.utils.file import download_file, encode_image

# [NEW] Import the markdown -> Slack converter
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


async def verify_slack_signature(request: Request):
    """
    Validate that this request is actually from Slack by checking:
      - x-slack-signature
      - x-slack-request-timestamp
      - HMAC SHA256 using our SLACK_SIGNING_SECRET
    """
    slack_signature = request.headers.get("x-slack-signature")
    slack_timestamp = request.headers.get("x-slack-request-timestamp")

    # If either header is missing, fail
    if not slack_signature or not slack_timestamp:
        raise HTTPException(status_code=400, detail="Missing Slack signature headers")

    # Guard against replay attacks: only allow if < 5 minutes old
    if abs(time.time() - int(slack_timestamp)) > 60 * 5:
        raise HTTPException(status_code=400, detail="Slack request timestamp is too old.")

    # Read the raw body
    raw_body = await request.body()
    body_str = raw_body.decode("utf-8")

    # Construct the signature base string
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
    # 1) Verify Slack signature
    await verify_slack_signature(request)

    # 2) Parse JSON body
    body = await request.json()

    # Slack challenge verification (when you first enable event subscription)
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
    This runs in a background task.
    We only proceed if:
      - msg_type == "message"
      - subtype is either None or "file_share"
      - user_id != our bot user ID
    """
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

    # 1) Fetch the last 6 messages for context
    context_messages = fetch_last_messages(channel=channel, limit=6)

    # 2) Post the FIRST placeholder message
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
        "Kinda lost, but will sort it out... 🫤"
    ]

    first_placeholder = placeholder_messages[0]
    placeholder_resp = slack_client.chat_postMessage(
        channel=channel,
        text=first_placeholder
    )
    placeholder_ts = placeholder_resp["ts"]

    # 3) We'll generate the final response in a separate thread
    result_holder = {}

    def generate_response():
        """
        This function does the actual Azure OpenAI calls,
        storing the final text or error into `result_holder`.
        """
        try:
            # If no files, process text
            if not files:
                final_resp = openai_service.process_text(
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
                            final_resp = openai_service.process_image(
                                image_base64=encoded,
                                user_text=user_text,
                                mimetype=mime or "image/png",
                                context=context_messages
                            )
                        else:
                            final_resp = "Could not download your image from Slack."
                        break
                if not image_found:
                    # No image recognized, treat as text
                    final_resp = (
                        "File was not recognized as an image. I'll just answer text:\n\n"
                        + openai_service.process_text(
                            user_text=user_text,
                            context=context_messages
                        )
                    )

            # Convert the final text from standard Markdown to Slack markup
            result_holder["text"] = markdown_to_slack(final_resp)

        except Exception as e:
            logging.exception("Error generating OpenAI response")
            result_holder["error"] = str(e)

    # Start that thread
    t = threading.Thread(target=generate_response)
    t.start()

    # 4) Meanwhile, rotate through placeholders every 2s until thread finishes or we exhaust messages
    for idx in range(1, len(placeholder_messages)):
        time.sleep(2)

        # if the thread is done, break early
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
            logging.exception("Failed to update placeholder message")

    # If still alive, wait for the thread to finish
    t.join()

    # 5) Remove the placeholder and post the final result (or error)
    try:
        slack_client.chat_delete(channel=channel, ts=placeholder_ts)
    except Exception:
        logging.exception("Failed to delete placeholder message")

    if "error" in result_holder:
        short_err = result_holder["error"].splitlines()[-1]
        slack_client.chat_postMessage(
            channel=channel,
            text=f"Error: {short_err}",
            thread_ts=thread_ts
        )
    else:
        final_text = result_holder.get("text", "No response.")
        slack_client.chat_postMessage(
            channel=channel,
            text=final_text,
            thread_ts=thread_ts
        )


def fetch_last_messages(channel: str, limit: int = 6):
    """
    Fetch the last `limit` messages from Slack in this channel.
    Return them as a list of dicts with roles: 'user' or 'assistant'.
    We skip messages from Slack system, etc.
    """
    try:
        response = slack_client.conversations_history(channel=channel, limit=limit)
        messages = response.get("messages", [])

        # Reverse to get them oldest to newest
        messages = list(reversed(messages))

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
