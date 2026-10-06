# AceDataCloud chat component for GitLab CI/CD

This project provides one manual `commit-summary` job. It sends the current commit title to the AceDataCloud Chat Completions API and saves the returned text as `summary.txt` for one day.

This directory is the source for a **separate GitLab component project**. Copy its contents to the root of that project. A GitHub Docs merge alone does not publish a GitLab CI/CD Catalog entry.

## Use the component

After the GitLab project has published a version, add this to a consuming project's `.gitlab-ci.yml`. Replace `your-group` with the actual GitLab namespace, and pin a published version:

```yaml
stages:
  - test
  - report

include:
  - component: gitlab.com/your-group/acedatacloud-chat/commit-summary@1.0.0
    inputs:
      stage: report
      model: gpt-5.5
```

The component also accepts `job-name` (default `acedatacloud-commit-summary`). The `model` input is sent as a value in the JSON request; it does not select a fallback. Check [current model pricing](https://platform.acedata.cloud/) before changing it.

Create `ACEDATACLOUD_API_TOKEN` in the **consuming** project's **Settings → CI/CD → Variables**. Set it to **Masked and hidden**, disable variable expansion, and mark it **Protected**. Protect the project's default branch. Never put the token in a component input, YAML file, job output, or artifact. Review CI changes before running them with this variable; masking does not prevent malicious pipeline code from exfiltrating a token. Keep `CI_DEBUG_TRACE` off. For stronger isolation, use an external secret manager supported by your GitLab instance.

The job appears only on a protected default branch and requires a manual start. It does not run for merge requests, fork pipelines, or tags. A successful run makes one billable request. The job does not retry automatically. If a connection fails after the request was sent or the response lacks a summary, check AceDataCloud usage before running it again: the billing outcome may be unknown. The log shows the HTTP status on an API error, not the API response body. The `summary.txt` artifact is available to project Developers or higher for one day. Avoid sending confidential commit titles unless your data policy allows it.

For a pipeline you can copy without a component project, see the [standalone example](https://github.com/AceDataCloud/Docs/blob/main/examples/gitlab/acedatacloud-chat.gitlab-ci.yml).

## Publish to the GitLab CI/CD Catalog

1. Create a GitLab project, for example `acedatacloud-chat`, in the intended namespace. Give it a clear project description and copy this directory's files to its repository root so `README.md`, `templates/commit-summary.yml`, `.gitlab-ci.yml`, and `tests/verify_component.rb` retain these paths. Make it public if the component should be available to all GitLab.com users.
2. Run the branch pipeline. `verify-component` checks the shell syntax, JSON encoding, token guard, error handling, and artifact behavior without an AceDataCloud token or billable call. The manual component job should remain unstarted.
3. Have a project Owner turn on **CI/CD Catalog project** under **Settings → General → Visibility, project features, permissions**. A Maintainer or Owner can publish releases. Protect the default branch and release tags.
4. After the component passes review, create a semantic version tag such as `1.0.0` on the reviewed default-branch commit. The tag pipeline runs `verify-component` before `publish-component`; the latter uses GitLab's `release` keyword to publish the version to the Catalog. An API-created Release alone does not publish the Catalog version.
5. Confirm the Release and Catalog entry in GitLab, resolve the actual component URL, then run one manual job in a dedicated consumer project with a limited token. Save the pipeline URL, job status, sanitized log, artifact name, and matching AceDataCloud usage record as publication evidence. Do not treat a passing component-project pipeline as proof of a real API call.

Do not create a release from a failed tag pipeline. Keep published tags immutable. Use patch versions for compatible fixes, minor versions for new backward-compatible inputs, and major versions for breaking changes. Consumers should pin an exact version and can roll back by restoring the previous version. Retain the previous published version during a migration.

## Support

Open an issue at [AceDataCloud Docs](https://github.com/AceDataCloud/Docs/issues) with the GitLab version, component version, pipeline/job URL, HTTP status, and a redacted log. Do not attach tokens, full API responses, or private commit titles. The component accepts no supplier-specific settings. It uses the public AceDataCloud API contract and does not add a model fallback.

The required GitLab project and release flow follow [GitLab's CI/CD component documentation](https://docs.gitlab.com/ci/components/). Secret handling follows [GitLab's CI/CD variable guidance](https://docs.gitlab.com/ci/variables/).
