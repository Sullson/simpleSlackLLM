import os

# Slack
SLACK_TOKEN = os.environ.get("SLACK_TOKEN", "")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "")

# Azure GPT-4o (vision) config
AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "")  # e.g., "gpt-4o-2024-08-06"
AZURE_OPENAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

# You can decide how many messages you want to keep in conversation if you store history:
NUMBER_OF_MESSAGES_TO_KEEP = int(os.environ.get("NUMBER_OF_MESSAGES_TO_KEEP", "5"))

