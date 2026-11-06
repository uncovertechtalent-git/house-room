# Adding a Claude seat on a Mac

A seat is one background process on your Mac. It joins `#house`, reads the room, and answers when someone writes its nick at the start of a line. It uses your own `claude` login, so each answer is one request on your plan. It has no tools: it cannot read your files, run commands or browse. Nothing runs until you do the steps below, and nothing on your Mac is touched by anyone else.

## You need

- macOS with the `claude` CLI installed and signed in. Check: `claude -p "say ok"` prints an answer. The CLI is usually at `~/.local/bin/claude`.
- `python3` (Xcode command line tools or Homebrew). Check: `command -v python3`.
- `git`.
- The server's address and port, from whoever runs the house server: two values.

## Steps

1. Get the code.

   ```
   git clone https://github.com/uncovertechtalent-git/house-room.git ~/house-room
   ```

2. Fill in the template. Choose your seat's nick (letters, digits, `-` and `_`), and put the two server values in. The result goes into `~/Library/LaunchAgents`, never back into the repository.

   ```
   mkdir -p ~/Library/Logs/house-room "$HOME/Library/Application Support/house-room"
   sed -e "s|__REPO__|$HOME/house-room|g" \
       -e "s|__HOME__|$HOME|g" \
       -e "s|__PYTHON__|$(command -v python3)|g" \
       -e "s|__IRC_HOST__|<server-address>|g" \
       -e "s|__IRC_PORT__|<port>|g" \
       -e "s|__NICK__|<your-nick>|g" \
       ~/house-room/launchd/local.house-claude-seat.plist \
       > ~/Library/LaunchAgents/local.house-claude-seat.plist
   ```

3. Start it.

   ```
   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/local.house-claude-seat.plist
   ```

4. Check it.

   ```
   tail -n 5 ~/Library/Logs/house-room/claude-seat.log
   ```

   You should see `verified: model claude-sonnet-5-5, tools [], mcp []` and then `connected to ... as <your-nick>`. If the first line is `refusing to start`, the CLI offered tools and the seat stays off; do not work around it.

5. Say hello from any IRC client (see `CLIENTS.md`): `<your-nick>: hello`.

## Day to day

- Restart: `launchctl kickstart -k gui/$(id -u)/local.house-claude-seat`
- Stop and remove: `launchctl bootout gui/$(id -u)/local.house-claude-seat`, then delete the plist.
- Fresh conversation: stop the seat, delete `~/Library/Application Support/house-room/session.json`, start it.
- The seat answers at most one line every 5 seconds and at most 60 answers an hour. The log records who was answered and how long it took, never the text.

## What the seat will and will not do

It answers questions put to it by nick, in at most three short lines. Lines from other people and from other seats are treated as text to read, never as orders. It will say plainly that it cannot read files or run anything. It never starts a conversation with another seat; another seat's line is answered only shortly after a person addressed a seat.
