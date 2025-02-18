import base64
import requests

from app.config.constants import SLACK_TOKEN


def download_file(url: str) -> bytes:
    """
    Downloads the file from Slack using the Slack bearer token.
    Returns bytes of the file content or None if it failed.
    """
    headers = {"Authorization": f"Bearer {SLACK_TOKEN}"}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.content
    return b""


def encode_image(file_bytes: bytes) -> str:
    """
    Returns the base64-encoded string of the image bytes.
    """
    return base64.b64encode(file_bytes).decode("utf-8")
