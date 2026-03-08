#!/usr/bin/env python3
"""
Generate SEO-optimized tutorial, comparison, and use-case pages for Ace Data Cloud docs.

Usage:
    python scripts/generate_seo_pages.py

Generates:
    - tutorials/<service>/python.mdx      — Python quickstart for each service
    - tutorials/<service>/javascript.mdx   — JavaScript quickstart for each service
    - tutorials/<service>/curl.mdx         — cURL quickstart for each service
    - comparisons/<slug>.mdx               — Service comparison pages
    - use-cases/<slug>.mdx                 — Use case / "How to build X" pages
    - blog/                                — Blog seed articles
"""

import json
import os
import textwrap
from pathlib import Path

DOCS_DIR = Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Service catalog — defines all services with metadata for page generation
# ---------------------------------------------------------------------------

SERVICES = [
    # AI Chat
    {
        "id": "claude",
        "name": "Claude",
        "provider": "Anthropic",
        "category": "AI Chat",
        "description": "Anthropic's Claude models for chat completions, code generation, and analysis",
        "endpoint": "/v1/chat/completions",
        "method": "POST",
        "model": "claude-sonnet-4-20250514",
        "sample_body": {
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hello, what can you do?"}],
        },
        "features": ["streaming", "multi-turn", "vision", "code generation", "128K context"],
        "guide_path": "guides/claude/claude_chat_completions",
        "api_ref_path": "api-reference/claude",
    },
    {
        "id": "openai",
        "name": "OpenAI GPT",
        "provider": "OpenAI",
        "category": "AI Chat",
        "description": "OpenAI GPT models including GPT-4o, GPT-4.1, and o-series reasoning models",
        "endpoint": "/v1/chat/completions",
        "method": "POST",
        "model": "gpt-4o",
        "sample_body": {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Explain quantum computing in simple terms."}],
        },
        "features": ["streaming", "vision", "function calling", "JSON mode", "image generation"],
        "guide_path": "guides/openai/openai_chat_completions",
        "api_ref_path": "api-reference/openai",
    },
    {
        "id": "gemini",
        "name": "Google Gemini",
        "provider": "Google",
        "category": "AI Chat",
        "description": "Google's Gemini models for chat, reasoning, and multimodal tasks",
        "endpoint": "/v1/chat/completions",
        "method": "POST",
        "model": "gemini-2.5-flash",
        "sample_body": {
            "model": "gemini-2.5-flash",
            "messages": [{"role": "user", "content": "Write a haiku about technology."}],
        },
        "features": ["streaming", "multi-turn", "vision", "long context", "thinking"],
        "guide_path": "guides/gemini/gemini_chat_completions",
        "api_ref_path": "api-reference/gemini",
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "provider": "DeepSeek",
        "category": "AI Chat",
        "description": "DeepSeek's models for chat, coding, and reasoning tasks",
        "endpoint": "/v1/chat/completions",
        "method": "POST",
        "model": "deepseek-chat",
        "sample_body": {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": "Solve this step by step: what is 15% of 240?"}],
        },
        "features": ["streaming", "reasoning", "coding", "math"],
        "guide_path": "guides/deepseek/deepseek_chat_completions",
        "api_ref_path": "api-reference/deepseek",
    },
    {
        "id": "grok",
        "name": "Grok",
        "provider": "xAI",
        "category": "AI Chat",
        "description": "xAI's Grok models for witty, knowledgeable chat and analysis",
        "endpoint": "/v1/chat/completions",
        "method": "POST",
        "model": "grok-3",
        "sample_body": {
            "model": "grok-3",
            "messages": [{"role": "user", "content": "What are the latest trends in AI?"}],
        },
        "features": ["streaming", "real-time knowledge", "reasoning"],
        "guide_path": "guides/grok/grok_chat_completions",
        "api_ref_path": "api-reference/grok",
    },
    # AI Image
    {
        "id": "midjourney",
        "name": "Midjourney",
        "provider": "Midjourney",
        "category": "AI Image",
        "description": "Midjourney's industry-leading AI image generation via API",
        "endpoint": "/midjourney/imagine",
        "method": "POST",
        "model": None,
        "sample_body": {
            "prompt": "A futuristic city at sunset, cyberpunk style --ar 16:9",
            "mode": "fast",
        },
        "features": ["text-to-image", "upscale", "variation", "in-painting", "blending", "async/webhook"],
        "guide_path": "guides/midjourney/midjourney_imagine",
        "api_ref_path": "api-reference/midjourney",
    },
    {
        "id": "flux",
        "name": "Flux",
        "provider": "Black Forest Labs",
        "category": "AI Image",
        "description": "Flux image generation models for fast, high-quality AI art",
        "endpoint": "/flux/images",
        "method": "POST",
        "model": "flux-schnell",
        "sample_body": {
            "model": "flux-schnell",
            "prompt": "A serene mountain landscape with aurora borealis",
        },
        "features": ["text-to-image", "fast generation", "multiple models"],
        "guide_path": "guides/flux/flux_images",
        "api_ref_path": "api-reference/flux",
    },
    {
        "id": "seedream",
        "name": "Seedream",
        "provider": "ByteDance",
        "category": "AI Image",
        "description": "ByteDance Seedream for high-fidelity AI image generation",
        "endpoint": "/seedream/images",
        "method": "POST",
        "model": "seedream-3.0",
        "sample_body": {
            "model": "seedream-3.0",
            "prompt": "A photorealistic portrait of a robot reading a book",
        },
        "features": ["text-to-image", "high fidelity", "multiple styles"],
        "guide_path": "guides/seedream/seedream_images",
        "api_ref_path": "api-reference/seedream",
    },
    {
        "id": "nano-banana",
        "name": "Nano Banana",
        "provider": "Google Gemini",
        "category": "AI Image",
        "description": "Gemini-based image generation and editing with Nano Banana",
        "endpoint": "/nano-banana/images",
        "method": "POST",
        "model": None,
        "sample_body": {
            "prompt": "A watercolor painting of a cozy bookshop",
        },
        "features": ["text-to-image", "image editing", "Gemini-powered"],
        "guide_path": "guides/nano-banana/nanobanana_images",
        "api_ref_path": "api-reference/nano-banana",
    },
    # AI Video
    {
        "id": "sora",
        "name": "Sora",
        "provider": "OpenAI",
        "category": "AI Video",
        "description": "OpenAI's Sora for generating stunning AI videos from text prompts",
        "endpoint": "/sora/videos",
        "method": "POST",
        "model": "sora-2",
        "sample_body": {
            "model": "sora-2",
            "prompt": "A cat playing piano in a jazz club",
            "duration": 10,
        },
        "features": ["text-to-video", "image-to-video", "multiple durations", "async/webhook"],
        "guide_path": "guides/sora/sora_videos",
        "api_ref_path": "api-reference/sora",
    },
    {
        "id": "veo",
        "name": "Veo",
        "provider": "Google",
        "category": "AI Video",
        "description": "Google's Veo for cinematic AI video generation",
        "endpoint": "/veo/videos",
        "method": "POST",
        "model": "veo-3",
        "sample_body": {
            "model": "veo-3",
            "prompt": "Time-lapse of a flower blooming in a garden",
        },
        "features": ["text-to-video", "cinematic quality", "async/webhook"],
        "guide_path": "guides/veo/veo_videos",
        "api_ref_path": "api-reference/veo",
    },
    {
        "id": "luma",
        "name": "Luma Dream Machine",
        "provider": "Luma AI",
        "category": "AI Video",
        "description": "Luma Dream Machine for fast, creative AI video generation",
        "endpoint": "/luma/videos",
        "method": "POST",
        "model": "ray-2",
        "sample_body": {
            "model": "ray-2",
            "prompt": "Ocean waves crashing on a tropical beach at golden hour",
        },
        "features": ["text-to-video", "image-to-video", "fast generation", "async/webhook"],
        "guide_path": "guides/luma/luma_videos",
        "api_ref_path": "api-reference/luma",
    },
    {
        "id": "kling",
        "name": "Kling",
        "provider": "Kuaishou",
        "category": "AI Video",
        "description": "Kling AI video generation for realistic and creative videos",
        "endpoint": "/kling/videos",
        "method": "POST",
        "model": "kling-v2",
        "sample_body": {
            "model": "kling-v2",
            "prompt": "A drone shot flying over a mountain range at dawn",
        },
        "features": ["text-to-video", "image-to-video", "motion brush", "async/webhook"],
        "guide_path": "guides/kling/kling_videos",
        "api_ref_path": "api-reference/kling",
    },
    {
        "id": "hailuo",
        "name": "Hailuo (MiniMax)",
        "provider": "MiniMax",
        "category": "AI Video",
        "description": "MiniMax Hailuo for AI video generation with Director mode",
        "endpoint": "/hailuo/videos",
        "method": "POST",
        "model": "T2V-01-Director",
        "sample_body": {
            "model": "T2V-01-Director",
            "prompt": "A child running through a field of sunflowers, slow motion",
        },
        "features": ["text-to-video", "director mode", "async/webhook"],
        "guide_path": "guides/hailuo/hailuo_videos",
        "api_ref_path": "api-reference/hailuo",
    },
    {
        "id": "seedance",
        "name": "Seedance",
        "provider": "ByteDance",
        "category": "AI Video",
        "description": "ByteDance Seedance for dance and motion video generation",
        "endpoint": "/seedance/videos",
        "method": "POST",
        "model": "doubao-seedance-1-5-pro-251215",
        "sample_body": {
            "model": "doubao-seedance-1-5-pro-251215",
            "content": [{"type": "text", "text": "A dancer performing contemporary ballet"}],
        },
        "features": ["text-to-video", "image-to-video", "dance/motion", "async/webhook"],
        "guide_path": "guides/seedance/seedance_videos",
        "api_ref_path": "api-reference/seedance",
    },
    # AI Audio
    {
        "id": "suno",
        "name": "Suno",
        "provider": "Suno AI",
        "category": "AI Audio",
        "description": "Suno AI music generation — create full songs from text prompts",
        "endpoint": "/suno/audios",
        "method": "POST",
        "model": "chirp-v4",
        "sample_body": {
            "prompt": "An upbeat pop song about summer adventures",
            "model": "chirp-v4",
            "custom": False,
            "action": "generate",
        },
        "features": ["text-to-music", "custom lyrics", "extend", "cover", "stems", "mashup", "persona"],
        "guide_path": "guides/suno/suno_audios",
        "api_ref_path": "api-reference/suno",
    },
    {
        "id": "fish",
        "name": "Fish Audio",
        "provider": "Fish Audio",
        "category": "AI Audio",
        "description": "Fish Audio for text-to-speech with voice cloning",
        "endpoint": "/fish/audios",
        "method": "POST",
        "model": None,
        "sample_body": {
            "text": "Welcome to Ace Data Cloud, your unified AI API platform.",
            "reference_id": "default",
        },
        "features": ["text-to-speech", "voice cloning", "multiple languages"],
        "guide_path": "guides/fish/fish_audios",
        "api_ref_path": "api-reference/fish",
    },
    # Web & Data
    {
        "id": "serp",
        "name": "Google Search (SERP)",
        "provider": "Google",
        "category": "Web & Data",
        "description": "Google Search results API — search, images, news, shopping, and more",
        "endpoint": "/serp/google",
        "method": "POST",
        "model": None,
        "sample_body": {
            "type": "search",
            "query": "best AI APIs 2026",
        },
        "features": ["web search", "image search", "news", "shopping", "knowledge graph"],
        "guide_path": "guides/serp/serp_google",
        "api_ref_path": "api-reference/serp",
    },
]

# ---------------------------------------------------------------------------
# Comparison pairs — for "X vs Y" pages
# ---------------------------------------------------------------------------

COMPARISONS = [
    {
        "slug": "claude-vs-openai",
        "title": "Claude API vs OpenAI API: A comprehensive comparison",
        "seo_title": "Claude API vs OpenAI API — Which is better for your project?",
        "description": "Compare Claude and OpenAI APIs side by side — pricing, features, performance, and code examples. Find out which AI chat API fits your needs.",
        "services": ["claude", "openai"],
        "aspects": [
            ("Models", "Claude offers Opus, Sonnet, and Haiku tiers. OpenAI offers GPT-4o, GPT-4.1, and o-series reasoning models."),
            ("Context window", "Claude supports up to 200K tokens. GPT-4o supports 128K tokens."),
            ("Streaming", "Both support SSE streaming with identical API format via Ace Data Cloud."),
            ("Vision", "Both support image inputs. GPT-4o also supports image generation."),
            ("Pricing", "Both are pay-as-you-go on Ace Data Cloud with free trial credits."),
        ],
    },
    {
        "slug": "claude-vs-gemini",
        "title": "Claude API vs Gemini API: Which AI model should you use?",
        "seo_title": "Claude API vs Google Gemini API — Features, pricing, and performance",
        "description": "Compare Anthropic Claude and Google Gemini APIs — models, capabilities, pricing, and integration examples through Ace Data Cloud.",
        "services": ["claude", "gemini"],
        "aspects": [
            ("Models", "Claude offers Opus/Sonnet/Haiku. Gemini offers 2.5 Pro, 2.5 Flash, and thinking models."),
            ("Context window", "Claude: 200K tokens. Gemini 2.5 Pro: 1M tokens."),
            ("Reasoning", "Both offer extended thinking capabilities for complex tasks."),
            ("Multimodal", "Both support text and image inputs. Gemini also processes audio and video."),
            ("Pricing", "Both available on Ace Data Cloud with unified billing."),
        ],
    },
    {
        "slug": "openai-vs-deepseek",
        "title": "OpenAI API vs DeepSeek API: Cost-effective AI comparison",
        "seo_title": "OpenAI GPT vs DeepSeek — Performance at a fraction of the cost",
        "description": "Compare OpenAI and DeepSeek APIs for chat, coding, and reasoning. Learn which offers better value through Ace Data Cloud's unified API.",
        "services": ["openai", "deepseek"],
        "aspects": [
            ("Models", "OpenAI: GPT-4o, GPT-4.1, o3/o4-mini. DeepSeek: DeepSeek-V3, DeepSeek-R1."),
            ("Coding", "Both excel at code generation. DeepSeek is particularly strong at competitive pricing."),
            ("Reasoning", "OpenAI o-series and DeepSeek-R1 both offer chain-of-thought reasoning."),
            ("Cost", "DeepSeek generally offers lower per-token pricing for comparable quality."),
            ("API format", "Both use OpenAI-compatible format on Ace Data Cloud — switch with one line change."),
        ],
    },
    {
        "slug": "midjourney-vs-flux",
        "title": "Midjourney API vs Flux API: AI image generation comparison",
        "seo_title": "Midjourney API vs Flux — Best AI image generation API in 2026",
        "description": "Compare Midjourney and Flux APIs for AI image generation — quality, speed, pricing, and use cases through Ace Data Cloud.",
        "services": ["midjourney", "flux"],
        "aspects": [
            ("Quality", "Midjourney excels at artistic, stylized images. Flux offers fast, photorealistic results."),
            ("Speed", "Flux Schnell generates in seconds. Midjourney takes 30-60 seconds in fast mode."),
            ("Features", "Midjourney: upscale, variation, in-painting, blending. Flux: rapid iterations, multiple models."),
            ("Pricing", "Flux is more cost-effective for high-volume use. Midjourney charges per generation."),
            ("Use cases", "Midjourney: marketing, art, design. Flux: rapid prototyping, batch generation."),
        ],
    },
    {
        "slug": "sora-vs-veo",
        "title": "Sora API vs Veo API: AI video generation face-off",
        "seo_title": "OpenAI Sora vs Google Veo — Which AI video API is better?",
        "description": "Compare Sora and Veo APIs for AI video generation — quality, duration, features, and pricing on Ace Data Cloud.",
        "services": ["sora", "veo"],
        "aspects": [
            ("Provider", "Sora by OpenAI. Veo by Google DeepMind."),
            ("Quality", "Both produce cinematic-quality videos. Veo 3 adds native audio generation."),
            ("Duration", "Sora: up to 25s (Pro). Veo: up to 8s per generation."),
            ("Models", "Sora: sora-2, sora-2-pro. Veo: veo-2, veo-3."),
            ("Image-to-video", "Both support image-to-video generation for reference-based creation."),
        ],
    },
    {
        "slug": "sora-vs-luma",
        "title": "Sora API vs Luma Dream Machine API: AI video generation",
        "seo_title": "Sora vs Luma Dream Machine — Best AI video generation API",
        "description": "Compare OpenAI Sora and Luma Dream Machine APIs — video quality, speed, pricing, and features on Ace Data Cloud.",
        "services": ["sora", "luma"],
        "aspects": [
            ("Speed", "Luma generates videos faster. Sora takes longer but produces higher fidelity."),
            ("Duration", "Sora: 10-25s. Luma: 5-10s per generation."),
            ("Quality", "Sora produces more cinematic results. Luma is great for quick creative iterations."),
            ("Models", "Sora: sora-2, sora-2-pro. Luma: ray-2, ray-2-flash."),
            ("Pricing", "Luma is more cost-effective per video. Sora charges premium for Pro quality."),
        ],
    },
    {
        "slug": "suno-vs-udio",
        "title": "Suno API vs Udio API: AI music generation comparison",
        "seo_title": "Suno vs Udio — Best AI music generation API for developers",
        "description": "Compare Suno and Udio APIs for AI music generation — song quality, features, customization, and pricing on Ace Data Cloud.",
        "services": ["suno"],
        "aspects": [
            ("Quality", "Suno produces radio-ready tracks. Udio excels at specific genre reproduction."),
            ("Features", "Suno: extend, cover, stems, mashup, persona. Udio: basic generation and extension."),
            ("Duration", "Suno v5: up to 9 minutes. Udio: up to 2 minutes per generation."),
            ("Customization", "Suno offers lyrics, style, persona control. Udio has simpler prompt-based control."),
            ("Models", "Suno: v3 through v5. Udio: latest model only."),
        ],
    },
    {
        "slug": "best-ai-image-apis",
        "title": "Best AI image generation APIs in 2026",
        "seo_title": "Top 5 AI image generation APIs — Midjourney, Flux, Seedream, and more",
        "description": "Compare the best AI image generation APIs available in 2026: Midjourney, Flux, Seedream, Nano Banana, and QR Art. Features, pricing, and code examples.",
        "services": ["midjourney", "flux", "seedream", "nano-banana"],
        "aspects": [
            ("Midjourney", "Industry-leading quality. Best for marketing, art, and professional design."),
            ("Flux", "Fastest generation. Best for rapid prototyping and batch processing."),
            ("Seedream", "ByteDance's cutting-edge model. Excellent photorealism and text rendering."),
            ("Nano Banana", "Gemini-powered. Best for image editing and iterative refinement."),
            ("Summary", "All available through one unified API at Ace Data Cloud with pay-as-you-go pricing."),
        ],
    },
    {
        "slug": "best-ai-video-apis",
        "title": "Best AI video generation APIs in 2026",
        "seo_title": "Top AI video generation APIs — Sora, Veo, Luma, Kling, and more",
        "description": "Compare the top AI video generation APIs: Sora, Veo, Luma, Kling, Hailuo, Seedance. Full comparison with code examples.",
        "services": ["sora", "veo", "luma", "kling", "hailuo", "seedance"],
        "aspects": [
            ("Sora", "OpenAI's flagship. Cinematic quality, up to 25s duration."),
            ("Veo", "Google DeepMind. Veo 3 adds native audio generation."),
            ("Luma", "Fastest generation. Great for creative iterations."),
            ("Kling", "Kuaishou's model. Motion brush for precise control."),
            ("Hailuo", "MiniMax's Director mode for cinematic control."),
            ("Seedance", "ByteDance. Specialized in dance and motion generation."),
        ],
    },
]

# ---------------------------------------------------------------------------
# Use cases — "How to build X" pages
# ---------------------------------------------------------------------------

USE_CASES = [
    {
        "slug": "ai-chatbot",
        "title": "How to build an AI chatbot with Python",
        "seo_title": "Build an AI chatbot with Python — Claude, GPT, Gemini API tutorial",
        "description": "Step-by-step tutorial to build an AI chatbot using Python with Claude, GPT, or Gemini via Ace Data Cloud's unified API.",
        "primary_service": "claude",
        "tags": ["chatbot", "python", "claude", "gpt", "tutorial"],
    },
    {
        "slug": "ai-chatbot-javascript",
        "title": "How to build an AI chatbot with JavaScript",
        "seo_title": "Build an AI chatbot with JavaScript/Node.js — OpenAI compatible API",
        "description": "Create an AI-powered chatbot using JavaScript and Node.js with any LLM (Claude, GPT, Gemini) through a single API.",
        "primary_service": "openai",
        "tags": ["chatbot", "javascript", "node.js", "openai", "tutorial"],
    },
    {
        "slug": "ai-image-generator",
        "title": "How to build an AI image generator app",
        "seo_title": "Build an AI image generator — Midjourney API + Python tutorial",
        "description": "Build a complete AI image generator application using Midjourney API with Python. Includes async generation, upscaling, and webhook handling.",
        "primary_service": "midjourney",
        "tags": ["image generation", "midjourney", "python", "tutorial"],
    },
    {
        "slug": "ai-music-generator",
        "title": "How to generate AI music with Suno API",
        "seo_title": "Generate AI music with Suno API — Python tutorial with code examples",
        "description": "Create AI-generated music tracks using Suno API. Covers basic generation, custom lyrics, style control, and song extension.",
        "primary_service": "suno",
        "tags": ["music generation", "suno", "python", "tutorial"],
    },
    {
        "slug": "ai-video-generator",
        "title": "How to generate AI videos with Sora API",
        "seo_title": "Generate AI videos with OpenAI Sora API — Complete tutorial",
        "description": "Create stunning AI-generated videos using OpenAI Sora API. Text-to-video and image-to-video with async processing.",
        "primary_service": "sora",
        "tags": ["video generation", "sora", "python", "tutorial"],
    },
    {
        "slug": "google-search-api",
        "title": "How to use Google Search API in Python",
        "seo_title": "Google Search API Python tutorial — SERP API with code examples",
        "description": "Access Google search results programmatically using the SERP API. Get web results, images, news, and knowledge graph data.",
        "primary_service": "serp",
        "tags": ["google search", "serp", "python", "web scraping"],
    },
    {
        "slug": "ai-text-to-speech",
        "title": "How to build a text-to-speech app with AI",
        "seo_title": "AI text-to-speech API tutorial — Fish Audio with voice cloning",
        "description": "Build a text-to-speech application using Fish Audio API with voice cloning support. Multiple languages and custom voices.",
        "primary_service": "fish",
        "tags": ["text-to-speech", "tts", "fish audio", "voice cloning"],
    },
    {
        "slug": "telegram-ai-bot",
        "title": "How to build a Telegram AI bot",
        "seo_title": "Build a Telegram AI bot with Python — GPT/Claude API tutorial",
        "description": "Create a Telegram bot powered by AI using Python. Supports chat, image generation, and music creation through Ace Data Cloud.",
        "primary_service": "openai",
        "tags": ["telegram", "bot", "python", "chatbot", "tutorial"],
    },
    {
        "slug": "discord-ai-bot",
        "title": "How to build a Discord AI bot",
        "seo_title": "Build a Discord AI bot — Chat, images, and music with one API",
        "description": "Create a feature-rich Discord bot with AI chat (GPT/Claude), image generation (Midjourney/Flux), and music (Suno) using Ace Data Cloud.",
        "primary_service": "openai",
        "tags": ["discord", "bot", "javascript", "tutorial"],
    },
    {
        "slug": "ai-saas-app",
        "title": "How to build an AI SaaS application",
        "seo_title": "Build an AI SaaS app — Integrate multiple AI APIs for your startup",
        "description": "Architecture guide for building an AI SaaS application using Ace Data Cloud. Covers authentication, billing, rate limiting, and multi-model integration.",
        "primary_service": "claude",
        "tags": ["saas", "architecture", "startup", "tutorial"],
    },
    {
        "slug": "mcp-claude-desktop",
        "title": "How to use MCP servers with Claude Desktop",
        "seo_title": "MCP servers for Claude Desktop — AI music, video, and search tools",
        "description": "Set up MCP servers in Claude Desktop to generate music (Suno), create videos (Sora, Luma), search the web, and generate images — all from chat.",
        "primary_service": "suno",
        "tags": ["mcp", "claude desktop", "tools", "tutorial"],
    },
    {
        "slug": "ai-qr-code",
        "title": "How to create artistic AI QR codes",
        "seo_title": "AI QR code generator API — Create beautiful QR codes with AI",
        "description": "Generate artistic, branded QR codes using AI. Combine functional QR codes with stunning AI-generated artwork via the QR Art API.",
        "primary_service": "midjourney",
        "tags": ["qr code", "ai art", "marketing", "tutorial"],
    },
]

# ---------------------------------------------------------------------------
# Blog articles
# ---------------------------------------------------------------------------

BLOG_ARTICLES = [
    {
        "slug": "unified-ai-api-platform",
        "title": "Why you need a unified AI API platform",
        "seo_title": "Unified AI API platform — One API key for ChatGPT, Claude, Gemini, Sora, Suno, and more",
        "description": "Stop juggling multiple AI API keys. Learn how a unified AI API platform simplifies development, reduces costs, and accelerates your AI product.",
        "date": "2026-03-09",
        "tags": ["ai api", "platform", "developer tools"],
        "author": "Ace Data Cloud",
    },
    {
        "slug": "openai-compatible-api",
        "title": "OpenAI-compatible API: Access 50+ AI models with one SDK",
        "seo_title": "OpenAI-compatible API — Use openai Python SDK with Claude, Gemini, DeepSeek, and more",
        "description": "Learn how to use the OpenAI Python/JS SDK to access Claude, Gemini, DeepSeek, Grok, and 50+ other models by changing just the base URL.",
        "date": "2026-03-09",
        "tags": ["openai", "sdk", "api", "compatibility"],
        "author": "Ace Data Cloud",
    },
    {
        "slug": "best-ai-apis-2026",
        "title": "Best AI APIs in 2026: The complete developer guide",
        "seo_title": "Best AI APIs 2026 — Top APIs for chat, image, video, music generation",
        "description": "A comprehensive guide to the best AI APIs available in 2026. Covers LLMs, image generation, video creation, music AI, and more with pricing comparison.",
        "date": "2026-03-09",
        "tags": ["ai apis", "guide", "2026", "comparison"],
        "author": "Ace Data Cloud",
    },
    {
        "slug": "ai-api-pricing-comparison",
        "title": "AI API pricing comparison: GPT vs Claude vs Gemini vs DeepSeek",
        "seo_title": "AI API pricing 2026 — Compare costs of ChatGPT, Claude, Gemini, DeepSeek",
        "description": "Detailed pricing comparison of major AI APIs: OpenAI GPT-4o, Anthropic Claude, Google Gemini, DeepSeek, and xAI Grok. Find the best value for your use case.",
        "date": "2026-03-09",
        "tags": ["pricing", "comparison", "cost", "ai api"],
        "author": "Ace Data Cloud",
    },
    {
        "slug": "mcp-servers-guide",
        "title": "What are MCP servers? A developer's guide to Model Context Protocol",
        "seo_title": "MCP servers explained — Model Context Protocol guide for AI developers",
        "description": "Learn about Model Context Protocol (MCP) servers, how they extend AI assistants with real-world tools, and how to use them with Claude Desktop, VS Code, and Cursor.",
        "date": "2026-03-09",
        "tags": ["mcp", "model context protocol", "claude", "ai tools"],
        "author": "Ace Data Cloud",
    },
    {
        "slug": "ai-video-generation-guide",
        "title": "AI video generation in 2026: Complete guide for developers",
        "seo_title": "AI video generation APIs 2026 — Sora, Veo, Luma, Kling developer guide",
        "description": "Everything you need to know about AI video generation APIs in 2026. Compare Sora, Veo, Luma, Kling, Hailuo, and Seedance with code examples.",
        "date": "2026-03-09",
        "tags": ["video generation", "ai video", "sora", "veo", "guide"],
        "author": "Ace Data Cloud",
    },
    {
        "slug": "suno-api-music-generation",
        "title": "Suno API: Generate music with AI — The complete guide",
        "seo_title": "Suno API tutorial — AI music generation with Python and JavaScript",
        "description": "Master Suno API for AI music generation. Create songs, extend tracks, generate covers, separate stems, and more with detailed code examples.",
        "date": "2026-03-09",
        "tags": ["suno", "music generation", "ai music", "tutorial"],
        "author": "Ace Data Cloud",
    },
    {
        "slug": "midjourney-api-guide",
        "title": "Midjourney API: Generate images programmatically",
        "seo_title": "Midjourney API — Generate AI images via API without Discord",
        "description": "Use Midjourney's AI image generation via API — no Discord needed. Complete guide with Python examples, upscaling, variations, and in-painting.",
        "date": "2026-03-09",
        "tags": ["midjourney", "image generation", "ai art", "api"],
        "author": "Ace Data Cloud",
    },
]

# ---------------------------------------------------------------------------
# Helper: get service by ID
# ---------------------------------------------------------------------------

SERVICE_MAP = {s["id"]: s for s in SERVICES}


def get_service(service_id: str) -> dict:
    return SERVICE_MAP[service_id]


# ---------------------------------------------------------------------------
# Template: tutorial pages
# ---------------------------------------------------------------------------


def generate_tutorial_python(service: dict) -> str:
    s = service
    body_json = json.dumps(s["sample_body"], indent=2)
    features_list = "\n".join(f"- {f}" for f in s["features"])

    lines = []
    lines.append(f'---\ntitle: "How to use {s["name"]} API with Python"')
    lines.append(f'seo: "{s["name"]} API Python tutorial — Quick start guide with code examples"')
    lines.append(f'description: "Learn how to integrate {s["name"]} API into your Python application. Step-by-step guide with authentication, request examples, and error handling."')
    lines.append("---\n")
    lines.append(f'This tutorial shows you how to use the **{s["name"]} API** with Python through Ace Data Cloud\'s unified API platform.\n')
    lines.append("## What you'll build\n")
    lines.append(f'By the end of this tutorial, you\'ll have a working Python script that calls the {s["name"]} API. Key capabilities:\n')
    lines.append(features_list + "\n")
    lines.append("## Prerequisites\n")
    lines.append("- Python 3.8+")
    lines.append("- An [Ace Data Cloud API key](https://platform.acedata.cloud) (free trial available)")
    lines.append("- `requests` library (`pip install requests`)\n")
    lines.append("## Step 1: Get your API key\n")
    lines.append("<Steps>")
    lines.append('<Step title="Create an account">')
    lines.append("    Sign up at [platform.acedata.cloud](https://platform.acedata.cloud).")
    lines.append("</Step>")
    lines.append(f'<Step title="Subscribe to {s["name"]}">')
    lines.append(f'    Go to the [{s["name"]} service page](https://platform.acedata.cloud) and click **Acquire**. You\'ll get free trial credits.')
    lines.append("</Step>")
    lines.append('<Step title="Copy your API key">')
    lines.append("    Navigate to your credentials and copy the Bearer token.")
    lines.append("</Step>")
    lines.append("</Steps>\n")
    lines.append("## Step 2: Make your first request\n")
    lines.append("```python")
    lines.append("import requests\n")
    lines.append('API_KEY = "YOUR_API_KEY"')
    lines.append('BASE_URL = "https://api.acedata.cloud"\n')
    lines.append("response = requests.post(")
    lines.append(f'    f"{{BASE_URL}}{s["endpoint"]}",')
    lines.append("    headers={")
    lines.append('        "Authorization": f"Bearer {API_KEY}",')
    lines.append('        "Content-Type": "application/json",')
    lines.append("    },")
    lines.append(f"    json={body_json},")
    lines.append(")\n")
    lines.append("data = response.json()")
    lines.append("print(data)")
    lines.append("```\n")
    lines.append("## Step 3: Handle the response\n")
    lines.append("The API returns a JSON response. Here's how to parse it:\n")
    lines.append("```python")
    lines.append("if response.status_code == 200:")
    lines.append('    result = response.json()')
    lines.append('    print("Success:", result)')
    lines.append("elif response.status_code == 401:")
    lines.append('    print("Error: Invalid API key")')
    lines.append("elif response.status_code == 429:")
    lines.append('    print("Error: Rate limit exceeded, try again later")')
    lines.append("else:")
    lines.append('    print(f"Error {response.status_code}:", response.text)')
    lines.append("```\n")

    if s["category"] == "AI Chat":
        lines.append("## Step 4: Streaming (real-time response)\n")
        lines.append("For chat models, you can stream responses token by token:\n")
        lines.append("```python")
        lines.append("import requests\n")
        lines.append("response = requests.post(")
        lines.append(f'    f"{{BASE_URL}}{s["endpoint"]}",')
        lines.append("    headers={")
        lines.append('        "Authorization": f"Bearer {API_KEY}",')
        lines.append('        "Content-Type": "application/json",')
        lines.append('        "Accept": "text/event-stream",')
        lines.append("    },")
        lines.append("    json={")
        if s["model"]:
            lines.append(f'        "model": "{s["model"]}",')
        lines.append('        "messages": [{"role": "user", "content": "Tell me a story"}],')
        lines.append('        "stream": True,')
        lines.append("    },")
        lines.append("    stream=True,")
        lines.append(")\n")
        lines.append("for line in response.iter_lines():")
        lines.append("    if line:")
        lines.append('        decoded = line.decode("utf-8")')
        lines.append('        if decoded.startswith("data: ") and decoded != "data: [DONE]":')
        lines.append('            print(decoded[6:], end="", flush=True)')
        lines.append("```\n")
    else:
        lines.append("## Step 4: Async processing with webhooks\n")
        lines.append("For long-running tasks, use webhooks to receive results asynchronously:\n")
        lines.append("```python")
        lines.append("response = requests.post(")
        lines.append(f'    f"{{BASE_URL}}{s["endpoint"]}",')
        lines.append("    headers={")
        lines.append('        "Authorization": f"Bearer {API_KEY}",')
        lines.append('        "Content-Type": "application/json",')
        lines.append("    },")
        lines.append(f"    json={{")
        for k, v in s["sample_body"].items():
            lines.append(f'        "{k}": {json.dumps(v)},')
        lines.append(f'        "callback_url": "https://your-server.com/webhook",')
        lines.append("    },")
        lines.append(")\n")
        lines.append("task = response.json()")
        lines.append('print("Task ID:", task.get("task_id"))')
        lines.append("# Results will be sent to your callback_url when ready")
        lines.append("```\n")

    lines.append("## Error handling\n")
    lines.append("| Status code | Meaning | What to do |")
    lines.append("|---|---|---|")
    lines.append("| 200 | Success | Parse the response |")
    lines.append("| 400 | Bad request | Check your request parameters |")
    lines.append("| 401 | Unauthorized | Verify your API key |")
    lines.append("| 403 | Forbidden | Content may violate usage policies |")
    lines.append("| 429 | Rate limited | Wait and retry with exponential backoff |")
    lines.append("| 500 | Server error | Retry after a short delay |\n")
    lines.append("## Next steps\n")
    lines.append("<CardGroup cols={2}>")
    lines.append(f'<Card title="API reference" href="/{s["api_ref_path"]}" icon="code">')
    lines.append("    Full API specification with all parameters.")
    lines.append("</Card>")
    lines.append(f'<Card title="Detailed guide" href="/{s["guide_path"]}" icon="book">')
    lines.append("    In-depth guide with advanced features.")
    lines.append("</Card>")
    lines.append("</CardGroup>")

    return "\n".join(lines) + "\n"


def generate_tutorial_javascript(service: dict) -> str:
    s = service
    body_json = json.dumps(s["sample_body"], indent=2)
    features_list = "\n".join(f"- {f}" for f in s["features"])

    lines = []
    lines.append(f'---\ntitle: "How to use {s["name"]} API with JavaScript"')
    lines.append(f'seo: "{s["name"]} API JavaScript tutorial — Node.js quick start guide"')
    lines.append(f'description: "Integrate {s["name"]} API into your JavaScript or Node.js application. Authentication, fetch examples, streaming, and error handling."')
    lines.append("---\n")
    lines.append(f'This tutorial shows you how to call the **{s["name"]} API** from JavaScript (Node.js or browser) using Ace Data Cloud.\n')
    lines.append("## What you'll learn\n")
    lines.append(features_list + "\n")
    lines.append("## Prerequisites\n")
    lines.append("- Node.js 18+ (for server-side) or a modern browser")
    lines.append("- An [Ace Data Cloud API key](https://platform.acedata.cloud) (free trial available)\n")
    lines.append("## Quick start\n")
    lines.append("### Using fetch (Node.js 18+ / Browser)\n")
    lines.append("```javascript")
    lines.append('const API_KEY = "YOUR_API_KEY";')
    lines.append('const BASE_URL = "https://api.acedata.cloud";\n')
    lines.append(f"const response = await fetch(`${{BASE_URL}}{s['endpoint']}`, {{")
    lines.append('  method: "POST",')
    lines.append("  headers: {")
    lines.append('    "Authorization": `Bearer ${API_KEY}`,')
    lines.append('    "Content-Type": "application/json",')
    lines.append("  },")
    lines.append(f"  body: JSON.stringify({body_json}),")
    lines.append("});\n")
    lines.append("const data = await response.json();")
    lines.append("console.log(data);")
    lines.append("```\n")

    if s["category"] == "AI Chat":
        lines.append("### Streaming\n")
        lines.append("```javascript")
        lines.append(f'const response = await fetch(`${{BASE_URL}}{s["endpoint"]}`, {{')
        lines.append('  method: "POST",')
        lines.append("  headers: {")
        lines.append('    "Authorization": `Bearer ${API_KEY}`,')
        lines.append('    "Content-Type": "application/json",')
        lines.append("  },")
        lines.append("  body: JSON.stringify({")
        if s["model"]:
            lines.append(f'    "model": "{s["model"]}",')
        lines.append('    "messages": [{ "role": "user", "content": "Tell me a story" }],')
        lines.append('    "stream": true,')
        lines.append("  }),")
        lines.append("});\n")
        lines.append("const reader = response.body.getReader();")
        lines.append("const decoder = new TextDecoder();\n")
        lines.append("while (true) {")
        lines.append("  const { done, value } = await reader.read();")
        lines.append("  if (done) break;")
        lines.append("  const chunk = decoder.decode(value);")
        lines.append("  process.stdout.write(chunk);")
        lines.append("}")
        lines.append("```\n")
        lines.append("### Using the OpenAI SDK\n")
        lines.append("The fastest way to get started — use the official OpenAI SDK with Ace Data Cloud:\n")
        lines.append("```bash\nnpm install openai\n```\n")
        lines.append("```javascript")
        lines.append('import OpenAI from "openai";\n')
        lines.append("const client = new OpenAI({")
        lines.append('  apiKey: "YOUR_API_KEY",')
        lines.append('  baseURL: "https://api.acedata.cloud/v1",')
        lines.append("});\n")
        lines.append("const completion = await client.chat.completions.create({")
        lines.append(f'  model: "{s["model"] or "gpt-4o"}",')
        lines.append('  messages: [{ role: "user", content: "Hello!" }],')
        lines.append("});\n")
        lines.append("console.log(completion.choices[0].message.content);")
        lines.append("```\n")
    else:
        lines.append("### Async processing\n")
        lines.append("```javascript")
        lines.append("// Submit task and poll for results")
        lines.append("const task = await response.json();")
        lines.append('console.log("Task submitted:", task.task_id);')
        lines.append("// Use callback_url for webhook delivery, or poll the tasks endpoint")
        lines.append("```\n")

    lines.append("## Error handling\n")
    lines.append("```javascript")
    lines.append("if (!response.ok) {")
    lines.append("  const error = await response.json();")
    lines.append("  switch (response.status) {")
    lines.append('    case 401: console.error("Invalid API key"); break;')
    lines.append('    case 429: console.error("Rate limited — retry later"); break;')
    lines.append("    default: console.error(`Error ${response.status}:`, error);")
    lines.append("  }")
    lines.append("}")
    lines.append("```\n")
    lines.append("## Next steps\n")
    lines.append("<CardGroup cols={2}>")
    lines.append(f'<Card title="Python tutorial" href="/tutorials/{s["id"]}/python" icon="python">')
    lines.append("    Same API, Python examples.")
    lines.append("</Card>")
    lines.append(f'<Card title="API reference" href="/{s["api_ref_path"]}" icon="code">')
    lines.append("    Full API specification.")
    lines.append("</Card>")
    lines.append("</CardGroup>")

    return "\n".join(lines) + "\n"


def generate_tutorial_curl(service: dict) -> str:
    s = service

    lines = []
    lines.append(f'---\ntitle: "How to use {s["name"]} API with cURL"')
    lines.append(f'seo: "{s["name"]} API cURL examples — Quick start from the command line"')
    lines.append(f'description: "Test the {s["name"]} API from your terminal using cURL. Copy-paste examples for authentication, basic requests, and streaming."')
    lines.append("---\n")
    lines.append(f'Test the **{s["name"]} API** directly from your terminal — no SDK needed.\n')
    lines.append("## Basic request\n")
    lines.append("```bash")
    lines.append(f'curl -X {s["method"]} https://api.acedata.cloud{s["endpoint"]} \\')
    lines.append('  -H "Authorization: Bearer YOUR_API_KEY" \\')
    lines.append('  -H "Content-Type: application/json" \\')
    lines.append("  -d '" + json.dumps(s["sample_body"]) + "'")
    lines.append("```\n")

    if s["category"] == "AI Chat":
        lines.append("## Streaming\n")
        lines.append("```bash")
        lines.append(f'curl -X POST https://api.acedata.cloud{s["endpoint"]} \\')
        lines.append('  -H "Authorization: Bearer YOUR_API_KEY" \\')
        lines.append('  -H "Content-Type: application/json" \\')
        stream_body = json.dumps({"model": s["model"] or "gpt-4o", "messages": [{"role": "user", "content": "Hello"}], "stream": True})
        lines.append("  -d '" + stream_body + "'")
        lines.append("```\n")
    else:
        lines.append("## With webhook callback\n")
        lines.append("```bash")
        lines.append(f'curl -X {s["method"]} https://api.acedata.cloud{s["endpoint"]} \\')
        lines.append('  -H "Authorization: Bearer YOUR_API_KEY" \\')
        lines.append('  -H "Content-Type: application/json" \\')
        webhook_body = json.dumps({**s["sample_body"], "callback_url": "https://your-server.com/webhook"})
        lines.append("  -d '" + webhook_body + "'")
        lines.append("```\n")

    lines.append("## Get your API key\n")
    lines.append("1. Sign up at [platform.acedata.cloud](https://platform.acedata.cloud)")
    lines.append(f'2. Subscribe to the {s["name"]} service')
    lines.append("3. Create a credential and copy the token\n")
    lines.append("Free trial credits included.\n")
    lines.append("## Next steps\n")
    lines.append("<CardGroup cols={2}>")
    lines.append(f'<Card title="Python tutorial" href="/tutorials/{s["id"]}/python" icon="python">')
    lines.append("    Full Python integration guide.")
    lines.append("</Card>")
    lines.append(f'<Card title="JavaScript tutorial" href="/tutorials/{s["id"]}/javascript" icon="js">')
    lines.append("    Node.js and browser examples.")
    lines.append("</Card>")
    lines.append("</CardGroup>")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Template: comparison pages
# ---------------------------------------------------------------------------


def generate_comparison(comp: dict) -> str:
    aspects_rows = "\n".join(
        f"| **{name}** | {desc} |" for name, desc in comp["aspects"]
    )
    service_cards = ""
    for sid in comp.get("services", []):
        if sid in SERVICE_MAP:
            s = SERVICE_MAP[sid]
            service_cards += f"""\
        <Card title="{s['name']} tutorial" href="/tutorials/{s['id']}/python" icon="code">
            Get started with {s['name']} API.
        </Card>
        """

    return textwrap.dedent(f"""\
        ---
        title: "{comp['title']}"
        seo: "{comp['seo_title']}"
        description: "{comp['description']}"
        ---

        {comp['description']}

        ## Quick comparison

        | Aspect | Details |
        |--------|---------|
        {aspects_rows}

        ## Unified API access

        All services compared above are available through **Ace Data Cloud's unified API**. This means:

        - **One API key** for all services
        - **OpenAI-compatible format** for chat models — switch models by changing one parameter
        - **Pay-as-you-go pricing** with free trial credits
        - **No separate accounts** needed for each provider

        ## Code example

        With Ace Data Cloud, switching between models is as simple as changing the `model` parameter:

        ```python
        import requests

        API_KEY = "YOUR_API_KEY"

        def call_api(model, prompt):
            return requests.post(
                "https://api.acedata.cloud/v1/chat/completions",
                headers={{"Authorization": f"Bearer {{API_KEY}}"}},
                json={{"model": model, "messages": [{{"role": "user", "content": prompt}}]}},
            ).json()

        # Switch between providers with one line change
        result = call_api("claude-sonnet-4-20250514", "Hello!")
        result = call_api("gpt-4o", "Hello!")
        result = call_api("gemini-2.5-flash", "Hello!")
        ```

        ## Get started

        <CardGroup cols={{2}}>
        {service_cards}
        </CardGroup>

        ## Try it free

        Sign up at [platform.acedata.cloud](https://platform.acedata.cloud) and get free trial credits for every service.
    """)


# ---------------------------------------------------------------------------
# Template: use case pages
# ---------------------------------------------------------------------------


def generate_use_case(uc: dict) -> str:
    s = SERVICE_MAP.get(uc["primary_service"], SERVICES[0])
    tags_str = ", ".join(uc["tags"])

    # Generate content based on slug
    if "chatbot" in uc["slug"] and "javascript" not in uc["slug"]:
        return _generate_chatbot_python(uc, s)
    elif "chatbot" in uc["slug"] and "javascript" in uc["slug"]:
        return _generate_chatbot_javascript(uc, s)
    elif "image-generator" in uc["slug"]:
        return _generate_image_generator(uc, s)
    elif "music" in uc["slug"]:
        return _generate_music_generator(uc, s)
    elif "video" in uc["slug"]:
        return _generate_video_generator(uc, s)
    elif "search" in uc["slug"] or "serp" in uc["slug"]:
        return _generate_search_app(uc, s)
    elif "text-to-speech" in uc["slug"] or "tts" in uc["slug"]:
        return _generate_tts_app(uc, s)
    elif "telegram" in uc["slug"]:
        return _generate_telegram_bot(uc, s)
    elif "discord" in uc["slug"]:
        return _generate_discord_bot(uc, s)
    elif "saas" in uc["slug"]:
        return _generate_saas_guide(uc, s)
    elif "mcp" in uc["slug"]:
        return _generate_mcp_guide(uc, s)
    elif "qr" in uc["slug"]:
        return _generate_qr_art(uc, s)
    else:
        return _generate_generic_use_case(uc, s)


def _generate_chatbot_python(uc, s):
    return textwrap.dedent(f"""\
        ---
        title: "{uc['title']}"
        seo: "{uc['seo_title']}"
        description: "{uc['description']}"
        ---

        Build a fully functional AI chatbot in Python using Ace Data Cloud's unified API. This tutorial works with **Claude, GPT-4o, Gemini, DeepSeek**, and any other supported model.

        ## What you'll build

        A command-line chatbot that:
        - Maintains conversation history (multi-turn)
        - Supports streaming responses
        - Works with any AI model via one API

        ## Prerequisites

        ```bash
        pip install openai
        ```

        ## Complete code

        ```python
        from openai import OpenAI

        client = OpenAI(
            api_key="YOUR_API_KEY",
            base_url="https://api.acedata.cloud/v1",
        )

        def chat(model="claude-sonnet-4-20250514"):
            messages = []
            print(f"Chatbot ready ({{model}}). Type 'quit' to exit.\\n")

            while True:
                user_input = input("You: ")
                if user_input.lower() in ("quit", "exit"):
                    break

                messages.append({{"role": "user", "content": user_input}})

                stream = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=True,
                )

                print("AI: ", end="", flush=True)
                full_response = ""
                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        print(content, end="", flush=True)
                        full_response += content
                print()

                messages.append({{"role": "assistant", "content": full_response}})

        if __name__ == "__main__":
            chat()
        ```

        ## Switch models instantly

        Change the model parameter to use any provider:

        ```python
        chat("claude-sonnet-4-20250514")  # Anthropic Claude
        chat("gpt-4o")                    # OpenAI GPT-4o
        chat("gemini-2.5-flash")          # Google Gemini
        chat("deepseek-chat")             # DeepSeek
        chat("grok-3")                    # xAI Grok
        ```

        All models use the same OpenAI-compatible API format — no code changes needed.

        ## Add system prompts

        Customize your chatbot's personality:

        ```python
        messages = [
            {{
                "role": "system",
                "content": "You are a helpful coding assistant. Answer concisely with code examples.",
            }}
        ]
        ```

        ## Next steps

        <CardGroup cols={{2}}>
        <Card title="JavaScript version" href="/use-cases/ai-chatbot-javascript" icon="js">
            Build the same chatbot in JavaScript.
        </Card>
        <Card title="Telegram bot" href="/use-cases/telegram-ai-bot" icon="paper-plane">
            Deploy your chatbot to Telegram.
        </Card>
        <Card title="Compare models" href="/comparisons/claude-vs-openai" icon="scale-balanced">
            Claude vs OpenAI — which to choose?
        </Card>
        <Card title="API reference" href="/api-reference/claude" icon="code">
            Full Claude API specification.
        </Card>
        </CardGroup>
    """)


def _generate_chatbot_javascript(uc, s):
    return textwrap.dedent(f"""\
        ---
        title: "{uc['title']}"
        seo: "{uc['seo_title']}"
        description: "{uc['description']}"
        ---

        Build an AI chatbot using JavaScript and Node.js. Works with **Claude, GPT, Gemini**, and all models on Ace Data Cloud.

        ## Prerequisites

        ```bash
        npm install openai readline
        ```

        ## Complete code

        ```javascript
        import OpenAI from "openai";
        import * as readline from "readline";

        const client = new OpenAI({{
          apiKey: "YOUR_API_KEY",
          baseURL: "https://api.acedata.cloud/v1",
        }});

        const rl = readline.createInterface({{
          input: process.stdin,
          output: process.stdout,
        }});

        const messages = [];

        async function chat() {{
          console.log("Chatbot ready. Type 'quit' to exit.\\n");

          const askQuestion = () => {{
            rl.question("You: ", async (input) => {{
              if (input.toLowerCase() === "quit") {{
                rl.close();
                return;
              }}

              messages.push({{ role: "user", content: input }});

              const stream = await client.chat.completions.create({{
                model: "gpt-4o",
                messages,
                stream: true,
              }});

              process.stdout.write("AI: ");
              let fullResponse = "";

              for await (const chunk of stream) {{
                const content = chunk.choices[0]?.delta?.content || "";
                process.stdout.write(content);
                fullResponse += content;
              }}
              console.log();

              messages.push({{ role: "assistant", content: fullResponse }});
              askQuestion();
            }});
          }};

          askQuestion();
        }}

        chat();
        ```

        ## Switch between models

        ```javascript
        // Just change the model string — same code, same API
        const stream = await client.chat.completions.create({{
          model: "claude-sonnet-4-20250514", // or "gpt-4o", "gemini-2.5-flash"
          messages,
          stream: true,
        }});
        ```

        ## Next steps

        <CardGroup cols={{2}}>
        <Card title="Python version" href="/use-cases/ai-chatbot" icon="python">
            Build the same chatbot in Python.
        </Card>
        <Card title="Discord bot" href="/use-cases/discord-ai-bot" icon="discord">
            Deploy to Discord.
        </Card>
        </CardGroup>
    """)


def _generate_image_generator(uc, s):
    return textwrap.dedent(f"""\
        ---
        title: "{uc['title']}"
        seo: "{uc['seo_title']}"
        description: "{uc['description']}"
        ---

        Build an AI image generator using the Midjourney API through Ace Data Cloud.

        ## What you'll build

        A Python application that can:
        - Generate images from text prompts
        - Upscale images to high resolution
        - Create variations of generated images
        - Handle async generation with webhooks

        ## Quick start

        ```python
        import requests
        import time

        API_KEY = "YOUR_API_KEY"
        BASE_URL = "https://api.acedata.cloud"

        # Generate an image
        response = requests.post(
            f"{{BASE_URL}}/midjourney/imagine",
            headers={{"Authorization": f"Bearer {{API_KEY}}"}},
            json={{
                "prompt": "A futuristic city at sunset, cyberpunk style --ar 16:9",
                "mode": "fast",
            }},
        )

        result = response.json()
        print("Image URL:", result["image_url"])
        print("Actions available:", result["actions"])
        ```

        ## Upscale an image

        After generating, upscale for higher resolution:

        ```python
        # Get the image_id from the generation response
        image_id = result["image_id"]

        upscale = requests.post(
            f"{{BASE_URL}}/midjourney/imagine",
            headers={{"Authorization": f"Bearer {{API_KEY}}"}},
            json={{
                "image_id": image_id,
                "action": "upscale",
                "index": 1,  # Upscale first image (1-4)
            }},
        )

        upscaled = upscale.json()
        print("Upscaled URL:", upscaled["image_url"])
        ```

        ## Alternative: Use Flux for faster generation

        For rapid prototyping, Flux generates images in seconds:

        ```python
        response = requests.post(
            f"{{BASE_URL}}/flux/images",
            headers={{"Authorization": f"Bearer {{API_KEY}}"}},
            json={{
                "model": "flux-schnell",
                "prompt": "A serene mountain landscape",
            }},
        )
        ```

        ## Next steps

        <CardGroup cols={{2}}>
        <Card title="Midjourney guide" href="/guides/midjourney/midjourney_imagine" icon="image">
            Advanced Midjourney features.
        </Card>
        <Card title="Compare image APIs" href="/comparisons/best-ai-image-apis" icon="scale-balanced">
            Midjourney vs Flux vs Seedream.
        </Card>
        </CardGroup>
    """)


def _generate_music_generator(uc, s):
    return textwrap.dedent(f"""\
        ---
        title: "{uc['title']}"
        seo: "{uc['seo_title']}"
        description: "{uc['description']}"
        ---

        Generate AI music tracks using the Suno API through Ace Data Cloud.

        ## Quick start

        ```python
        import requests

        API_KEY = "YOUR_API_KEY"

        # Generate a song from a text prompt
        response = requests.post(
            "https://api.acedata.cloud/suno/audios",
            headers={{"Authorization": f"Bearer {{API_KEY}}"}},
            json={{
                "prompt": "An upbeat pop song about summer adventures",
                "model": "chirp-v4",
                "action": "generate",
            }},
        )

        songs = response.json()["data"]
        for song in songs:
            print(f"Title: {{song['title']}}")
            print(f"Audio: {{song['audio_url']}}")
            print(f"Duration: {{song['duration']}}s")
        ```

        ## Custom lyrics and style

        ```python
        response = requests.post(
            "https://api.acedata.cloud/suno/audios",
            headers={{"Authorization": f"Bearer {{API_KEY}}"}},
            json={{
                "model": "chirp-v4",
                "custom": True,
                "action": "generate",
                "title": "Summer Dreams",
                "style": "pop, upbeat, energetic",
                "lyric": "[Verse]\\nSunshine on my face\\nRunning through the waves\\n\\n[Chorus]\\nSummer dreams are calling me",
            }},
        )
        ```

        ## Extend a song

        Continue an existing song from a specific point:

        ```python
        response = requests.post(
            "https://api.acedata.cloud/suno/audios",
            headers={{"Authorization": f"Bearer {{API_KEY}}"}},
            json={{
                "model": "chirp-v4",
                "action": "extend",
                "audio_id": "SONG_ID_HERE",
                "continue_at": 120,  # Continue from 2 minutes
            }},
        )
        ```

        ## Available actions

        | Action | Description |
        |--------|-------------|
        | `generate` | Create new songs from prompt |
        | `extend` | Continue an existing song |
        | `cover` | Create a cover in a different style |
        | `stems` | Separate vocals and instruments |
        | `mashup` | Combine multiple songs |
        | `remaster` | Enhance audio quality |

        ## Next steps

        <CardGroup cols={{2}}>
        <Card title="Full Suno guide" href="/guides/suno/suno_audios" icon="music">
            All Suno features in detail.
        </Card>
        <Card title="Compare music APIs" href="/comparisons/suno-vs-udio" icon="scale-balanced">
            Suno vs Udio comparison.
        </Card>
        </CardGroup>
    """)


def _generate_video_generator(uc, s):
    return textwrap.dedent(f"""\
        ---
        title: "{uc['title']}"
        seo: "{uc['seo_title']}"
        description: "{uc['description']}"
        ---

        Generate AI videos using OpenAI's Sora API through Ace Data Cloud.

        ## Quick start

        ```python
        import requests

        API_KEY = "YOUR_API_KEY"

        # Generate a video
        response = requests.post(
            "https://api.acedata.cloud/sora/videos",
            headers={{
                "Authorization": f"Bearer {{API_KEY}}",
                "Content-Type": "application/json",
            }},
            json={{
                "model": "sora-2",
                "prompt": "A cat playing piano in a jazz club, cinematic lighting",
                "duration": 10,
            }},
        )

        result = response.json()
        if result.get("task_id"):
            print("Task submitted:", result["task_id"])
            # Video generation takes 1-5 minutes
        ```

        ## Check task status

        ```python
        task_id = result["task_id"]

        status = requests.get(
            f"https://api.acedata.cloud/sora/tasks/{{task_id}}",
            headers={{"Authorization": f"Bearer {{API_KEY}}"}},
        )

        task = status.json()
        if task["state"] == "succeeded":
            print("Video URL:", task["video_url"])
        else:
            print("Status:", task["state"])
        ```

        ## Use webhooks for async processing

        ```python
        response = requests.post(
            "https://api.acedata.cloud/sora/videos",
            headers={{"Authorization": f"Bearer {{API_KEY}}"}},
            json={{
                "model": "sora-2",
                "prompt": "Ocean waves at sunset",
                "callback_url": "https://your-server.com/webhook",
            }},
        )
        # Results will be POSTed to your callback_url
        ```

        ## Alternative video APIs

        | API | Best for | Speed |
        |-----|----------|-------|
        | Sora | Cinematic quality | 2-5 min |
        | Veo | Audio + video | 1-3 min |
        | Luma | Fast creative videos | 30s-2min |
        | Kling | Motion control | 1-3 min |

        ## Next steps

        <CardGroup cols={{2}}>
        <Card title="Full Sora guide" href="/guides/sora/sora_videos" icon="video">
            Advanced Sora features.
        </Card>
        <Card title="Compare video APIs" href="/comparisons/best-ai-video-apis" icon="scale-balanced">
            Sora vs Veo vs Luma vs Kling.
        </Card>
        </CardGroup>
    """)


def _generate_search_app(uc, s):
    return textwrap.dedent(f"""\
        ---
        title: "{uc['title']}"
        seo: "{uc['seo_title']}"
        description: "{uc['description']}"
        ---

        Access Google search results programmatically using the SERP API.

        ## Quick start

        ```python
        import requests

        API_KEY = "YOUR_API_KEY"

        response = requests.post(
            "https://api.acedata.cloud/serp/google",
            headers={{"Authorization": f"Bearer {{API_KEY}}"}},
            json={{
                "type": "search",
                "query": "best AI APIs 2026",
                "number": 10,
            }},
        )

        results = response.json()
        for item in results.get("organic_results", []):
            print(f"{{item['title']}} - {{item['link']}}")
        ```

        ## Search types

        | Type | Description |
        |------|-------------|
        | `search` | Standard web search results |
        | `images` | Image search results |
        | `news` | News articles |
        | `shopping` | Product listings |
        | `videos` | Video results |
        | `maps` | Location results |

        ## Filtering by location and language

        ```python
        response = requests.post(
            "https://api.acedata.cloud/serp/google",
            headers={{"Authorization": f"Bearer {{API_KEY}}"}},
            json={{
                "type": "search",
                "query": "AI startups",
                "country": "US",
                "language": "en",
                "range": "month",  # Results from past month
            }},
        )
        ```

        ## Next steps

        <CardGroup cols={{2}}>
        <Card title="Full SERP guide" href="/guides/serp/serp_google" icon="magnifying-glass">
            Image search, news, and more.
        </Card>
        <Card title="API reference" href="/api-reference/serp" icon="code">
            Complete SERP API specification.
        </Card>
        </CardGroup>
    """)


def _generate_tts_app(uc, s):
    return textwrap.dedent(f"""\
        ---
        title: "{uc['title']}"
        seo: "{uc['seo_title']}"
        description: "{uc['description']}"
        ---

        Build a text-to-speech application using Fish Audio API with voice cloning support.

        ## Quick start

        ```python
        import requests

        API_KEY = "YOUR_API_KEY"

        response = requests.post(
            "https://api.acedata.cloud/fish/audios",
            headers={{"Authorization": f"Bearer {{API_KEY}}"}},
            json={{
                "text": "Welcome to Ace Data Cloud, your unified AI API platform.",
                "reference_id": "default",
            }},
        )

        result = response.json()
        print("Audio URL:", result.get("audio_url"))
        ```

        ## Custom voice

        Clone voices or use preset voices:

        ```python
        # List available voices
        voices = requests.get(
            "https://api.acedata.cloud/fish/voices",
            headers={{"Authorization": f"Bearer {{API_KEY}}"}},
        ).json()

        # Use a specific voice
        response = requests.post(
            "https://api.acedata.cloud/fish/audios",
            headers={{"Authorization": f"Bearer {{API_KEY}}"}},
            json={{
                "text": "Your custom text here.",
                "reference_id": voices["data"][0]["id"],
            }},
        )
        ```

        ## Next steps

        <CardGroup cols={{2}}>
        <Card title="Full Fish Audio guide" href="/guides/fish/fish_audios" icon="microphone">
            Voice cloning and advanced features.
        </Card>
        <Card title="API reference" href="/api-reference/fish" icon="code">
            Complete API specification.
        </Card>
        </CardGroup>
    """)


def _generate_telegram_bot(uc, s):
    return textwrap.dedent(f"""\
        ---
        title: "{uc['title']}"
        seo: "{uc['seo_title']}"
        description: "{uc['description']}"
        ---

        Build a Telegram bot powered by AI (Claude, GPT, Gemini) using Python.

        ## Prerequisites

        ```bash
        pip install python-telegram-bot openai
        ```

        ## Complete code

        ```python
        from telegram import Update
        from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
        from openai import OpenAI

        TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
        client = OpenAI(
            api_key="YOUR_ACEDATA_API_KEY",
            base_url="https://api.acedata.cloud/v1",
        )

        async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
            await update.message.reply_text("Hi! I'm an AI bot. Send me a message!")

        async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user_message = update.message.text

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{{"role": "user", "content": user_message}}],
            )

            reply = response.choices[0].message.content
            await update.message.reply_text(reply)

        def main():
            app = Application.builder().token(TELEGRAM_TOKEN).build()
            app.add_handler(CommandHandler("start", start))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
            app.run_polling()

        if __name__ == "__main__":
            main()
        ```

        ## Add conversation memory

        ```python
        # Store conversation per user
        conversations = {{}}

        async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user_id = update.effective_user.id
            if user_id not in conversations:
                conversations[user_id] = []

            conversations[user_id].append({{
                "role": "user",
                "content": update.message.text,
            }})

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=conversations[user_id],
            )

            reply = response.choices[0].message.content
            conversations[user_id].append({{"role": "assistant", "content": reply}})
            await update.message.reply_text(reply)
        ```

        ## Next steps

        <CardGroup cols={{2}}>
        <Card title="Discord bot" href="/use-cases/discord-ai-bot" icon="discord">
            Build a Discord bot instead.
        </Card>
        <Card title="Python chatbot" href="/use-cases/ai-chatbot" icon="python">
            CLI chatbot tutorial.
        </Card>
        </CardGroup>
    """)


def _generate_discord_bot(uc, s):
    return textwrap.dedent(f"""\
        ---
        title: "{uc['title']}"
        seo: "{uc['seo_title']}"
        description: "{uc['description']}"
        ---

        Build a Discord bot with AI chat, image generation, and music creation.

        ## Prerequisites

        ```bash
        npm install discord.js openai
        ```

        ## Basic AI chat bot

        ```javascript
        import {{ Client, GatewayIntentBits }} from "discord.js";
        import OpenAI from "openai";

        const client = new Client({{
          intents: [
            GatewayIntentBits.Guilds,
            GatewayIntentBits.GuildMessages,
            GatewayIntentBits.MessageContent,
          ],
        }});

        const ai = new OpenAI({{
          apiKey: "YOUR_ACEDATA_API_KEY",
          baseURL: "https://api.acedata.cloud/v1",
        }});

        client.on("messageCreate", async (message) => {{
          if (message.author.bot) return;
          if (!message.content.startsWith("!ai ")) return;

          const prompt = message.content.slice(4);

          const response = await ai.chat.completions.create({{
            model: "gpt-4o",
            messages: [{{ role: "user", content: prompt }}],
          }});

          await message.reply(response.choices[0].message.content);
        }});

        client.login("YOUR_DISCORD_BOT_TOKEN");
        ```

        ## Add image generation

        ```javascript
        client.on("messageCreate", async (message) => {{
          if (message.content.startsWith("!image ")) {{
            const prompt = message.content.slice(7);
            await message.reply("Generating image...");

            const response = await fetch("https://api.acedata.cloud/flux/images", {{
              method: "POST",
              headers: {{
                Authorization: "Bearer YOUR_ACEDATA_API_KEY",
                "Content-Type": "application/json",
              }},
              body: JSON.stringify({{ model: "flux-schnell", prompt }}),
            }});

            const result = await response.json();
            await message.reply(result.data?.[0]?.url || "Failed to generate image");
          }}
        }});
        ```

        ## Next steps

        <CardGroup cols={{2}}>
        <Card title="Telegram bot" href="/use-cases/telegram-ai-bot" icon="paper-plane">
            Build a Telegram bot instead.
        </Card>
        <Card title="Compare LLMs" href="/comparisons/claude-vs-openai" icon="scale-balanced">
            Choose the best model.
        </Card>
        </CardGroup>
    """)


def _generate_saas_guide(uc, s):
    return textwrap.dedent(f"""\
        ---
        title: "{uc['title']}"
        seo: "{uc['seo_title']}"
        description: "{uc['description']}"
        ---

        Architecture guide for building an AI SaaS application using Ace Data Cloud as your AI backend.

        ## Why use a unified API

        Instead of managing separate API keys and SDKs for each AI provider, Ace Data Cloud gives you:

        - **One API key** for 50+ AI models and services
        - **OpenAI-compatible format** — use existing SDKs
        - **Pay-as-you-go** — no minimum commitments
        - **Built-in rate limiting and error handling**

        ## Recommended architecture

        ```
        Your SaaS App
            │
            ├── Frontend (React/Vue/Next.js)
            │
            ├── Backend (Node.js/Python/Go)
            │   ├── User auth & billing
            │   ├── AI request routing
            │   └── Response caching
            │
            └── Ace Data Cloud API
                ├── Chat (Claude/GPT/Gemini)
                ├── Images (Midjourney/Flux)
                ├── Video (Sora/Veo/Luma)
                ├── Audio (Suno/Fish)
                └── Search (Google SERP)
        ```

        ## Key integration patterns

        ### 1. Model routing

        Let users choose their preferred model:

        ```python
        from openai import OpenAI

        client = OpenAI(
            api_key="YOUR_KEY",
            base_url="https://api.acedata.cloud/v1",
        )

        def generate_response(user_model_preference, messages):
            return client.chat.completions.create(
                model=user_model_preference,  # User's choice
                messages=messages,
                stream=True,
            )
        ```

        ### 2. Fallback chains

        If one model fails, try another:

        ```python
        FALLBACK_MODELS = ["claude-sonnet-4-20250514", "gpt-4o", "gemini-2.5-flash"]

        def generate_with_fallback(messages):
            for model in FALLBACK_MODELS:
                try:
                    return client.chat.completions.create(
                        model=model,
                        messages=messages,
                    )
                except Exception:
                    continue
            raise Exception("All models failed")
        ```

        ### 3. Cost optimization

        Route to cheaper models for simple tasks:

        ```python
        def smart_route(messages, task_complexity="simple"):
            if task_complexity == "simple":
                model = "deepseek-chat"       # Most cost-effective
            elif task_complexity == "medium":
                model = "gpt-4o-mini"         # Good balance
            else:
                model = "claude-sonnet-4-20250514"  # Best quality

            return client.chat.completions.create(model=model, messages=messages)
        ```

        ## Next steps

        <CardGroup cols={{2}}>
        <Card title="Authentication" href="/authentication" icon="lock">
            API key management.
        </Card>
        <Card title="Pricing comparison" href="/comparisons/claude-vs-openai" icon="scale-balanced">
            Compare model costs.
        </Card>
        </CardGroup>
    """)


def _generate_mcp_guide(uc, s):
    return textwrap.dedent(f"""\
        ---
        title: "{uc['title']}"
        seo: "{uc['seo_title']}"
        description: "{uc['description']}"
        ---

        Set up MCP (Model Context Protocol) servers to give Claude Desktop access to AI music, video, image, and search tools.

        ## What are MCP servers?

        MCP servers let AI assistants like Claude call external tools. With Ace Data Cloud's MCP servers, Claude can:

        - Generate music with **Suno**
        - Create videos with **Sora**, **Veo**, **Luma**
        - Generate images with **Midjourney**, **Nano Banana**
        - Search the web with **Google SERP**

        ## Setup

        ### 1. Install MCP servers

        ```bash
        pip install mcp-suno mcp-serp mcp-midjourney mcp-luma mcp-sora mcp-veo
        ```

        ### 2. Get your API key

        Sign up at [platform.acedata.cloud](https://platform.acedata.cloud) and get your Bearer token.

        ### 3. Configure Claude Desktop

        Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

        ```json
        {{
          "mcpServers": {{
            "suno": {{
              "command": "mcp-suno",
              "env": {{
                "ACEDATACLOUD_API_TOKEN": "YOUR_API_KEY"
              }}
            }},
            "search": {{
              "command": "mcp-serp",
              "env": {{
                "ACEDATACLOUD_API_TOKEN": "YOUR_API_KEY"
              }}
            }},
            "midjourney": {{
              "command": "mcp-midjourney",
              "env": {{
                "ACEDATACLOUD_API_TOKEN": "YOUR_API_KEY"
              }}
            }},
            "sora": {{
              "command": "mcp-sora",
              "env": {{
                "ACEDATACLOUD_API_TOKEN": "YOUR_API_KEY"
              }}
            }}
          }}
        }}
        ```

        ### 4. Restart Claude Desktop

        After saving the config, restart Claude Desktop. You'll see the tools icon (🔨) in the chat input.

        ## Example prompts

        - "Generate a jazz song about rainy days"
        - "Create a video of a cat playing piano"
        - "Search for the latest AI news"
        - "Generate an image of a futuristic city"

        ## Available MCP servers

        | Server | PyPI | Features |
        |--------|------|----------|
        | mcp-suno | [PyPI](https://pypi.org/project/mcp-suno/) | Music generation, lyrics, covers, stems |
        | mcp-serp | [PyPI](https://pypi.org/project/mcp-serp/) | Google search (web, images, news) |
        | mcp-midjourney | GitHub | Image generation, upscale, variations |
        | mcp-luma | GitHub | Video generation (Dream Machine) |
        | mcp-sora | GitHub | Video generation (OpenAI Sora) |
        | mcp-veo | GitHub | Video generation (Google Veo) |

        ## Next steps

        <CardGroup cols={{2}}>
        <Card title="MCP overview" href="/mcp/overview" icon="puzzle-piece">
            Full MCP documentation.
        </Card>
        <Card title="Suno MCP" href="/mcp/suno" icon="music">
            Detailed Suno MCP guide.
        </Card>
        </CardGroup>
    """)


def _generate_qr_art(uc, s):
    return textwrap.dedent(f"""\
        ---
        title: "{uc['title']}"
        seo: "{uc['seo_title']}"
        description: "{uc['description']}"
        ---

        Create stunning AI-enhanced QR codes for marketing, branding, and creative projects.

        ## Quick start

        ```python
        import requests

        API_KEY = "YOUR_API_KEY"

        response = requests.post(
            "https://api.acedata.cloud/qrart/generate",
            headers={{"Authorization": f"Bearer {{API_KEY}}"}},
            json={{
                "content": "https://acedata.cloud",
                "prompt": "A beautiful garden with flowers, watercolor style",
            }},
        )

        result = response.json()
        print("QR Art URL:", result.get("image_url"))
        ```

        ## Use cases

        - **Marketing campaigns** — Branded QR codes on flyers and ads
        - **Business cards** — Artistic QR codes that stand out
        - **Product packaging** — Beautiful scannable codes
        - **Event invitations** — Custom-themed QR codes

        ## Next steps

        <CardGroup cols={{2}}>
        <Card title="QR Art guide" href="/guides/qrart/qrart_generate" icon="qrcode">
            Advanced QR Art features.
        </Card>
        <Card title="API reference" href="/api-reference/qrart" icon="code">
            Full API specification.
        </Card>
        </CardGroup>
    """)


def _generate_generic_use_case(uc, s):
    return textwrap.dedent(f"""\
        ---
        title: "{uc['title']}"
        seo: "{uc['seo_title']}"
        description: "{uc['description']}"
        ---

        {uc['description']}

        ## Quick start

        ```python
        import requests

        API_KEY = "YOUR_API_KEY"

        response = requests.post(
            "https://api.acedata.cloud{s['endpoint']}",
            headers={{"Authorization": f"Bearer {{API_KEY}}"}},
            json={json.dumps(s['sample_body'], indent=2)},
        )

        print(response.json())
        ```

        ## Next steps

        <CardGroup cols={{2}}>
        <Card title="Full guide" href="/{s['guide_path']}" icon="book">
            Detailed guide with examples.
        </Card>
        <Card title="API reference" href="/{s['api_ref_path']}" icon="code">
            Complete API specification.
        </Card>
        </CardGroup>
    """)


# ---------------------------------------------------------------------------
# Template: blog articles
# ---------------------------------------------------------------------------


def generate_blog_article(article: dict) -> str:
    a = article
    if a["slug"] == "unified-ai-api-platform":
        return _blog_unified_platform(a)
    elif a["slug"] == "openai-compatible-api":
        return _blog_openai_compatible(a)
    elif a["slug"] == "best-ai-apis-2026":
        return _blog_best_ai_apis(a)
    elif a["slug"] == "ai-api-pricing-comparison":
        return _blog_pricing_comparison(a)
    elif a["slug"] == "mcp-servers-guide":
        return _blog_mcp_servers(a)
    elif a["slug"] == "ai-video-generation-guide":
        return _blog_video_generation(a)
    elif a["slug"] == "suno-api-music-generation":
        return _blog_suno_music(a)
    elif a["slug"] == "midjourney-api-guide":
        return _blog_midjourney(a)
    else:
        return _blog_generic(a)


def _blog_unified_platform(a):
    return textwrap.dedent(f"""\
        ---
        title: "{a['title']}"
        seo: "{a['seo_title']}"
        description: "{a['description']}"
        ---

        Building AI products in 2026 means juggling dozens of APIs: OpenAI for chat, Anthropic for Claude, Google for Gemini, Midjourney for images, Suno for music, Sora for video. Each has its own authentication, billing, SDK, rate limits, and error formats.

        **A unified AI API platform solves this.**

        ## The problem

        A typical AI application needs:

        | Service | Provider | SDK | Auth |
        |---------|----------|-----|------|
        | Chat | OpenAI | openai-python | API key |
        | Chat | Anthropic | anthropic-python | API key |
        | Chat | Google | google-genai | OAuth/API key |
        | Images | Midjourney | None (Discord) | Discord token |
        | Video | Sora | openai-python | API key |
        | Music | Suno | None (web only) | Cookies |
        | Search | Google | SerpAPI | API key |

        That's **7 different API keys**, 5 SDKs, and 7 billing accounts to manage.

        ## The solution

        With Ace Data Cloud, you get **one API key** for all of these:

        ```python
        from openai import OpenAI

        client = OpenAI(
            api_key="ONE_KEY_FOR_EVERYTHING",
            base_url="https://api.acedata.cloud/v1",
        )

        # Claude
        client.chat.completions.create(model="claude-sonnet-4-20250514", ...)

        # GPT-4o
        client.chat.completions.create(model="gpt-4o", ...)

        # Gemini
        client.chat.completions.create(model="gemini-2.5-flash", ...)
        ```

        ## Benefits

        1. **Single billing** — One invoice, one credit balance
        2. **Unified format** — OpenAI-compatible for all chat models
        3. **No SDK overhead** — Use `requests` or `openai` SDK for everything
        4. **Free trial** — Credits for every service, no credit card required
        5. **Global availability** — No geo-restrictions on any model

        ## Get started

        Sign up at [platform.acedata.cloud](https://platform.acedata.cloud) and start building with 50+ AI models today.
    """)


def _blog_openai_compatible(a):
    return textwrap.dedent(f"""\
        ---
        title: "{a['title']}"
        seo: "{a['seo_title']}"
        description: "{a['description']}"
        ---

        The OpenAI SDK (`openai` for Python, `openai` for Node.js) is the most widely used AI SDK in the world. With Ace Data Cloud, you can use this same SDK to access **Claude, Gemini, DeepSeek, Grok**, and 50+ other models.

        ## How it works

        Just change the `base_url`:

        ```python
        from openai import OpenAI

        # Instead of pointing to api.openai.com...
        client = OpenAI(
            api_key="YOUR_ACEDATA_KEY",
            base_url="https://api.acedata.cloud/v1",  # ← This is the only change
        )

        # Now use ANY model
        response = client.chat.completions.create(
            model="claude-sonnet-4-20250514",  # Anthropic Claude
            messages=[{{"role": "user", "content": "Hello!"}}],
        )
        ```

        ## Supported models

        | Provider | Models |
        |----------|--------|
        | Anthropic | Claude Opus 4, Claude Sonnet 4, Claude Haiku |
        | OpenAI | GPT-4o, GPT-4.1, o3, o4-mini |
        | Google | Gemini 2.5 Pro, Gemini 2.5 Flash |
        | DeepSeek | DeepSeek-V3, DeepSeek-R1 |
        | xAI | Grok-3, Grok-3-mini |

        ## JavaScript

        ```javascript
        import OpenAI from "openai";

        const client = new OpenAI({{
          apiKey: "YOUR_ACEDATA_KEY",
          baseURL: "https://api.acedata.cloud/v1",
        }});

        const response = await client.chat.completions.create({{
          model: "gemini-2.5-flash",
          messages: [{{ role: "user", content: "Hello!" }}],
        }});
        ```

        ## cURL

        ```bash
        curl https://api.acedata.cloud/v1/chat/completions \\
          -H "Authorization: Bearer YOUR_ACEDATA_KEY" \\
          -H "Content-Type: application/json" \\
          -d '{{"model": "deepseek-chat", "messages": [{{"role": "user", "content": "Hello!"}}]}}'
        ```

        ## Get started

        [Sign up free](https://platform.acedata.cloud) → get your API key → use the OpenAI SDK with any model.
    """)


def _blog_best_ai_apis(a):
    return textwrap.dedent(f"""\
        ---
        title: "{a['title']}"
        seo: "{a['seo_title']}"
        description: "{a['description']}"
        ---

        A comprehensive guide to the best AI APIs available in 2026, organized by category.

        ## AI Chat & LLM APIs

        | API | Provider | Best for |
        |-----|----------|----------|
        | Claude | Anthropic | Code generation, analysis, long context |
        | GPT-4o | OpenAI | General purpose, vision, image generation |
        | Gemini 2.5 | Google | Multimodal, long context (1M tokens) |
        | DeepSeek | DeepSeek | Cost-effective coding and reasoning |
        | Grok | xAI | Real-time knowledge, witty responses |

        ## AI Image Generation APIs

        | API | Provider | Best for |
        |-----|----------|----------|
        | Midjourney | Midjourney | Artistic, marketing-quality images |
        | Flux | Black Forest Labs | Fast generation, batch processing |
        | Seedream | ByteDance | Photorealism, text rendering |
        | Nano Banana | Google Gemini | Image editing, iterative refinement |

        ## AI Video Generation APIs

        | API | Provider | Best for |
        |-----|----------|----------|
        | Sora | OpenAI | Cinematic quality, long duration |
        | Veo 3 | Google | Video + audio generation |
        | Luma | Luma AI | Fast creative videos |
        | Kling | Kuaishou | Motion control |
        | Hailuo | MiniMax | Director mode |
        | Seedance | ByteDance | Dance and motion |

        ## AI Music Generation APIs

        | API | Provider | Best for |
        |-----|----------|----------|
        | Suno | Suno AI | Full-song generation, covers, stems |
        | Fish Audio | Fish Audio | Text-to-speech, voice cloning |
        | Riffusion | Riffusion | Real-time music |

        ## Web & Data APIs

        | API | Provider | Best for |
        |-----|----------|----------|
        | Google SERP | Google | Web search, images, news |

        ## Access all APIs with one key

        All services listed above are available through [Ace Data Cloud](https://platform.acedata.cloud) — one API key, one billing account, OpenAI-compatible format for all chat models.
    """)


def _blog_pricing_comparison(a):
    return textwrap.dedent(f"""\
        ---
        title: "{a['title']}"
        seo: "{a['seo_title']}"
        description: "{a['description']}"
        ---

        Compare the pricing of major AI chat APIs to find the best value for your use case.

        ## Pricing overview

        All prices below reflect Ace Data Cloud's pay-as-you-go rates. No minimum commitment, free trial included.

        | Model | Input (per 1M tokens) | Output (per 1M tokens) | Best for |
        |-------|----------------------|------------------------|----------|
        | GPT-4o | $2.50 | $10.00 | General purpose |
        | GPT-4o mini | $0.15 | $0.60 | Cost-sensitive apps |
        | Claude Sonnet 4 | $3.00 | $15.00 | Code + analysis |
        | Claude Haiku | $0.25 | $1.25 | Fast, cheap |
        | Gemini 2.5 Flash | $0.15 | $0.60 | Budget multimodal |
        | DeepSeek Chat | $0.14 | $0.28 | Most cost-effective |
        | Grok 3 | $3.00 | $15.00 | Real-time knowledge |

        *Pricing is approximate and subject to change. Check [platform.acedata.cloud](https://platform.acedata.cloud) for current rates.*

        ## Cost optimization tips

        1. **Use cheap models for simple tasks** — GPT-4o mini or DeepSeek for basic Q&A
        2. **Stream responses** — Better UX without extra cost
        3. **Cache frequent queries** — Reduce API calls for common questions
        4. **Use shorter system prompts** — Input tokens add up quickly
        5. **Set `max_tokens`** — Prevent unexpectedly long responses

        ## Get started

        [Sign up free](https://platform.acedata.cloud) and get trial credits for every model.
    """)


def _blog_mcp_servers(a):
    return textwrap.dedent(f"""\
        ---
        title: "{a['title']}"
        seo: "{a['seo_title']}"
        description: "{a['description']}"
        ---

        MCP (Model Context Protocol) is an open protocol by Anthropic that lets AI assistants use external tools. Think of it as "plugins for AI" — but standardized and open source.

        ## How MCP works

        ```
        AI Assistant (Claude, GPT, etc.)
            │
            ├── MCP Client (built into Claude Desktop, VS Code, Cursor)
            │
            └── MCP Server (your tool)
                ├── list_tools()     → Tell the AI what you can do
                ├── call_tool()      → Execute when the AI requests
                └── get_prompt()     → Provide context/instructions
        ```

        ## Available MCP servers

        Ace Data Cloud publishes open-source MCP servers for:

        | Server | Install | Use case |
        |--------|---------|----------|
        | [mcp-suno](https://pypi.org/project/mcp-suno/) | `pip install mcp-suno` | AI music generation |
        | [mcp-serp](https://pypi.org/project/mcp-serp/) | `pip install mcp-serp` | Google search |
        | mcp-midjourney | GitHub | AI image generation |
        | mcp-luma | GitHub | AI video (Dream Machine) |
        | mcp-sora | GitHub | AI video (OpenAI Sora) |
        | mcp-veo | GitHub | AI video (Google Veo) |
        | mcp-nanobanana | GitHub | AI image editing (Gemini) |

        ## Quick setup

        ```bash
        # Install
        pip install mcp-suno mcp-serp

        # Set your API key
        export ACEDATACLOUD_API_TOKEN="your_key_here"

        # Run (stdio mode for Claude Desktop)
        mcp-suno
        ```

        ## Learn more

        - [MCP overview](/mcp/overview) — Full documentation
        - [Claude Desktop setup](/use-cases/mcp-claude-desktop) — Step-by-step guide
        - [Model Context Protocol spec](https://modelcontextprotocol.io) — Official documentation
    """)


def _blog_video_generation(a):
    return textwrap.dedent(f"""\
        ---
        title: "{a['title']}"
        seo: "{a['seo_title']}"
        description: "{a['description']}"
        ---

        AI video generation has exploded in 2026. Here's everything developers need to know about the available APIs.

        ## The landscape

        | API | Provider | Max duration | Audio | Pricing |
        |-----|----------|-------------|-------|---------|
        | Sora | OpenAI | 25s | No | Premium |
        | Veo 3 | Google | 8s | Yes (native) | Mid-range |
        | Luma | Luma AI | 10s | No | Budget |
        | Kling | Kuaishou | 10s | No | Mid-range |
        | Hailuo | MiniMax | 6s | No | Budget |
        | Seedance | ByteDance | 10s | Yes | Mid-range |

        ## Getting started

        All video APIs on Ace Data Cloud follow the same pattern:

        1. **Submit** a generation request → get a `task_id`
        2. **Poll** the task endpoint or use a **webhook**
        3. **Download** the video when ready

        ```python
        import requests
        import time

        API_KEY = "YOUR_API_KEY"

        # Submit
        r = requests.post(
            "https://api.acedata.cloud/sora/videos",
            headers={{"Authorization": f"Bearer {{API_KEY}}"}},
            json={{"model": "sora-2", "prompt": "A timelapse of clouds", "duration": 10}},
        )
        task_id = r.json()["task_id"]

        # Poll
        while True:
            status = requests.get(
                f"https://api.acedata.cloud/sora/tasks/{{task_id}}",
                headers={{"Authorization": f"Bearer {{API_KEY}}"}},
            ).json()
            if status["state"] == "succeeded":
                print("Video:", status["video_url"])
                break
            time.sleep(10)
        ```

        ## Choosing the right API

        - **Highest quality:** Sora (sora-2-pro)
        - **Fastest:** Luma (ray-2-flash)
        - **With audio:** Veo 3 or Seedance
        - **Best control:** Kling (motion brush)
        - **Cheapest:** Hailuo

        ## Try them all

        [Sign up](https://platform.acedata.cloud) for free trial credits and test every video API.
    """)


def _blog_suno_music(a):
    return textwrap.dedent(f"""\
        ---
        title: "{a['title']}"
        seo: "{a['seo_title']}"
        description: "{a['description']}"
        ---

        Suno is the leading AI music generation platform, and it's available as an API through Ace Data Cloud. Here's a complete guide.

        ## What Suno can do

        - **Generate songs** from text prompts (up to 9 minutes)
        - **Custom lyrics** with full control over title, style, and structure
        - **Extend** existing songs from any point
        - **Cover** songs in different styles
        - **Separate stems** (vocals, drums, bass, etc.)
        - **Mashup** multiple songs
        - **Remaster** for improved audio quality

        ## Quick start

        ```python
        import requests

        response = requests.post(
            "https://api.acedata.cloud/suno/audios",
            headers={{"Authorization": "Bearer YOUR_API_KEY"}},
            json={{
                "prompt": "A chill lo-fi hip hop beat for studying",
                "model": "chirp-v4",
                "action": "generate",
            }},
        )

        for song in response.json()["data"]:
            print(f"{{song['title']}}: {{song['audio_url']}}")
        ```

        ## Models

        | Model | Max duration | Quality |
        |-------|-------------|---------|
        | chirp-v3 | 4 min | Good |
        | chirp-v3.5 | 4 min | Better |
        | chirp-v4 | 6 min | Great |
        | chirp-v5 | 9 min | Best |

        ## MCP integration

        Use Suno directly from Claude Desktop:

        ```bash
        pip install mcp-suno
        ```

        Then ask Claude: "Generate a jazz song about rainy days" — it just works.

        ## Learn more

        - [Full Suno guide](/guides/suno/suno_audios) — All features and actions
        - [Suno MCP](/mcp/suno) — Claude Desktop integration
        - [API reference](/api-reference/suno) — Complete specification
    """)


def _blog_midjourney(a):
    return textwrap.dedent(f"""\
        ---
        title: "{a['title']}"
        seo: "{a['seo_title']}"
        description: "{a['description']}"
        ---

        Midjourney produces some of the best AI-generated images available today. Through Ace Data Cloud, you can access it via a simple REST API — no Discord required.

        ## Why use the Midjourney API?

        - **No Discord** — Call it from your code, not a chat app
        - **Programmatic** — Automate image generation at scale
        - **Full features** — Upscale, variations, in-painting, blending
        - **Webhook support** — Async generation with callbacks

        ## Quick start

        ```python
        import requests

        response = requests.post(
            "https://api.acedata.cloud/midjourney/imagine",
            headers={{"Authorization": "Bearer YOUR_API_KEY"}},
            json={{
                "prompt": "A photorealistic mountain landscape at golden hour --ar 16:9",
                "mode": "fast",
            }},
        )

        result = response.json()
        print("Image:", result["image_url"])
        ```

        ## Features

        | Action | Description |
        |--------|-------------|
        | imagine | Generate from text prompt |
        | upscale | Enhance resolution |
        | variation | Create variations |
        | in-painting | Edit parts of an image |
        | blend | Combine multiple images |
        | describe | Get prompt from an image |

        ## Alternatives

        | API | Speed | Quality | Cost |
        |-----|-------|---------|------|
        | Midjourney | 30-60s | Excellent | Higher |
        | Flux | 2-5s | Very good | Lower |
        | Seedream | 10-20s | Very good | Mid |

        ## Get started

        [Sign up free](https://platform.acedata.cloud) — trial credits included for Midjourney and all other services.
    """)


def _blog_generic(a):
    return textwrap.dedent(f"""\
        ---
        title: "{a['title']}"
        seo: "{a['seo_title']}"
        description: "{a['description']}"
        ---

        {a['description']}

        ## Get started

        [Sign up at Ace Data Cloud](https://platform.acedata.cloud) — free trial credits included.
    """)


# ---------------------------------------------------------------------------
# Main: Generate all pages
# ---------------------------------------------------------------------------


def main():
    stats = {"tutorials": 0, "comparisons": 0, "use_cases": 0, "blog": 0}

    # 1. Tutorials
    for service in SERVICES:
        for lang, generator in [
            ("python", generate_tutorial_python),
            ("javascript", generate_tutorial_javascript),
            ("curl", generate_tutorial_curl),
        ]:
            path = DOCS_DIR / "tutorials" / service["id"] / f"{lang}.mdx"
            path.parent.mkdir(parents=True, exist_ok=True)
            content = generator(service)
            path.write_text(content, encoding="utf-8")
            stats["tutorials"] += 1

    # 2. Comparisons
    for comp in COMPARISONS:
        path = DOCS_DIR / "comparisons" / f"{comp['slug']}.mdx"
        path.parent.mkdir(parents=True, exist_ok=True)
        content = generate_comparison(comp)
        path.write_text(content, encoding="utf-8")
        stats["comparisons"] += 1

    # 3. Use cases
    for uc in USE_CASES:
        path = DOCS_DIR / "use-cases" / f"{uc['slug']}.mdx"
        path.parent.mkdir(parents=True, exist_ok=True)
        content = generate_use_case(uc)
        path.write_text(content, encoding="utf-8")
        stats["use_cases"] += 1

    # 4. Blog
    for article in BLOG_ARTICLES:
        path = DOCS_DIR / "blog" / f"{article['slug']}.mdx"
        path.parent.mkdir(parents=True, exist_ok=True)
        content = generate_blog_article(article)
        path.write_text(content, encoding="utf-8")
        stats["blog"] += 1

    total = sum(stats.values())
    print(f"Generated {total} pages:")
    print(f"  Tutorials:   {stats['tutorials']}")
    print(f"  Comparisons: {stats['comparisons']}")
    print(f"  Use cases:   {stats['use_cases']}")
    print(f"  Blog:        {stats['blog']}")
    print(f"\nExisting pages: ~147")
    print(f"New pages:      {total}")
    print(f"Total:          ~{147 + total}")


if __name__ == "__main__":
    main()
