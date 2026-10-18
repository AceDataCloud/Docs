# n8n template submission draft

Status on 2026-10-06: the JSON is ready for a Creator Dashboard upload. It has not been submitted or listed in n8n's template library. Upload requires an n8n Creator account at [creators.n8n.io](https://creators.n8n.io/login).

- Workflow file: [acedatacloud-chat.json](acedatacloud-chat.json)
- Proposed title: **Generate a chat answer in n8n with AceDataCloud**
- Suggested keywords: AceDataCloud, chat completions, HTTP Request, AI, prompt
- Reviewer references: [submission guidelines](https://n8n.notion.site/Template-submission-guidelines-9959894476734da3b402c90b124b1f77) and [sticky note guidelines](https://n8n.notion.site/Sticky-note-guidelines-for-templates-2aa5b6e0c94f8058b0aefddd02655887)

## Description to paste into Creator Dashboard

Add a short AI answer to an n8n automation with AceDataCloud Chat Completions. This template is a starting point for teams that want to turn an incoming text field into a response they can route to another app, such as a support queue or an internal review step. It uses only built-in n8n nodes, so there is no community package to install.

### How it works

A manual trigger starts one test run. Edit Fields supplies a sample prompt and the `gpt-4o-mini` model. HTTP Request sends a non-streaming request to AceDataCloud using an n8n HTTP Bearer Auth credential. A final Edit Fields node exposes the answer, response ID, model, and token counts as separate fields for downstream nodes. The request caps output at 80 tokens, and automatic retries are off to avoid replaying an ambiguous billable request.

### Setup

Create an AceDataCloud API token with Chat Completions access. Import the workflow JSON, connect the token as a Bearer Auth credential in **AceDataCloud chat**, and save the workflow. Change the sample prompt if desired, then run the manual trigger once. Check the final output and the matching AceDataCloud usage record before attaching a schedule or webhook.

### Customize

Replace the manual trigger with your source node and map its text into `prompt`. Choose another supported model or adjust `max_tokens` for your task. Configure n8n execution-data retention when prompts contain sensitive information.

## Submission and review record

After uploading the JSON and description, record the Creator Dashboard submission ID, review status, and published n8n template URL here. A Docs PR and an importable JSON file do not establish n8n library publication.
