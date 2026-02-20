#!/usr/bin/env bash
# Creates the scaffolding for a new Python bot
# Usage: ./scripts/new-bot.sh BotName "Bot Description" "Author Name"

set -e

BOT_NAME="${1:?Usage: new-bot.sh BotName \"Description\" \"Author\"}"
BOT_DESC="${2:-A Robocode Tank Royale bot}"
BOT_AUTHOR="${3:-Anonymous}"

BOT_DIR="bots/${BOT_NAME}"

if [ -d "$BOT_DIR" ]; then
    echo "Error: Bot directory '$BOT_DIR' already exists."
    exit 1
fi

mkdir -p "$BOT_DIR"

# Create Python source
cat > "${BOT_DIR}/${BOT_NAME}.py" << 'PYEOF'
from robocode_tank_royale.bot_api import Bot
from robocode_tank_royale.bot_api.events import ScannedBotEvent, HitByBulletEvent, HitWallEvent


class BOTNAME(Bot):
    def run(self) -> None:
        """Called when a new round starts."""
        while self.running:
            # TODO: Implement your strategy here
            self.forward(100)
            self.turn_gun_left(360)
            self.back(100)
            self.turn_gun_left(360)

    def on_scanned_bot(self, e: ScannedBotEvent) -> None:
        """Enemy detected by radar."""
        self.fire(1)

    def on_hit_by_bullet(self, e: HitByBulletEvent) -> None:
        """We were hit by a bullet."""
        bearing = self.calc_bearing(e.bullet.direction)
        self.turn_right(90 - bearing)

    def on_hit_wall(self, e: HitWallEvent) -> None:
        """We hit a wall."""
        self.back(50)


def main() -> None:
    bot = BOTNAME()
    bot.start()


if __name__ == "__main__":
    main()
PYEOF

# Replace placeholder with actual bot name
sed -i "s/BOTNAME/${BOT_NAME}/g" "${BOT_DIR}/${BOT_NAME}.py"

# Create JSON config
cat > "${BOT_DIR}/${BOT_NAME}.json" << JSONEOF
{
  "name": "${BOT_NAME}",
  "version": "1.0",
  "authors": ["${BOT_AUTHOR}"],
  "description": "${BOT_DESC}",
  "homepage": "",
  "countryCodes": ["us"],
  "platform": "Python",
  "programmingLang": "Python 3"
}
JSONEOF

# Create Windows launcher
cat > "${BOT_DIR}/${BOT_NAME}.cmd" << CMDEOF
@echo off
python ${BOT_NAME}.py %*
CMDEOF

# Create Unix launcher
cat > "${BOT_DIR}/${BOT_NAME}.sh" << SHEOF
#!/usr/bin/env sh
python3 "\$(dirname "\$0")/${BOT_NAME}.py" "\$@"
SHEOF

chmod 755 "${BOT_DIR}/${BOT_NAME}.sh"

echo "Created bot '${BOT_NAME}' in ${BOT_DIR}/"
echo "Files:"
ls -la "${BOT_DIR}/"
