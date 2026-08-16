"""Force-replace wrapper.__wrapped__ with setattr in engine.py."""
p = "src/retrymap/engine.py"
s = open(p, encoding="utf-8").read()
target = 'wrapper.__wrapped__ = fn'
replacement = 'setattr(wrapper, "__wrapped__", fn)'
assert target in s, "target not found"
s = s.replace(target, replacement)
assert target not in s, "replacement failed"
open(p, "w", encoding="utf-8").write(s)
print("patched:", replacement in open(p, encoding="utf-8").read())
