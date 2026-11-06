#!/usr/bin/env python3
"""The Claude seat: the claude CLI in print mode, one turn, no tools.

On a line that addresses it, the seat runs
  claude -p --model ... --tools "" --safe-mode ... --session-id|--resume <id>
with a system prompt that names the seat and the rails, and the last 20
channel lines as context. The channel has one fixed session: created on the
first run, resumed afterwards.

The seat refuses to start unless the CLI itself reports an empty tool list
and no MCP servers. Standard library only.

Environment:
  HOUSE_IRC_HOST, HOUSE_IRC_PORT   the IRC server
  HOUSE_NICK                       default meeseeks
  HOUSE_CHANNEL                    default #house
  HOUSE_CLAUDE_BIN                 path of the claude CLI, default claude
  HOUSE_CLAUDE_MODEL               default claude-sonnet-5-5
  HOUSE_CLAUDE_TIMEOUT             seconds per turn, default 60
  HOUSE_STATE_DIR                  holds the session id and the empty working directory
  HOUSE_SEAT_NICKS                 comma list of other seats (also learned from the bot tag)
"""
import json
import os
import signal
import subprocess
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import irc  # noqa: E402
import rails  # noqa: E402

# Everything that could give the model a tool or a side effect is off:
# no built-in tools, no MCP servers, no hooks, skills or plugins, nothing to prompt for.
CLI_FLAGS = ["--tools", "", "--safe-mode", "--strict-mcp-config", "--disable-slash-commands",
             "--permission-prompts", "none"]


class Claude:
    def __init__(self, binary, model, timeout, state_dir):
        self.binary, self.model, self.timeout = binary, model, timeout
        self.state_file = os.path.join(state_dir, "session.json")
        self.cwd = os.path.join(state_dir, "cwd")  # empty on purpose: no project files, no CLAUDE.md
        os.makedirs(self.cwd, mode=0o700, exist_ok=True)

    def _run(self, args, prompt):
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT")}
        proc = subprocess.Popen([self.binary, "-p", "--model", self.model, *CLI_FLAGS, *args],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, cwd=self.cwd, env=env, start_new_session=True)
        try:
            out, err = proc.communicate(prompt, timeout=self.timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()
            raise TimeoutError(f"claude timed out after {self.timeout}s")
        return proc.returncode, out, err

    def check_no_tools(self):
        """Ask the CLI what it would run with and exit unless the answer is nothing."""
        code, out, _ = self._run(["--no-session-persistence", "--output-format", "stream-json", "--verbose"],
                                 "Reply with the single word ok.")
        init = next((m for m in map(_json, out.splitlines()) if m.get("type") == "system" and m.get("subtype") == "init"), {})
        if code != 0 or init.get("tools") != [] or init.get("mcp_servers") != []:
            raise SystemExit(f"refusing to start: tools={init.get('tools')!r} mcp={init.get('mcp_servers')!r} exit={code}")
        rails.log(f"verified: model {init.get('model')}, tools [], mcp []")

    def _session(self):
        try:
            with open(self.state_file, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {"id": str(uuid.uuid4()), "created": False}

    def _save(self, state):
        with open(self.state_file, "w", encoding="utf-8") as fh:
            json.dump(state, fh)

    def answer(self, system, user):
        state = self._session()
        for _ in range(2):
            flag = "--resume" if state["created"] else "--session-id"
            code, out, err = self._run([flag, state["id"], "--system-prompt", system, "--output-format", "json"], user)
            if "No conversation found" in out + err:  # session file gone: start a new one
                state = {"id": str(uuid.uuid4()), "created": False}
                continue
            result = _json(out)
            if code != 0 or result.get("is_error") or "result" not in result:
                raise RuntimeError(f"claude exit {code}")
            self._save({"id": state["id"], "created": True})
            return result["result"]
        raise RuntimeError("no session")


def _json(text):
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else {}
    except ValueError:
        return {}


def main():
    nick = os.environ.get("HOUSE_NICK", "meeseeks")
    channel = os.environ.get("HOUSE_CHANNEL", "#house")
    state_dir = os.path.expanduser(os.environ.get("HOUSE_STATE_DIR", "~/.local/state/house-room"))
    os.makedirs(state_dir, mode=0o700, exist_ok=True)
    claude = Claude(os.environ.get("HOUSE_CLAUDE_BIN", "claude"), os.environ.get("HOUSE_CLAUDE_MODEL", "claude-sonnet-5-5"),
                    int(os.environ.get("HOUSE_CLAUDE_TIMEOUT", "60")), state_dir)
    claude.check_no_tools()
    seat = rails.Seat(nick, channel, claude.answer, os.environ.get("HOUSE_SEAT_NICKS", "").split(","), per_hour=60)
    client = irc.Client(rails.env("HOUSE_IRC_HOST"), int(rails.env("HOUSE_IRC_PORT", "6667")), nick, channel, log=rails.log)
    client.run(seat.handle)


if __name__ == "__main__":
    main()
