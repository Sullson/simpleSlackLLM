import base64
from typing import List, Optional
import httpx

from langchain_openai import AzureChatOpenAI
from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
    AIMessage,
    BaseMessage,
)

from app.config.constants import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_DEPLOYMENT,
    AZURE_OPENAI_API_VERSION,
)


class AzureOpenAIService:
    def __init__(self):
        self.llm = AzureChatOpenAI(
            azure_deployment=AZURE_OPENAI_DEPLOYMENT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            model="gpt-4o",
            temperature=0.7,
            streaming=False,
            max_retries=2,
        )

    def process_text(self, user_text: str, context: List[dict] = None) -> str:
        """
        Incorporates the last Slack messages as context, then appends the new user_text.
        """
        if context is None:
            context = []

        messages: List[BaseMessage] = [
            SystemMessage(content=(
                "You are a helpful assistant. You can analyze both text and images if they are provided by the user."
                "You have the history of last few messages in the context."
            ))
        ]

        # Convert Slack context messages into LangChain messages
        for c in context:
            role = c["role"]
            content = c["content"]
            if role == "assistant":
                messages.append(AIMessage(content=content))
            else:
                messages.append(HumanMessage(content=content))

        # Finally, add the new user message
        messages.append(HumanMessage(content=user_text))

        result = self.llm.invoke(messages)
        return result.content.strip()

    def process_image(
        self,
        image_base64: str,
        user_text: str,
        mimetype: str,
        context: List[dict] = None
    ) -> str:
        """
        Accept base64 image data + user text + context.
        """
        if context is None:
            context = []

        messages: List[BaseMessage] = [
            SystemMessage(content=(
                "You are a vision-capable assistant. You can interpret images if provided."
            ))
        ]

        # Slack context to LLM messages
        for c in context:
            role = c["role"]
            content = c["content"]
            if role == "assistant":
                messages.append(AIMessage(content=content))
            else:
                messages.append(HumanMessage(content=content))

        # Finally add the user message with an embedded image block
        messages.append(
            HumanMessage(
                content=[
                    {
                        "type": "text",
                        "text": user_text.strip() or "Please describe this image:"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mimetype};base64,{image_base64}"
                        },
                    },
                ]
            )
        )

        result = self.llm.invoke(messages)
        return result.content.strip()
