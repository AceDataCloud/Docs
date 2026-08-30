---
title: "Qwen Image Generation and Editing API"
description: "Qwen Image integration guide - Ace Data Cloud"
---

`POST https://api.acedata.cloud/qwen-image/images` completes text-to-image generation and editing of 1–3 reference images through the same interface, supporting `qwen-image-3.0` and `qwen-image-3.0-pro`.

## Model Selection

| Model                   | Suitable Scenarios       | Official Standard Price                   |
| -------------------- | -------------------- | ----------------------- |
| `qwen-image-3.0`     | Batch creation, rapid iteration  | Output $0.030/image             |
| `qwen-image-3.0-pro` | Complex layouts, high-precision output | 1K $0.040/image; 2K $0.075/image |

Reference images are billed based on the actual input quantity, with an official standard price of $0.003/image.

## Synchronous Generation

```bash
curl -X POST 'https://api.acedata.cloud/qwen-image/images' \
  -H 'Authorization: Bearer YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "qwen-image-3.0",
    "prompt": "A simple red circle centered on a clean white background.",
    "size": "1024*1024",
    "n": 1,
    "watermark": false
  }'
```

A successful response includes a permanent CDN image URL, actual usage, and the cost for this request:

```json
{
  "success": true,
  "task_id": "565a7f55-72c6-43ed-b274-268ff046e5b4",
  "trace_id": "bb923cec-1550-43b4-8df2-288ac0977b4b",
  "data": [
    {
      "image_url": "https://platform2.cdn.acedata.cloud/qwen-image/40d5c76b-2f84-4b04-9ea0-b706417ae622.png"
    }
  ],
  "usage": {
    "input_image_count": 0,
    "output_image_count": 1,
    "output_image_type": "qima_output_1k",
    "output_width": 1024,
    "output_height": 1024
  },
  "cost": {
    "amount": 0.322,
    "currency": "credit",
    "list_amount": 0.35
  }
}
```

## Reference Image Editing

Add `image_urls`, supporting 1–3 publicly accessible images:

```json
{
  "model": "qwen-image-3.0-pro",
  "prompt": "Retain the subject, change the background to a warm **###** poster style",
  "image_urls": [
    "https://platform2.cdn.acedata.cloud/qwen-image/40d5c76b-2f84-4b04-9ea0-b706417ae622.png"
  ],
  "size": "2048*2048",
  "n": 1,
  "watermark": false
}
```

`prompt_extend_mode=agent` is only used for text-to-image generation. The range for `n` is 1–6; the aspect ratio must be between 1:8 and 8:1.

## Asynchronous Tasks

After setting `async: true`, the interface immediately returns `task_id`. Use `/qwen-image/tasks` to query the final state, or provide a `callback_url` to receive completion notifications. Generation is billed only once, and task queries do not incur repeated charges.
