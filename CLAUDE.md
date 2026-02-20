# Robocode Tank Royale - Python Bot Development

## Project Overview

This is a Python bot development repository for **Robocode Tank Royale**. Bots created here compete in automated tank battles within the Tank Royale arena.

## Related Repositories

- `C:\repos\tank-royale` - Tank Royale source code (includes sample bots in `sample-bots/python/`)
- `C:\repos\tank-royale-viewer` - Battle viewer application

## Documentation

See the `docs/` directory for detailed reference documentation, including full API reference and game mechanics.

## Bot Structure

Each bot lives in its own directory under `bots/`:

```
bots/
  MyBot/
    MyBot.py       # Python source code
    MyBot.json     # Bot configuration
    MyBot.cmd      # Windows launcher
    MyBot.sh       # Unix launcher
```

### BotName.json (Configuration)

```json
{
  "name": "BotName",
  "version": "1.0",
  "authors": ["Author Name"],
  "description": "Short description of the bot strategy.",
  "platform": "Python",
  "programmingLang": "Python"
}
```

### BotName.cmd (Windows Launcher)

```batch
@echo off
python BotName.py %*
```

### BotName.sh (Unix Launcher)

```sh
#!/usr/bin/env sh
python3 "$(dirname "$0")/BotName.py" "$@"
```

## Python API Basics

### Installation

```bash
pip install robocode-tank-royale
```

### Import and Bot Class

```python
from robocode_tank_royale.bot_api import Bot

class MyBot(Bot):
    def run(self):
        while self.running:
            # Main loop
            pass

    # Override event handlers as needed
```

A bot extends `Bot`, overrides `run()` for the main loop, and overrides event handler methods to react to game events.

### Blocking Methods

These methods execute and block until the action completes:

- `forward(distance)` - Move forward
- `back(distance)` - Move backward
- `turn_left(degrees)` - Turn body left
- `turn_right(degrees)` - Turn body right
- `turn_gun_left(degrees)` - Turn gun left
- `turn_gun_right(degrees)` - Turn gun right
- `fire(firepower)` - Fire the gun

### Non-Blocking Setter Methods

These set the action but return immediately. Call `go()` to execute all pending actions for one tick:

- `set_forward(distance)`, `set_back(distance)`
- `set_turn_left(degrees)`, `set_turn_right(degrees)`
- `set_turn_gun_left(degrees)`, `set_turn_gun_right(degrees)`
- `set_turn_radar_left(degrees)`, `set_turn_radar_right(degrees)`
- `set_fire(firepower)`

Use with `go()` to execute multiple actions simultaneously each turn.

### Key Properties

- **Position/Direction:** `x`, `y`, `direction`, `gun_direction`, `radar_direction`
- **State:** `energy`, `speed`, `gun_heat`, `enemy_count`, `running`

### Helper Methods

- `calc_bearing(direction)` - Calculate bearing from bot direction
- `bearing_to(x, y)` - Bearing from bot to point
- `gun_bearing_to(x, y)` - Bearing from gun to point
- `distance_to(x, y)` - Distance from bot to point
- `direction_to(x, y)` - Absolute direction to point

## Key Game Constants

| Constant | Value |
|----------|-------|
| Max speed | 8 units/turn |
| Acceleration | 1 unit/turn |
| Deceleration | 2 units/turn |
| Max body turn rate | 10 - 0.75 * abs(speed) deg/turn |
| Max gun turn rate | 20 deg/turn |
| Max radar turn rate | 45 deg/turn |
| Firepower range | 0.1 - 3.0 |
| Bullet speed | 20 - 3 * firepower |
| Bullet damage | 4 * firepower (+ 2*(firepower-1) bonus if firepower > 1) |
| Gun heat on fire | 1 + firepower / 5 |
| Energy gained on hit | 3 * firepower |
| Scan radius | 1200 units |
| Bot bounding circle radius | 18 units |
