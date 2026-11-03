# Skill di terze parti

| Skill | Origine | Versione | Licenza |
|---|---|---|---|
| impeccable | https://github.com/pbakaus/impeccable | vedi `impeccable/scripts/VERSION` | vedi `impeccable/LICENSE` |
| brainstorming, dispatching-parallel-agents, executing-plans, finishing-a-development-branch, receiving-code-review, requesting-code-review, subagent-driven-development, systematic-debugging, test-driven-development, using-git-worktrees, using-superpowers, verification-before-completion, writing-plans, writing-skills, diagnosing-superpowers | Superpowers, https://github.com/obra/superpowers | commit 2ce8aa1 | MIT, © 2025 Jesse Vincent (`LICENSE-superpowers`) |
| karpathy-guidelines | https://github.com/forrestchang/andrej-karpathy-skills | commit 2c60614 | MIT (dichiarata nel plugin e nella skill) |

Le skill di Superpowers sono copiate senza modifiche, senza l'hook di avvio
del plugin: Claude le trova dalla descrizione. Il logo remoto della pagina di
brainstorming visivo è disattivato con `SUPERPOWERS_DISABLE_TELEMETRY` in
`.claude/settings.json`.

Per aggiornarle: riclona i repository e ricopia le cartelle in `.claude/skills/`.
