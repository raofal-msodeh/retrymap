"""Scaffold RetryMap project structure (dirs only)."""
import os

base = "/home/ubuntu/retrymap"
dirs = [
    "src/retrymap",
    "tests",
    "examples",
    "docs/adr",
    ".github/ISSUE_TEMPLATE",
]
for d in dirs:
    os.makedirs(os.path.join(base, d), exist_ok=True)
print("dirs created")
