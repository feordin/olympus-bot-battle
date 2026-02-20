# Olympus Bot Battle

A shared repository for the Olympus team to develop and battle Python bots in [Robocode Tank Royale](https://robocode-dev.github.io/tank-royale/). Each team member builds autonomous tank bots that compete against each other in the arena.

## Getting Started

### Prerequisites

- Python 3
- [Robocode Tank Royale](https://robocode-dev.github.io/tank-royale/) game server

### Install Dependencies

```bash
pip install robocode-tank-royale
```

### Create a New Bot

1. Create a new directory under `bots/` with your bot's name
2. Add the required files:

```
bots/
  YourBot/
    YourBot.py       # Bot source code
    YourBot.json     # Bot configuration (name, author, description)
    YourBot.cmd      # Windows launcher
    YourBot.sh       # Unix launcher
```

3. Your bot extends the `Bot` class and implements a `run()` method:

```python
from robocode_tank_royale.bot_api import Bot

class YourBot(Bot):
    def run(self):
        while self.running:
            # Your strategy here
            pass
```

See the `docs/` directory for the full API reference and game mechanics.

## Included Bots

| Bot | Description |
|-----|-------------|
| Berserker | Pure aggression -- charges enemies and fires at max power |
| Corners | Hides in corners and fires at passing enemies |
| Crazy | Moves erratically to avoid being hit |
| Fire | Fires at enemies when scanned |
| MyFirstBot | Simple example bot for learning the API |
| MyFirstDroid / MyFirstLeader | Team bot examples (droid + leader) |
| PaintingBot | Demonstrates the painting API |
| RamFire | Rams into enemies and fires on collision |
| SpinBot | Spins in circles while firing at max power |
| Target | Stationary target for testing |
| TrackFire | Tracks and fires at the nearest enemy |
| VelocityBot | Demonstrates velocity-based movement |
| Walls | Navigates along the arena walls with gun pointed inward |

## Documentation

- `docs/robocode-reference.md` -- Full API reference and game constants
- `docs/PromptHistory.md` -- History of AI-assisted bot development prompts
