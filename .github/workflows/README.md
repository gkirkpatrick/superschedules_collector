# GitHub Workflows

## Disabled Workflows

The following workflows have been disabled by renaming them with `.disabled` extension:

- `claude.yml.disabled` - Interactive Claude Code responses to `@claude` mentions
- `claude-code-review.yml.disabled` - Automated Claude Code reviews on PRs

## Why Disabled?

- Direct Claude Code interaction is more reliable and faster
- No configuration/permission headaches
- Better debugging and context
- No timeout limitations

## Re-enabling

To re-enable any workflow, simply remove the `.disabled` extension:

```bash
mv claude.yml.disabled claude.yml
mv claude-code-review.yml.disabled claude-code-review.yml
```

The workflows are fully configured and ready to use if needed for team collaboration in the future.