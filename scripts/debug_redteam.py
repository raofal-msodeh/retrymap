"""Debug red_team PYTHONPATH handling."""
import os
import subprocess

os.chdir("/home/ubuntu/retrymap")
env = dict(os.environ)
env["PYTHONPATH"] = "src"
r = subprocess.run(
    ["python3", "-c", "from retrymap import ExponentialPolicy; ExponentialPolicy(base=2.0, cap=1.0)"],
    capture_output=True, text=True, env=env,
)
print("rc:", r.returncode)
print("stderr:", r.stderr.strip()[:200])
