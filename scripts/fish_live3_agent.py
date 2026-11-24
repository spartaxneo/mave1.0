"""Create or update Mave's Fish Live 3 agent and publish it.

    python3 scripts/fish_live3_agent.py https://<brain-public-url>

Live 3 handles listening, turn-taking, backchannels and voice; its custom LLM is our
brain server (services/voice/os1_voice/brain_server.py). Writes FISH_AGENT_ID to .env.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
ENV = ENV_PATH.read_text()


def env(key: str) -> str:
    m = re.search(rf"(?m)^{key}=(.*)$", ENV)
    return m.group(1).split("#")[0].strip() if m else ""


def call(method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        "https://api.fish.audio" + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {env('FISH_API_KEY')}", "Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r) if r.status != 204 else {}


def main() -> None:
    brain_url = (sys.argv[1] if len(sys.argv) > 1 else env("BRAIN_PUBLIC_URL")).rstrip("/")
    if not brain_url.startswith("https://"):
        raise SystemExit("usage: fish_live3_agent.py https://<brain-public-url>  (Fish requires public HTTPS)")
    agent_id = env("FISH_AGENT_ID")
    if not agent_id:
        created = call("POST", "/v1/agent/agents", {"name": "mave-live3"})
        agent_id = created.get("id") or created.get("agent_id") or created.get("_id")
        print("created agent", agent_id)
    config = {
        "voice": {"engine": "live3", "voice_id": env("FISH_VOICE_1_ID"), "speaking_language": "en"},
        "llm": {"custom": {"base_url": f"{brain_url}/v1", "model": "mave", "api_key": env("OS1_BRAIN_TOKEN")}},
        # The brain supplies persona and routing; Fish's own prompt stays minimal.
        "prompt": {
            "system_prompt": "You are Mave.",
            "first_message_mode": "prompt",
            "first_message_prompt": "Open the conversation.",
        },
        "conversation": {"backchannel": {"enabled": True}, "interruptible": True},
    }
    cfg = call("PATCH", f"/v1/agent/agents/{agent_id}/config", config)
    c = cfg.get("config", cfg)
    print("voice:", {k: c["voice"].get(k) for k in ("engine", "voice_id")}, "llm:", c["llm"]["custom"]["base_url"])
    print("published version", call("POST", f"/v1/agent/agents/{agent_id}/publish", {"version_title": "os1 live3"}).get("version_number"))
    text = ENV_PATH.read_text()
    for key, val in (("FISH_AGENT_ID", agent_id), ("BRAIN_PUBLIC_URL", brain_url)):
        text = re.sub(rf"(?m)^{key}=.*$", f"{key}={val}", text) if re.search(rf"(?m)^{key}=", text) else text + f"\n{key}={val}"
    ENV_PATH.write_text(text)


if __name__ == "__main__":
    main()
