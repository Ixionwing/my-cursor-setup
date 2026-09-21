---
name: web-design-guidelines
description: Review UI code for Web Interface Guidelines compliance. Use when asked to "review my UI", "check accessibility", "audit design", "review UX", or "check my site against best practices".
metadata:
  author: vercel
  version: "1.0.0"
  argument-hint: <file-or-pattern>
---

> Vendored from Vercel Labs agent-skills (`web-design-guidelines`) plus
> web-interface-guidelines `command.md`, MIT License, Copyright (c) 2025
> Vercel Labs. Unmodified snapshots:
> `third_party/vercel-labs-agent-skills/web-design-guidelines/`.
> Skill wrapper revision: 063bee94c3f4df8453406c830b0a7df0f2860278.
> Guidelines body revision: e3d624baaf29dc1fc645aff3e38f03e564d2d6b1.
> This file is a **Cursor port** (not unmodified). Do not WebFetch GitHub.

# Web Interface Guidelines

Review files for compliance with Web Interface Guidelines.

## How It Works

1. Read sibling `command.md` (vendored; Pigment-shaped examples are the ease-of-use default)
2. Read the specified files (or prompt user for files/pattern)
3. Check against all rules in that file
4. Output findings in the terse `file:line` format

**Behavior is required; nomenclature is not.** `focus-visible`, skip links, reduced motion, labeled controls, and the rest of the rules must exist. Review against the **in-use** framework (Pigment `css` / MUI `sx` / theme, or Tailwind if that is already the stack). Do not false-flag a correct Pigment (or Chakra, Emotion, etc.) implementation for missing Tailwind classes. When reviewing a repo that already uses another framework, map the same behaviors onto that framework — do not fail a Tailwind UI for not looking like Pigment.

## Usage

When a user provides a file or pattern argument:
1. Read sibling `command.md`
2. Read the specified files
3. Apply all rules from those guidelines
4. Output findings using the format specified in the guidelines

If no files specified, ask the user which files to review.
