# Publishing to GitHub / 发布到 GitHub

The source tree is ready for a new repository named `ai-ready-semantic-hub`. No remote account or repository URL is embedded in the source. A connected GitHub account with repository creation rights is required.

If using GitHub CLI on your computer, authenticate first with `gh auth login`, then run these commands from the source directory (replace `YOUR_OWNER` with your username or an organization where you can create repositories):

```bash
git init -b main
git add .
git commit -m "Initial semantic hub implementation"
gh repo create YOUR_OWNER/ai-ready-semantic-hub --public --source=. --remote=origin --push
```

Use `--private` if you want a private evaluation before open sourcing. Configure your own Git author identity if Git requests it. The command must create a new repository; do not use it to overwrite an unrelated existing repository.

Before the first public release:

- Review the source and license. Example definitions are synthetic; do not add internal schemas, API keys or real orders.
- Enable private vulnerability reporting and appropriate branch protection in repository settings.
- Run CI and inspect the browser/container jobs, then tag a release.
- Set a repository description and relevant topics (`semantic-layer`, `business-intelligence`, `mcp`, `data-catalog`, `ai-agents`).

Do not claim a GitHub repository exists until creation and push have succeeded. 本源码包不包含 GitHub 凭证；远端仓库必须在实际授权后创建，并核对推送结果。
