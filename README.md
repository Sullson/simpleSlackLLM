# Slack + GPT-4o (Vision) Bot

This repository contains a **simple Slack bot** built with **FastAPI** and **LangChain** (via [langchain-openai](https://pypi.org/project/langchain-openai/)). It demonstrates:

- Text-based completions using **Azure GPT-4o**.
- Automatic **image** understanding if the user uploads an image to Slack, using GPT-4o’s vision capabilities.

---

## 1. Prerequisites

1. **Slack App** (with Bot token `xoxb-...` and Slack Signing Secret).
2. **Azure OpenAI** resource deployed with a GPT-4o model supporting vision.
3. An **Azure Container Registry (ACR)** or a **Docker Hub** account to host your container image.
4. An **Azure Web App for Containers** instance (or ability to create one).
5. Environment variables (to be added in Azure App Settings or `.env`):
    - `SLACK_TOKEN` (Slack Bot token)
    - `SLACK_SIGNING_SECRET` (Slack signing secret)
    - `AZURE_OPENAI_API_KEY`
    - `AZURE_OPENAI_ENDPOINT` (e.g. `https://my-resource.openai.azure.com/`)
    - `AZURE_OPENAI_DEPLOYMENT` (name of your GPT-4o deployment, e.g. `gpt-4o-2024-08-06`)
    - `AZURE_OPENAI_API_VERSION` (e.g. `2024-02-15-preview`)

---

## 2. Project Structure

```
.
├─ app/
│   ├─ config/
│   │   └─ constants.py        # All environment variable configs
│   ├─ routers/
│   │   └─ slack.py            # Slack event router
│   ├─ services/
│   │   └─ azure_openai.py     # AzureOpenAIService w/ GPT-4o text & vision
│   ├─ utils/
│   │   └─ file.py             # Slack file download + base64
│   └─ main.py                 # FastAPI startup
├─ requirements.txt
├─ Dockerfile
└─ README.md

```

---

## 3. Building & Pushing the Docker Image

1. **Build** the Docker image locally (or in GitHub Actions, or Azure DevOps, etc.):
    
    ```bash
    docker build -t your-image-name .

    ```
    
2. **Test** locally if you wish (optional):
    
    ```bash
    docker run --rm -it -p 8000:8000 \
      -e SLACK_TOKEN="xoxb-..." \
      -e SLACK_SIGNING_SECRET="abc123" \
      -e AZURE_OPENAI_API_KEY="..." \
      -e AZURE_OPENAI_ENDPOINT="..." \
      -e AZURE_OPENAI_DEPLOYMENT="..." \
      -e AZURE_OPENAI_API_VERSION="..." \
      your-image-name
    ```
    
3. **Push** to a registry.
    - If using Azure Container Registry (ACR), you might do:
        
        ```bash
        # Log in to ACR
        az acr login --name YOUR_ACR_NAME
        
        # Tag image for ACR
        docker tag your-image-name YOUR_ACR_NAME.azurecr.io/your-image-name:latest
        
        # Push
        docker push YOUR_ACR_NAME.azurecr.io/your-image-name:latest
        ```
        
    - Or if using Docker Hub:
        
        ```bash
        docker tag your-image-name docker.io/your-dockerhub-user/your-image-name:latest
        docker push docker.io/your-dockerhub-user/your-image-name:latest
        ```
        

---

## 4. Creating an Azure Web App for Containers

1. In the [Azure Portal](https://portal.azure.com/), go to **Create a resource** and select **Web App**.
2. Under **Publish**, choose **Docker** container.
3. Under **Region**, pick where you want it hosted.
4. For **Container Settings**:
    - Select **Single Container** (or you can use a docker-compose approach if needed).
    - Choose your **Registry** type (Azure Container Registry, Docker Hub, etc.).
    - Enter your image name and tag, e.g. `YOUR_ACR_NAME.azurecr.io/your-image-name:latest`.
    - Provide any required credentials (e.g. your ACR username/password, or Docker Hub credentials).
5. **Review + Create** the Web App.

---

## 5. Configure Environment Variables in Azure Web App

Go to your **Web App** → **Settings** → **Configuration** → **Environment Variables** (or “Application settings” depending on the UI). Add each variable:

- `SLACK_TOKEN` = `xoxb-...`
- `SLACK_SIGNING_SECRET` = (whatever Slack gave you)
- `AZURE_OPENAI_API_KEY` = `YOUR_AZURE_OPENAI_KEY`
- `AZURE_OPENAI_ENDPOINT` = `https://<yourresource>.openai.azure.com/`
- `AZURE_OPENAI_DEPLOYMENT` = `gpt-4o-2024-08-06` (whatever your deployment is named)
- `AZURE_OPENAI_API_VERSION` = `2024-02-15-preview` (or whichever)

Click **Save**. The Web App will restart to load these new environment variables.

---

## 6. Configure Slack

1. In your Slack App settings (on api.slack.com/apps):
    - Go to **Basic Information** → **Event Subscriptions**.
    - Enable events, then set **Request URL** to your new Azure Web App URL plus `/slack/events`.For example: `https://my-bot.azurewebsites.net/slack/events`
    - Under **Subscribe to Bot Events**, add events like `message.im` or `message.channels` as needed.
2. Under **OAuth & Permissions**, ensure the **Scopes** include `chat:write`, `files:read`, etc.
3. Install the app to your workspace.

---

## 7. Usage

Once deployed, your Slack bot is live at the URL associated with your **Azure Web App**. Whenever a user DMs or mentions the bot (depending on your Slack configuration), Slack will send an event to `[Your-WebApp-URL]/slack/events`. The FastAPI code will:

1. **Check** if the user’s message includes an image:
    - If yes, we call the `process_image(...)` method of GPT-4o (Vision).
2. **If not**, we call the text-based method to handle normal conversation.

The response is then posted back to the same Slack channel or thread.

Examples:

- **Text only**:
    - “Hey bot, what is the capital of France?” → The model replies with `Paris`.
- **Image**:
    - Attach an image of a cat, “What do you see here?” → The model replies with “It looks like a cat in a living room,” etc.

---

## 8. Troubleshooting Tips

1. **Check Logs**: In the Azure Portal, go to your Web App → **Log stream** to see the container logs.
2. **Slack**: Check if the Slack event subscription is verified (look for a green check mark in Slack’s Event Subscriptions page).
3. **Permissions**: The Slack Bot must have “files:read” scope if you want to process images.
4. **Vision**: Confirm you have GPT-4o or a similar vision-enabled model. Otherwise you’ll get errors like “image not supported.”

---

## 9. Further Enhancements

- **Multi-turn Memory**: Save Slack conversation history in a database or Redis for context.
- **Function Calling**: Extend with more advanced function calling or tool use in GPT-4o.
- **Autoscaling**: Adjust your Azure App’s plan to handle heavier usage.