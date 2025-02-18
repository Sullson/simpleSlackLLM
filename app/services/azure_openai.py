import base64
from typing import List
import httpx

from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage

from app.config.constants import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_DEPLOYMENT,
    AZURE_OPENAI_API_VERSION,
)

class AzureOpenAIService:
    """
    A wrapper for GPT-4o (vision-enabled) usage via LangChain's AzureChatOpenAI.
    """

    def __init__(self):
        # We assume this deployment is GPT-4o or GPT-4o-mini or whichever
        # version you have that supports vision input
        self.llm = AzureChatOpenAI(
            azure_deployment=AZURE_OPENAI_DEPLOYMENT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            model="gpt-4o",  # purely for tracing/logging, set how you like
            temperature=0.7,
            streaming=False,
            max_retries=2,
        )

    def process_text(self, user_text: str) -> str:
        """Simple text-only conversation with GPT-4o."""
        messages: List[BaseMessage] = [
            SystemMessage(content="You are a helpful assistant."),
            HumanMessage(content=user_text),
        ]
        response = self.llm.invoke(messages)
        return response.content.strip()

    def process_image(self, image_base64: str, user_text: str, mimetype: str) -> str:
        """
        Accepts base64 and the actual Slack mimetype (e.g., 'image/png').
        We'll feed "data:image/png;base64,xxx" or "data:image/jpeg;base64,xxx"
        to GPT-4 or GPT-4o.
        """
        messages = [
            SystemMessage(content="You are a vision-capable assistant."),
            HumanMessage(
                content=[
                    {
                        "type": "text",
                        "text": user_text.strip() or "Please describe this image:",
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mimetype};base64,{image_base64}"
                        },
                    },
                ]
            ),
        ]
        result = self.llm.invoke(messages)
