---
title: "Wan Video Generation API"
description: "Wan integration guide - Ace Data Cloud"
---

`POST https://api.acedata.cloud/wan/videos` supports both the existing Wan 2.6 model and `wan3.0-video`. Wan 3 automatically recognizes text, first and last frames, or reference material patterns based on `media`.

## Wan 3 Text-to-Video

```bash
curl -X POST 'https://api.acedata.cloud/wan/videos' \
  -H 'Authorization: Bearer YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "wan3.0-video",
    "prompt": "A paper boat drifting through a neon city at night",
    "duration": 5,
    "resolution": "720P",
    "ratio": "16:9",
    "audio": true,
    "async": true
  }'
```

Wan 3 supports integer durations from 2 to 30 seconds or `-1` for intelligent duration, with resolutions of `480P`, `720P`, and `1080P`.

## Multimedia Reference

```json
{
  "model": "wan3.0-video",
  "prompt": "Create a cinematic product reveal",
  "media": [
    {"type":"first_frame","url":"https://platform2.cdn.acedata.cloud/qwen-image/40d5c76b-2f84-4b04-9ea0-b706417ae622.png"},
    {"type":"last_frame","url":"https://platform2.cdn.acedata.cloud/qwen-image/7a5a490c-1d60-4498-a362-a9334148f460.png"}
  ],
  "duration": 8,
  "resolution": "1080P",
  "ratio": "16:9",
  "async": true
}
```

`media.type` supports:

- `first_frame` / `last_frame`
- `reference_image`
- `reference_video`
- `reference_audio`
- `file` / `link`

First and last frame modes and reference material modes cannot be mixed. The final output video duration for reference videos is calculated based on the actual input video seconds added to the successful output video seconds; text, image, and audio inputs do not increase video seconds.

## Official Standard Pricing

| Resolution |      Price |
| ----- | ------: |
| 480P  | $0.05/second |
| 720P  | $0.10/second |
| 1080P | $0.20/second |

## Wan 2.6 Compatibility

The existing `wan2.6-t2v`, `wan2.6-i2v`, `wan2.6-r2v` and flash variants continue to use parameters such as `action`, `image_url`, `reference_video_urls`, with unchanged calling paths.

## Asynchronous and Results

By setting `async: true`, you will immediately receive a `task_id`, and you can obtain the final state through `/wan/tasks`. Successful videos will be stored in AceDataCloud CDN, and the actual usage and cost will be returned in the response.
