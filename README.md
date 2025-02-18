# Slack + GPT-4o (Vision) Bot

A **Slack bot** built with **FastAPI** that uses **Azure GPT-4o** to handle both **text** and **image**-based questions.

## 1. Features

- **Text Completions**: Chat-like replies.
- **Image Understanding**: Auto-detects images uploaded in Slack and uses GPT-4o’s vision capabilities.
- **Message Context**: Fetches the last 6 messages from the Slack channel for context.
- **Slack Signature Verification**: Ensures only genuine Slack requests can reach the bot.

## 2. Prerequisites

1. A **Slack App** (with a Bot token `xoxb-...` and **Slack Signing Secret**).
2. An **Azure OpenAI** resource with a **GPT-4o** (vision-capable) model.
3. Optionally, a container registry (e.g. **Azure Container Registry** or **Docker Hub**) if you plan to deploy via Docker.
4. These environment variables:
    - `SLACK_TOKEN` (bot token)
    - `SLACK_SIGNING_SECRET` (required to verify Slack’s signature)
    - `AZURE_OPENAI_API_KEY`
    - `AZURE_OPENAI_ENDPOINT` (e.g. `https://myresource.openai.azure.com/`)
    - `AZURE_OPENAI_DEPLOYMENT` (e.g. `gpt-4o-2024-08-06`)
    - `AZURE_OPENAI_API_VERSION` (e.g. `2024-02-15-preview`)

## 3. Installation & Quick Start

1. **Install Dependencies**:
    
    ```bash
    bash
    Copy
    pip install -r requirements.txt
    
    ```
    
2. **Run Locally**:
    
    ```bash
    bash
    Copy
    export SLACK_TOKEN="xoxb-..."
    export SLACK_SIGNING_SECRET="abc123"
    # ...other required env vars...
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    
    ```
    
3. **Slack Setup**:
    - In your Slack App’s settings, under **Event Subscriptions**:
        - Enable events; set the **Request URL** to `<your-base-url>/slack/events`.
        - Add relevant **Bot Events** like `message.channels`, `message.im`.
    - Add `chat:write`, `files:read`, and any other needed scopes under **OAuth & Permissions**.
    - Install the app to your workspace.

## 4. Security Mechanism

- The bot **verifies** each incoming Slack request using your `SLACK_SIGNING_SECRET`.
- It checks the `x-slack-signature` and `x-slack-request-timestamp` headers, computing an HMAC using your secret.
- If the signature is **invalid** or the request is **too old**, the request is **rejected** with `401 Unauthorized`.
- This prevents unauthorized actors from spoofing Slack messages.

## 5. Docker Build & Deploy (Optional)

1. **Build** locally:
    
    ```bash
    bash
    Copy
    docker build -t your-image-name .
    
    ```
    
2. **Run** with environment variables:
    
    ```bash
    bash
    Copy
    docker run -p 8000:8000 \
      -e SLACK_TOKEN="xoxb-..." \
      -e SLACK_SIGNING_SECRET="abc123" \
      -e AZURE_OPENAI_API_KEY="..." \
      -e AZURE_OPENAI_ENDPOINT="..." \
      -e AZURE_OPENAI_DEPLOYMENT="..." \
      -e AZURE_OPENAI_API_VERSION="..." \
      your-image-name
    
    ```
    
3. **Push** to a registry if needed (e.g. Azure Container Registry, Docker Hub).

## 6. Usage

- **Text Messages**: Just type @mention or DM the bot. It will respond with GPT-4o text completions.
- **Image Messages**: Upload an image in Slack and tag the bot (or DM), and it will describe or analyze the image.

## 7. Troubleshooting

- **Signature Check**: Make sure `SLACK_SIGNING_SECRET` is correct. If the Slack subscription fails, check your logs for `Invalid Slack signature`.
- **Logs**: In production (e.g. Azure Web App), check container logs for detailed error messages.