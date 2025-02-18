import base64
from typing import List, Union

import httpx
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage

from app.config.constants import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_DEPLOYMENT,
)

class AzureOpenAIService:
    """
    A simple wrapper around langchain_openai.AzureChatOpenAI to handle text and image tasks.
    """

    def __init__(self):
        # Instantiate the LLM (chat model) from langchain_openai
        self.llm = AzureChatOpenAI(
            azure_deployment=AZURE_OPENAI_DEPLOYMENT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            temperature=0.7,
            streaming=False,
            max_retries=2,
        )

    def process_text(self, user_text: str) -> str:
        """
        Simple text-only conversation with Azure GPT.
        """
        messages: List[BaseMessage] = [
            SystemMessage(content="You are a helpful assistant."),
            HumanMessage(content=user_text),
        ]
        result = self.llm.invoke(messages)
        return result.content.strip()

    def process_image(self, image_base64: str, user_text: str) -> str:
        """
        Calls a vision-enabled Azure GPT model with the base64 image included in the user content.
        The user may also include a question or instruction in 'user_text'.
        """
        # According to Azure Vision Chat docs, the 'messages' content can have structured data for the image:
        # e.g. content = [ { "type": "text", "text": user_text }, { "type": "image_url", "image_url": { "url": "data:image/..."} } ]
        # Make sure your deployment is GPT-4 Turbo with Vision or GPT-35-Turbo that supports images.
        messages: List[BaseMessage] = [
            SystemMessage(content="You are a vision-capable assistant. Answer questions about the uploaded image."),
            HumanMessage(content=[
                {
                    "type": "text",
                    "text": user_text.strip() or "Please describe this image:",
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}"
                    }
                }
            ]),
        ]
        result = self.llm.invoke(messages)
        return result.content.strip()
