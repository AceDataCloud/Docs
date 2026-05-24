---
title: "Suno 声音克隆 API 对接说明"
description: "Suno Music Generation 集成指南 - Ace Data Cloud"
---

SUNO 允许我们通过任意音频文件创建自定义声音角色，实现声音克隆用于音乐生成。与已有的 Persona API（使用 Suno 生成的 `audio_id`）不同，该 API 接受一个公开可访问的 `audio_url`，即你自己的人声录音。本文档讲解声音克隆 API 的对接方法。

## 第一步：创建声音角色

该 API 有三个输入参数：`audio_url`（必填），为一个公开可访问的 MP3 或 WAV 格式音频文件 URL，其中包含单人清晰人声；`name` 和 `description`（可选），为声音角色的名称和描述。

**音频文件要求：**
- 格式：MP3 或 WAV
- 时长：至少 10 秒
- 内容：单人清晰人声，尽量减少背景噪音或音乐

```bash
curl -X POST 'https://api.acedata.cloud/suno/voices' \
-H 'accept: application/json' \
-H 'authorization: Bearer {token}' \
-H 'content-type: application/json' \
-d '{
  "audio_url": "http://cos.aitutu.cc/mp4/ru-user-voice.mp3",
  "name": "RU User Voice Test",
  "description": "用户语音录音示例"
}'
```

结果如下：

```json
{
  "success": true,
  "task_id": "b9150e51-d87c-4556-a55e-100947a63bdf",
  "data": {
    "persona_id": "e95013f8-eaee-4741-a42f-1d559a9d0b2b",
    "name": "RU User Voice Test",
    "is_public": false
  }
}
```

可以看到，`data` 的 `persona_id` 字段就是创建的声音角色 ID。`is_public` 字段始终为 `false`，因为通过上传音频创建的声音角色是私有的。

## 第二步：使用声音角色生成音乐

有了声音角色 ID 之后，我们便可以使用 [Suno Audios Generation API](https://platform.acedata.cloud/documents/4da95d9d-7722-4a72-857d-bf6be86036e9) 来进行音乐生成了。将 `action` 设为 `generate`，并将 `persona_id` 设为上面返回的声音角色 ID，生成的歌曲将使用克隆的声音进行演唱。

> **注意：** 声音克隆仅支持 `chirp-v4-5` 及以上模型（如 `chirp-v4-5`、`chirp-v5`、`chirp-v5-5`），不支持 `chirp-v4`。

```bash
curl -X POST 'https://api.acedata.cloud/suno/audios' \
-H 'accept: application/json' \
-H 'authorization: Bearer {token}' \
-H 'content-type: application/json' \
-d '{
  "action": "generate",
  "model": "chirp-v5-5",
  "prompt": "A warm synth-pop song about city nights",
  "persona_id": "e95013f8-eaee-4741-a42f-1d559a9d0b2b"
}'
```

结果如下：

```json
{
  "success": true,
  "task_id": "53d8a334-a972-43c5-895e-60c4454e88d5",
  "data": [
    {
      "id": "16463960-077c-4700-bbb3-3c7897b943d3",
      "title": "Soft Neon on My Skin",
      "audio_url": "https://cdn1.suno.ai/16463960-077c-4700-bbb3-3c7897b943d3.mp3",
      "image_url": "https://cdn2.suno.ai/image_16463960-077c-4700-bbb3-3c7897b943d3.jpeg",
      "model": "chirp-v5-5",
      "state": "succeeded",
      "prompt": "A warm synth-pop song about city nights",
      "duration": 156.28
    }
  ]
}
```

可以看到，生成的歌曲使用了克隆的声音进行演唱。`persona_id` 也可以与 `cover` 动作配合使用，用克隆的声音翻唱已有歌曲。
