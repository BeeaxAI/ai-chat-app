# AI Chat

A multi-provider AI chat application built with FastAPI and vanilla JavaScript. Supports streaming responses from Anthropic Claude, OpenAI GPT, and Google Gemini — switchable from the UI without restarting.

## Features

- **Multi-provider support** — Anthropic Claude, OpenAI GPT, Google Gemini
- **Streaming responses** — real-time token-by-token output via SSE
- **Conversation history** — persistent chats stored in SQLite
- **Model selector** — switch provider and model per conversation
- **System prompt & settings** — configurable temperature, max tokens, and system prompt
- **Markdown rendering** — code blocks, tables, and formatting in responses
- **No login required** — single-user mode, open straight to chat

## Supported Models

| Provider | Models |
|----------|--------|
| Anthropic | Claude Sonnet 4, Claude Haiku 4.5, Claude Opus 4.6 |
| OpenAI | GPT-4o, GPT-4o Mini, GPT-4 Turbo |
| Google | Gemini 2.0 Flash, Gemini 1.5 Pro |

## Quick Start

**1. Clone the repo**
```bash
git clone https://github.com/BeeaxAI/ai-chat-app.git
cd ai-chat-app
```

**2. Set up environment**
```bash
cp .env.example .env
```

Edit `.env` and add at least one API key:
```env
ANTHROPIC_API_KEY=your-key
OPENAI_API_KEY=your-key
GOOGLE_API_KEY=your-key

DEFAULT_PROVIDER=google
DEFAULT_MODEL=gemini-2.0-flash
```

**3. Run**
```bash
bash run.sh
```

App will be available at **http://localhost:8000**

## Manual Setup

```bash
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Docker

```bash
docker build -t ai-chat .
docker run -p 8000:8000 --env-file .env ai-chat
```

## Project Structure

```
ai-chat-app/
├── main.py                    # FastAPI entry point
├── requirements.txt
├── run.sh                     # Quick-start script
├── backend/
│   ├── config.py              # Settings from .env
│   ├── database.py            # SQLite setup
│   ├── middleware/
│   │   └── rate_limit.py
│   ├── models/
│   │   └── schemas.py         # Pydantic models
│   ├── routers/
│   │   ├── auth.py
│   │   ├── chat.py            # Streaming chat endpoint
│   │   └── conversations.py   # CRUD for conversations
│   └── services/
│       ├── auth.py
│       └── llm_providers.py   # Anthropic / OpenAI / Google clients
└── frontend/
    ├── index.html
    ├── css/styles.css
    └── js/
        ├── app.js             # UI logic
        ├── api.js             # API client
        └── markdown.js        # Markdown renderer
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/chat/providers` | List available providers and models |
| POST | `/api/chat/stream` | Send a message (SSE streaming) |
| GET | `/api/conversations` | List conversations |
| POST | `/api/conversations` | Create a conversation |
| PATCH | `/api/conversations/{id}` | Rename / archive |
| DELETE | `/api/conversations/{id}` | Delete |
| GET | `/api/conversations/{id}/messages` | Get messages |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Anthropic API key |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `GOOGLE_API_KEY` | — | Google Gemini API key |
| `DEFAULT_PROVIDER` | `anthropic` | Default provider |
| `DEFAULT_MODEL` | `claude-sonnet-4-20250514` | Default model |
| `MAX_REQUESTS_PER_MINUTE` | `30` | Rate limit |
| `MAX_TOKENS_PER_REQUEST` | `4096` | Token cap per request |
| `DEBUG` | `false` | Enable debug logging |
