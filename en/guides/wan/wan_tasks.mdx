---
title: "Wan Task Query API"
description: "Wan integration guide - Ace Data Cloud"
---

`POST https://api.acedata.cloud/wan/tasks` is used to query, batch query, or delete Wan video tasks. Task queries do not incur additional generation fees.

## Query a Single Task

```bash
curl -X POST 'https://api.acedata.cloud/wan/tasks' \
  -H 'Authorization: Bearer YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '{"action":"retrieve","id":"TASK_ID"}'
```

The `response.data.video_url` of the completed task is a permanent CDN address; `response.usage` includes resolution, input/output video seconds, frame rate, and aspect ratio; `response.cost` is the settlement for the generated task.

## Batch Query

```json
{
  "action": "retrieve_batch",
  "ids": [
    "TASK_ID_1",
    "TASK_ID_2"
  ]
}
```

Returns `{ "items": [...], "count": 2 }`. When tasks are in progress, there may not yet be `finished_at` and final `response`.

## Delete Task Record

```json
{
  "action": "delete",
  "id": "TASK_ID"
}
```

Deletion only affects task history records and will not delete the already generated CDN videos.
