# Slack + Azure OpenAI (with Vision) Bot

This repository contains a **simple Slack bot** built with **FastAPI** and **LangChain** (via `langchain-openai`) to demonstrate:

- **Text-based completions** using **Azure GPT** (GPT-35-Turbo or GPT-4 Turbo with Vision).
- **Automatic image analysis** when a user uploads an image to Slack, utilizing a custom `process_image` function.

---

## 1. Prerequisites

1. **Python 3.10+**
2. **Slack App** with:
    - A **Bot Token** (`xoxb-...`)
    - A **Slack Signing Secret**
3. **Azure OpenAI** resource deployed with a **Chat** model that supports vision.
    - Example: **GPT-4 Turbo with Vision** or **GPT-35-Turbo** (with `2024-02-15-preview` for vision support).
4. Set the following environment variables:
    - `SLACK_TOKEN`: Slack Bot token (e.g., `xoxb-...`)
    - `SLACK_SIGNING_SECRET`: Slack signing secret
    - `AZURE_OPENAI_API_KEY`: Your Azure OpenAI key
    - `AZURE_OPENAI_ENDPOINT`: Example: `https://my-resource.openai.azure.com/`
    - `AZURE_OPENAI_DEPLOYMENT`: Example: `gpt-4-vision` or `gpt-35-turbo`
    - `AZURE_OPENAI_API_VERSION`: Example: `2024-02-15-preview`

These variables can be set in a `.env` file or directly in your deployment environment.

---

## 2. Project Structure

```
bash
CopyEdit
project-root/
├── app/
│   ├── config/
│   │   └── constants.py        # Environment variable configurations
│   ├── routers/
│   │   └── slack.py            # Slack event router
│   ├── services/
│   │   └── azure_openai.py     # AzureOpenAIService with text and image processing
│   ├── utils/
│   │   └── file.py             # Slack file download and base64 utilities
│   └── main.py                 # FastAPI startup script
├── requirements.txt            # Project dependencies
├── Dockerfile                  # Docker setup
└── README.md                   # Project documentation
```

---

## 3. Installation & Local Development

### 1. Clone the repository:

```bash
git clone https://github.com/your-repo/slack-azure-openai-bot.git
cd slack-azure-openai-bot
```

### 2. Install dependencies:

```bash
pip install -r requirements.txt
```

### 3. Set environment variables:

```bash
export SLACK_TOKEN="xoxb-123-abc"
export SLACK_SIGNING_SECRET="1234567890abcd"
export AZURE_OPENAI_API_KEY="your-azure-key"
export AZURE_OPENAI_ENDPOINT="https://my-resource.openai.azure.com/"
export AZURE_OPENAI_DEPLOYMENT="gpt-4-vision"
export AZURE_OPENAI_API_VERSION="2024-02-15-preview"
```

### 4. Run the app locally:

```bash
uvicorn app.main:app --reload
```

### 5. Expose your local server to Slack (e.g., using `ngrok`):

```bash
ngrok http 8000
```

### 6. Configure Slack:

- In **Slack App → Event Subscriptions**, set the **Request URL** to:
    
    ```
    https://your-ngrok-url.ngrok.io/slack/events
    ```
    
- Subscribe to:
    - `message.channels`
    - `message.im` (for direct messages)
- In **OAuth & Permissions**, ensure your bot has:
    - `chat:write`
    - `files:read`
    - `files:write` (if needed)

---

## 4. Usage

### Sending messages to the bot:

- **Text only**: The bot calls `process_text(...)` with Azure GPT and returns a chat-style response.
- **Image uploads**: The bot calls `process_image(...)`, which analyzes the image using Azure GPT vision capabilities and posts the result back to Slack.

### Example Interactions:

**Text-based query:**

```
User: What is the capital of France?
Bot: The capital of France is Paris.
```

**Image-based query:**

```
User uploads an image (e.g., a golden retriever) and asks:
User: "What do you see?"
Bot: "It appears to be a golden retriever in a park."
```

---

## 5. Deploying via Docker

### Build the Docker image:

```bash
docker build -t slack-azure-bot .
```

### Run the container:

```bash
docker run -it --rm -p 8000:8000 \
  -e SLACK_TOKEN="xoxb-..." \
  -e SLACK_SIGNING_SECRET="abc123" \
  -e AZURE_OPENAI_API_KEY="..." \
  -e AZURE_OPENAI_ENDPOINT="..." \
  -e AZURE_OPENAI_DEPLOYMENT="..." \
  -e AZURE_OPENAI_API_VERSION="..." \
  slack-azure-bot
```

- Ensure your **container's exposed port (`8000`)** is used for your Slack Event Subscription.

---

## 6. Extending & Customizing

- **Conversation History**: Store Slack messages in a database or memory for multi-turn conversations.
- **Additional Tools**: Use LangChain’s **function calling** or integrate more external APIs.
- **UI / Enhancements**: Add message parsing, custom formatting, or conversation memory.

---

## 7. Notes on Azure Vision

- You must have a **vision-enabled model** deployed.
- The bot sends images as `data:image/jpeg;base64,<data>` when calling Azure OpenAI.
- You can **modify prompts** for more detailed responses.

---

## 8. Troubleshooting

| Issue | Possible Causes & Fixes |
| --- | --- |
| **No response** | Check Slack bot token and ensure Slack events are triggered. Look at FastAPI logs. |
| **Image not recognized** | Slack may not send the file info. Ensure `files: [...]` is present in the event payload. |
| **Azure API errors** | Check `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, and `AZURE_OPENAI_DEPLOYMENT`. |
| **Missing Vision Capabilities** | Ensure your model supports images (e.g., `2024-02-15-preview` API version). |

---

## 9. License

Licensed under **Apache 2.0**. Feel free to **modify and extend** as needed.