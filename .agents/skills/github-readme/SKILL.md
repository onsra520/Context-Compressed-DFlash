---
name: github-readme
description: >
  Creates professional, well-structured, and visually appealing README.md files for GitHub projects.
  Use this skill whenever the user wants to: write a README, document a GitHub project, update an
  existing README, create docs for a new repo, or asks "how do I write a good README". Trigger on
  any mention of "README", "repo documentation", "github docs", "project docs", "shields.io",
  "badges", or any request to describe or document a software project. Always produce a real .md
  file — never just inline markdown text in chat.
---

# GitHub README Skill

Generate professional, GitHub-standard `README.md` files with a complete structure, badges, and compelling content.

---

## Workflow

### Step 1 — Gather Information

If the user hasn't provided enough context, ask using `ask_user_input_v0` (if available):

| Field | Notes |
|---|---|
| Project name | Required |
| Short description | 1–2 sentences |
| Language / Framework | Used to select appropriate badges |
| Key features | At least 3 bullet points |
| Installation steps | Specific terminal commands |
| Usage examples | Code snippets or demo link |
| License type | MIT, Apache, GPL, etc. |
| Author name / GitHub handle | For contact section |

**If the user doesn't provide enough info**, infer from context and use clear placeholders like `<!-- TODO: add description -->` so they can fill in later easily.

---

### Step 2 — Pick the Right Template

Based on the project type, select the corresponding template:

| Project Type | Template |
|---|---|
| CLI Tool / Script | `cli` — focus on usage & flags |
| Web App / SaaS | `webapp` — demo GIF, screenshots, deploy link |
| Library / Package | `library` — API docs, code examples |
| Mobile App | `mobile` — store badges, screenshots |
| Data Science / ML | `datascience` — dataset, metrics, notebooks |
| Game | `game` — gameplay GIF, controls |
| API / Backend | `api` — endpoints table, auth guide |
| Template / Boilerplate | `boilerplate` — feature checklist, fork guide |

Refer to `references/templates.md` for the full structure of each template.

---

### Step 3 — Write the README

#### Required sections (in order):

```
1.  Header        — logo + name + tagline
2.  Badges        — language, version, license, build status
3.  Demo          — screenshot or GIF (if available)
4.  Table of Contents — required if README > 100 lines
5.  About         — what the project does and why
6.  Features      — bullet list of key capabilities
7.  Installation  — step-by-step setup commands
8.  Usage         — examples with code blocks
9.  Configuration — env vars / config options (if needed)
10. Contributing  — how to open PRs and issues
11. License       — license name + link
12. Contact       — author info or links
```

#### Writing principles:

- **Language**: Write in the same language the user is using. Keep technical terms in English regardless.
- **Code blocks**: Always declare the language (` ```bash `, ` ```python `, etc.)
- **Tone**: Clear, concise, professional — no filler text
- **Emoji**: Use selectively for headings (🚀 ✨ 📦 🛠️ 🤝 📄) — do not overuse
- **Badges**: Only include badges that add real value (see Step 4 below)

---

### Step 4 — Badges

Use [shields.io](https://shields.io) format:

```markdown
![Badge](https://img.shields.io/badge/label-message-color?style=flat-square&logo=logoname)
```

#### Common language badges:

```markdown
<!-- Python -->
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)

<!-- Node.js -->
![Node.js](https://img.shields.io/badge/Node.js-18+-339933?style=flat-square&logo=node.js&logoColor=white)

<!-- TypeScript -->
![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6?style=flat-square&logo=typescript&logoColor=white)

<!-- React -->
![React](https://img.shields.io/badge/React-18+-61DAFB?style=flat-square&logo=react&logoColor=black)

<!-- Go -->
![Go](https://img.shields.io/badge/Go-1.21+-00ADD8?style=flat-square&logo=go&logoColor=white)

<!-- Rust -->
![Rust](https://img.shields.io/badge/Rust-1.70+-000000?style=flat-square&logo=rust&logoColor=white)
```

#### Project status badges:

```markdown
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)
![Version](https://img.shields.io/badge/version-1.0.0-blue?style=flat-square)
![Stars](https://img.shields.io/github/stars/USERNAME/REPO?style=flat-square)
![Issues](https://img.shields.io/github/issues/USERNAME/REPO?style=flat-square)
![Build](https://img.shields.io/github/actions/workflow/status/USERNAME/REPO/ci.yml?style=flat-square)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat-square)
```

See `references/badges.md` for the full badge reference list.

---

### Step 5 — Craft a Great Header

A strong header has three components:

```markdown
<div align="center">

<!-- Optional logo -->
<img src="assets/logo.png" alt="Logo" width="120" />

# 🚀 Project Name

**A short, punchy tagline describing the project in one sentence.**

[Live Demo](https://demo-link.com) · [Report Bug](https://github.com/user/repo/issues) · [Request Feature](https://github.com/user/repo/issues)

![Badge1](url) ![Badge2](url) ![Badge3](url)

</div>

---
```

---

### Step 6 — Output the File

1. Write the final file to `/mnt/user-data/outputs/README.md`
2. Call `present_files` so the user can download it
3. Give a short summary: which sections were generated, and which placeholders they should fill in

---

## Important Rules

- **Always create a real file** — never just display markdown inline in chat
- **Use clear placeholders**: `<!-- TODO: ... -->` or `[YourValue]` for anything the user must fill in
- **Never fabricate information**: If you don't know the version, write `X.X.X` — don't guess
- **Table of Contents**: Required if README > 80 lines; use standard GitHub anchor links (`[Section](#section)`)
- **Alignment**: Use `<div align="center">` for centering — avoid complex inline CSS