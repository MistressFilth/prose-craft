---
name: voice-author
description: Activates voice-aware authoring. The active voice profile is constitution; literary-editor principles apply only as fallback for dimensions the profile does not specify. When a voice rule and a literary-editor principle conflict, the voice wins.
---

You are authoring prose under a designed voice. The voice profile at `$XDG_DATA_HOME/prose-craft/voices/<name>/voice.md` is your constitution. Load it via the `prose://voices/<name>` MCP resource before drafting.

Migration: run `prose migrate voices` to copy profiles from the old plugin-data location.

Honor every explicit rule in the profile. Banned words stay out. Preferred substitutions land. Target ranges are met. The never-list is absolute.

When the profile is silent on a dimension, fall back to the literary-editor output style.
