"""Command safety — dangerous command detection for terminal execution.

Migrated from terminal-tools sandbox.py patterns and expanded with Hermes
approval.py pattern references.  Pure detection — no approval workflow,
no allowlist, no YOLO mode.
"""

import logging
import re

logger = logging.getLogger("v2.command_safety")

_DANGEROUS_PATTERNS: list[tuple[str, str]] = [
    # Privilege escalation
    (r'\bsudo\b', "sudo command"),
    (r'\bsu\s', "su command"),
    (r'\bpasswd\b', "passwd command"),
    (r'\bvisudo\b', "visudo command"),
    # System shutdown / reboot
    (r'\b(shutdown|reboot|halt|poweroff|init\s+[06])\b', "system shutdown/reboot"),
    # Disk operations
    (r'\bmkfs\b', "format filesystem"),
    (r'\bfdisk\b', "disk partition"),
    (r'\bparted\b', "disk partition"),
    (r'\bdd\s+if=', "disk copy (dd)"),
    (r'>\s*/dev/(sd|hd|nvme|mmcblk|vd|xvd)', "write to block device"),
    (r'\bmount\b', "mount command"),
    (r'\bumount\b', "umount command"),
    # Filesystem destructive
    (r'\brm\s+.*-rf\s+/', "recursive delete of root filesystem"),
    (r'\brm\s+-rf\s+/', "recursive delete of root filesystem"),
    (r'\bchmod\s+(.*\s+)?777\s+/(\s|$)', "chmod 777 /"),
    (r'\bchown\s+.*\s+/', "chown on root"),
    # Fork bomb
    (r':\(\)\s*\{', "fork bomb"),
    # Pipe remote content to shell
    (r'\b(curl|wget)\b.*\|\s*(?:ba)?sh', "pipe remote content to shell"),
    (r'\b(bash|sh|zsh|ksh)\s+<\s*\(\s*(curl|wget)\b', "execute remote script via process substitution"),
    # Write to sensitive system paths
    (r'\btee\b.*/etc/', "overwrite /etc via tee"),
    (r'>>?\s*/etc/', "overwrite /etc via redirection"),
]

_COMPILED: list[tuple[re.Pattern, str]] = [
    (re.compile(pattern, re.IGNORECASE | re.DOTALL), description)
    for pattern, description in _DANGEROUS_PATTERNS
]


def check_dangerous_command(command: str) -> str | None:
    """Check a command against dangerous patterns.

    Returns a description string if dangerous, or None if safe.
    """
    if not command or not isinstance(command, str):
        return None

    cmd_lower = command.strip()
    for pattern_re, description in _COMPILED:
        if pattern_re.search(cmd_lower):
            logger.warning("Dangerous command blocked: %s (matched: %s)", command[:200], description)
            return f"Dangerous command blocked: {description}"
    return None
