def strip_markdown_fences(content: str) -> str:
    for prefix in ("```markdown", "```python", "```json", "```"):
        if content.startswith(prefix):
            content = content[len(prefix):]
            break
    if content.endswith("```"):
        content = content[:-3]
    return content.strip()
