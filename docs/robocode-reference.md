# Robocode Tank Royale - Comprehensive Reference

## 1. Game Mechanics

### Battle / Round / Turn Structure

- A **battle** consists of multiple **rounds**.
- Each **round** runs until one or zero bots remain (or a timeout).
- Each **turn** (tick) is a discrete time step within a round. During each turn:
  1. All bots execute their pending actions simultaneously.
  2. Bullets move.
  3. Collisions are resolved.
  4. Scans are performed.
  5. Events are dispatched to bots.

### Energy System

- Each bot starts with **100 energy**.
- **Losing energy:**
  - Firing: costs the firepower amount (0.1 to 3.0).
  - Being hit by a bullet: loses `4 * firepower` damage (plus `2 * (firepower - 1)` bonus if firepower > 1).
  - Colliding with another bot: loses **0.6 energy**.
  - Colliding with a wall: loses `max(0, abs(speed) / 2 - 1)` energy.
- **Gaining energy:**
  - When your bullet hits an opponent: gain `3 * firepower` energy.
- A bot is **disabled** (cannot move or fire) when energy drops to 0, and is **destroyed** when energy goes below 0.

### Physics

#### Movement

- Bots move forward or backward along their body heading.
- **Max speed:** 8 units/turn.
- **Acceleration:** 1 unit/turn (when speeding up).
- **Deceleration:** 2 units/turn (when slowing down or reversing).
- Bots cannot exceed max speed; the engine clamps velocity.

#### Turning

- **Body turn rate:** `10 - 0.75 * abs(speed)` degrees/turn. Faster bots turn slower.
- **Gun turn rate:** 20 degrees/turn (maximum).
- **Radar turn rate:** 45 degrees/turn (maximum).
- All three components (body, gun, radar) can turn independently in the same tick when using setter methods.

#### Coordinate System

- The arena origin (0, 0) is at the bottom-left corner.
- X increases to the right, Y increases upward.
- 0 degrees is up (north), angles increase clockwise.

### Bullet Mechanics

- **Firepower range:** 0.1 to 3.0.
- **Bullet speed:** `20 - 3 * firepower` units/turn. Lower firepower = faster bullets.
- **Bullet damage:** `4 * firepower`. If firepower > 1, an additional `2 * (firepower - 1)` bonus damage is applied.
- **Gun heat on fire:** `1 + firepower / 5`. The gun cannot fire while heat > 0.
- **Gun cooling rate:** Configurable per battle (default: 0.1 per turn).
- Bullets travel in a straight line from the gun position at the moment of firing.

### Scanning

- The **radar** emits a scan arc each turn based on how far the radar rotated.
- The scan arc sweeps from the radar's previous direction to its current direction.
- Any bot whose center falls within the scan arc (up to **1200 units** radius) triggers a `ScannedBotEvent`.
- If the radar does not rotate, the scan arc is zero and nothing is detected.
- Tip: To get a wide scan, rotate the radar; to lock onto a target, minimize radar movement around the target bearing.

### Collisions

- **Bot-to-bot collision:** Both bots lose **0.6 energy**. Bots are pushed apart so they no longer overlap. A `HitBotEvent` is fired.
- **Bot-to-wall collision:** The bot loses `max(0, abs(speed) / 2 - 1)` energy. The bot is stopped at the wall boundary. A `HitWallEvent` is fired.
- **Bullet-to-bot collision:** The target bot takes bullet damage. The firing bot gains `3 * firepower` energy. A `BulletHitBotEvent` is fired to both bots.
- **Bullet-to-bullet collision:** Both bullets are destroyed. A `BulletHitBulletEvent` is fired to both owners.
- **Bullet-to-wall collision:** The bullet is destroyed. A `BulletHitWallEvent` is fired to the owner.

---

## 2. Tank Anatomy

### Three Independent Components

1. **Body** - Controls movement (forward, back, turning). The base of the tank.
2. **Gun (Turret)** - Mounted on the body. Controls firing direction. Rotates independently from body.
3. **Radar** - Mounted on the gun. Controls scanning direction. Rotates independently from gun.

### Rotation Hierarchy

- The **gun** is mounted on the **body**: when the body rotates, the gun rotates with it by default.
- The **radar** is mounted on the **gun**: when the gun rotates, the radar rotates with it by default.
- This creates a chain: body rotation affects gun, gun rotation affects radar.

### Independent Control (Adjustment)

To decouple rotation, use the adjustment properties:

- `is_adjust_gun_for_body_turn` (bool) - When `True`, the gun does NOT rotate when the body turns. Default: `False`.
- `is_adjust_radar_for_gun_turn` (bool) - When `True`, the radar does NOT rotate when the gun turns. Default: `False`.
- `is_adjust_radar_for_body_turn` (bool) - When `True`, the radar does NOT rotate when the body turns. Default: `False`.

For competitive bots, set all three to `True` and control each component explicitly.

### Bot Bounding Circle

- Each bot has a circular bounding area with radius **18 units** centered on its position.
- This circle is used for all collision detection (bullets, walls, other bots).

---

## 3. Python Bot API Complete Reference

### Blocking Methods

These methods block execution until the action finishes (i.e., movement or rotation completes).

| Method | Description |
|--------|-------------|
| `forward(distance: float)` | Move forward by `distance` units. Negative values move backward. |
| `back(distance: float)` | Move backward by `distance` units. Negative values move forward. |
| `turn_left(degrees: float)` | Turn body left by `degrees`. Negative values turn right. |
| `turn_right(degrees: float)` | Turn body right by `degrees`. Negative values turn left. |
| `turn_gun_left(degrees: float)` | Turn gun left by `degrees`. |
| `turn_gun_right(degrees: float)` | Turn gun right by `degrees`. |
| `turn_radar_left(degrees: float)` | Turn radar left by `degrees`. |
| `turn_radar_right(degrees: float)` | Turn radar right by `degrees`. |
| `fire(firepower: float)` | Fire the gun with given firepower (0.1-3.0). Blocks until gun fires. |
| `rescan()` | Perform another scan with the current radar position. |
| `wait_for(condition)` | Block until a condition is met. |

### Non-Blocking Setter Methods

These methods set a pending action and return immediately. Call `go()` to execute all pending actions for one tick.

| Method | Description |
|--------|-------------|
| `set_forward(distance: float)` | Set forward distance for next tick(s). |
| `set_back(distance: float)` | Set backward distance for next tick(s). |
| `set_turn_left(degrees: float)` | Set body turn left for next tick(s). |
| `set_turn_right(degrees: float)` | Set body turn right for next tick(s). |
| `set_turn_gun_left(degrees: float)` | Set gun turn left for next tick(s). |
| `set_turn_gun_right(degrees: float)` | Set gun turn right for next tick(s). |
| `set_turn_radar_left(degrees: float)` | Set radar turn left for next tick(s). |
| `set_turn_radar_right(degrees: float)` | Set radar turn right for next tick(s). |
| `set_fire(firepower: float)` | Set fire for next tick. Returns `True` if gun is ready. |
| `set_stop()` | Stop all pending movement and turning. |
| `set_resume()` | Resume previously stopped movement. |
| `go()` | Execute all pending actions for one tick. **Must be called to advance the turn.** |

### Properties (Read-Only State)

| Property | Type | Description |
|----------|------|-------------|
| `x` | float | Bot's X position on the arena. |
| `y` | float | Bot's Y position on the arena. |
| `direction` | float | Bot body heading in degrees (0 = north, clockwise). |
| `gun_direction` | float | Gun heading in degrees. |
| `radar_direction` | float | Radar heading in degrees. |
| `energy` | float | Current energy level. |
| `speed` | float | Current speed (positive = forward, negative = backward). |
| `gun_heat` | float | Current gun heat. Gun fires when heat reaches 0. |
| `enemy_count` | int | Number of enemies remaining in the round. |
| `running` | bool | `True` while the bot is active in the round. |
| `turn_number` | int | Current turn number. |
| `round_number` | int | Current round number. |
| `number_of_rounds` | int | Total rounds in the battle. |
| `arena_width` | float | Width of the arena. |
| `arena_height` | float | Height of the arena. |
| `game_type` | str | Type of game (e.g., "classic", "melee"). |

### Properties (Turn Rates / Remaining)

| Property | Type | Description |
|----------|------|-------------|
| `turn_rate` | float | Current body turn rate (deg/turn). |
| `gun_turn_rate` | float | Current gun turn rate (deg/turn). |
| `radar_turn_rate` | float | Current radar turn rate (deg/turn). |
| `max_turn_rate` | float | Maximum body turn rate at current speed. |
| `max_gun_turn_rate` | float | Maximum gun turn rate (20). |
| `max_radar_turn_rate` | float | Maximum radar turn rate (45). |
| `distance_remaining` | float | Distance remaining in current move. |
| `turn_remaining` | float | Degrees remaining in current body turn. |
| `gun_turn_remaining` | float | Degrees remaining in current gun turn. |
| `radar_turn_remaining` | float | Degrees remaining in current radar turn. |

### Properties (Adjustment Flags)

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `is_adjust_gun_for_body_turn` | bool | False | Decouple gun from body rotation. |
| `is_adjust_radar_for_gun_turn` | bool | False | Decouple radar from gun rotation. |
| `is_adjust_radar_for_body_turn` | bool | False | Decouple radar from body rotation. |

### Properties (Colors)

Set these to customize bot appearance. Accepts color values or `None` for default.

| Property | Description |
|----------|-------------|
| `body_color` | Body fill color. |
| `turret_color` | Gun turret color. |
| `radar_color` | Radar dish color. |
| `bullet_color` | Bullet color. |
| `scan_color` | Scan arc color. |
| `tracks_color` | Tank track color. |
| `gun_color` | Gun barrel color. |

Colors can be set using `Color.from_string("#RRGGBB")` or predefined constants from `robocode_tank_royale.bot_api`.

### Calculation / Helper Methods

| Method | Description |
|--------|-------------|
| `calc_bearing(direction: float) -> float` | Normalize bearing relative to bot heading. Returns -180 to 180. |
| `bearing_to(x: float, y: float) -> float` | Bearing from bot heading to a point. Returns -180 to 180. |
| `gun_bearing_to(x: float, y: float) -> float` | Bearing from gun heading to a point. |
| `radar_bearing_to(x: float, y: float) -> float` | Bearing from radar heading to a point. |
| `distance_to(x: float, y: float) -> float` | Euclidean distance from bot to a point. |
| `direction_to(x: float, y: float) -> float` | Absolute direction (0-360) from bot to a point. |
| `normalize_absolute_angle(angle: float) -> float` | Normalize angle to 0-360 range. |
| `normalize_relative_angle(angle: float) -> float` | Normalize angle to -180 to 180 range. |
| `calc_bullet_speed(firepower: float) -> float` | Calculate bullet speed: `20 - 3 * firepower`. |
| `calc_gun_heat(firepower: float) -> float` | Calculate gun heat: `1 + firepower / 5`. |
| `calc_max_turn_rate(speed: float) -> float` | Calculate max body turn rate at given speed. |

---

## 4. Event System

### Event Queue

- Events are placed in a queue each turn and dispatched in priority order (highest first).
- Events **expire after 2 turns** if not processed (they are removed from the queue).
- **Critical events** never expire and are always delivered: `ScannedBotEvent`, `SkippedTurnEvent`.

### Default Event Priorities

Higher number = processed first.

| Event | Default Priority | Description |
|-------|-----------------|-------------|
| `WonRoundEvent` | 100 | Bot won the round. |
| `SkippedTurnEvent` | 95 | Bot skipped a turn (took too long). Critical. |
| `CustomEvent` | 80 | User-defined condition triggered. |
| `BotDeathEvent` | 70 | Another bot was destroyed. |
| `BulletHitWallEvent` | 60 | Your bullet hit a wall. |
| `BulletHitBulletEvent` | 55 | Your bullet hit another bullet. |
| `BulletHitBotEvent` | 50 | Your bullet hit another bot. |
| `HitByBulletEvent` | 40 | You were hit by a bullet. |
| `HitWallEvent` | 35 | You hit a wall. |
| `HitBotEvent` | 30 | You collided with another bot. |
| `ScannedBotEvent` | 20 | Your radar detected a bot. Critical. |
| `DeathEvent` | 10 | Your bot was destroyed. |
| `TickEvent` | 0 | Start of a new turn. |
| `RoundStartedEvent` | -1 | Round has started. |
| `RoundEndedEvent` | -2 | Round has ended. |
| `GameEndedEvent` | -3 | Game (battle) has ended. |
| `ConnectedEvent` | -4 | Bot connected to server. |
| `DisconnectedEvent` | -5 | Bot disconnected from server. |

### Event Handlers

Override these methods in your bot class to handle events:

| Handler Method | Event Object | Key Fields |
|----------------|-------------|------------|
| `on_scanned_bot(event)` | `ScannedBotEvent` | `scanned_bot_id`, `x`, `y`, `direction`, `energy`, `speed` |
| `on_hit_by_bullet(event)` | `HitByBulletEvent` | `bullet` (with `x`, `y`, `direction`, `firepower`, `speed`, `owner_id`) |
| `on_bullet_hit(event)` | `BulletHitBotEvent` | `bullet`, `victim_id`, `energy` |
| `on_hit_wall(event)` | `HitWallEvent` | `bot_id` |
| `on_hit_bot(event)` | `HitBotEvent` | `bot_id`, `x`, `y`, `energy`, `is_rammed` |
| `on_bullet_hit_wall(event)` | `BulletHitWallEvent` | `bullet` |
| `on_bullet_hit_bullet(event)` | `BulletHitBulletEvent` | `bullet`, `hit_bullet` |
| `on_death(event)` | `DeathEvent` | `bot_id` |
| `on_bot_death(event)` | `BotDeathEvent` | `bot_id` |
| `on_won_round(event)` | `WonRoundEvent` | `bot_id` |
| `on_skipped_turn(event)` | `SkippedTurnEvent` | `bot_id` |
| `on_tick(event)` | `TickEvent` | `turn_number`, `events` |
| `on_round_started(event)` | `RoundStartedEvent` | `round_number` |
| `on_round_ended(event)` | `RoundEndedEvent` | `round_number`, `turn_number`, `results` |
| `on_game_ended(event)` | `GameEndedEvent` | `number_of_rounds`, `results` |
| `on_connected(event)` | `ConnectedEvent` | `server_url` |
| `on_disconnected(event)` | `DisconnectedEvent` | `server_url` |
| `on_custom_event(event)` | `CustomEvent` | `condition` |

### Event Handler Best Practices

- Keep event handlers **fast and lightweight**. Heavy computation blocks the bot.
- Store data from events (e.g., enemy positions) in instance variables for use in `run()`.
- Do not call blocking methods inside event handlers unless you understand the interruption behavior.
- Use `set_*` methods inside event handlers and let `go()` in the main loop execute them.

---

## 5. Bot Architecture Recommendations

### Three-Strategy Pattern

Structure your bot logic into three independent strategies:

1. **Movement Strategy** - How the bot moves to avoid damage.
2. **Gun Strategy** - How the bot aims and fires at opponents.
3. **Scanning Strategy** - How the bot uses radar to gather enemy information.

### Recommended Main Loop

```python
def run(self):
    # Enable independent control
    self.is_adjust_gun_for_body_turn = True
    self.is_adjust_radar_for_gun_turn = True
    self.is_adjust_radar_for_body_turn = True

    while self.running:
        self.do_movement()
        self.do_gun()
        self.do_scanning()
        self.go()
```

Using setters + `go()` allows all three strategies to execute simultaneously each tick.

### Movement Strategies

- **Oscillating / Zigzag:** Alternate forward and backward movement with random distances.
- **Circular:** Constant forward movement with constant turn rate.
- **Wall smoothing:** Follow walls while maintaining distance.
- **Bullet dodging:** Change direction when enemy fires (detect energy drop).

### Gun Strategies

- **Head-on targeting:** Aim directly at the enemy's current position.
- **Linear targeting:** Predict where the enemy will be based on current speed and heading.
- **Circular targeting:** Predict based on enemy's turning rate.
- **Virtual bullets:** Simulate multiple targeting algorithms and use the one that hits most often.

### Scanning Strategies

- **Spinning radar:** Continuously spin radar for broad awareness (good for melee).
- **Narrow lock:** Oscillate radar narrowly around a target for tight tracking (good for 1v1).
- **Widening search:** Start narrow, widen if target is lost.

### Advanced Concepts

- **Wave surfing:** Track incoming bullet waves and move to positions with lowest hit probability.
- **Enemy energy tracking:** Detect enemy fire by monitoring energy drops in `ScannedBotEvent`.
- **Segmented statistics:** Record enemy movement patterns indexed by various factors (distance, velocity, wall proximity).
- **Anti-gravity movement:** Assign repulsive forces to enemies and walls, move along the resultant vector.

---

## 6. File Structure

### Directory Layout

```
bots/
  BotName/
    BotName.py         # Bot source code
    BotName.json       # Bot configuration
    BotName.cmd        # Windows launcher
    BotName.sh         # Unix launcher
```

### JSON Config Format

```json
{
  "name": "BotName",
  "version": "1.0",
  "authors": ["Author Name"],
  "description": "Brief description of the bot's strategy and behavior.",
  "platform": "Python",
  "programmingLang": "Python"
}
```

All fields are required. The `name` field must match the directory and file names exactly.

### Windows Launcher (BotName.cmd)

```batch
@echo off
python BotName.py %*
```

### Unix Launcher (BotName.sh)

```sh
#!/usr/bin/env sh
python3 "$(dirname "$0")/BotName.py" "$@"
```

Make sure to set the executable bit on Unix: `chmod +x BotName.sh`.

---

## 7. Sample Bot Strategies

### MyFirstBot

The simplest bot. Moves forward 100 units, turns the gun 360 degrees (scanning as it goes), moves back 100 units, and repeats. Fires when it detects an enemy. Good starting template.

### Corners

Moves to a corner of the arena and camps there. Spins the gun to scan for enemies and fires when targets are found. If hit, it may select a different corner. Effective in melee where corner positions reduce exposure angles.

### Fire

Stays mostly stationary. Tracks enemies by turning the gun toward scanned bots. Adjusts fire power based on distance (higher power at close range). Moves slightly when hit to avoid being an easy target.

### Walls

Follows the arena walls in a rectangular path, moving along the perimeter. Fires at enemies when they are scanned during the patrol. Uses wall-riding for predictable but hard-to-hit-with-linear-targeting movement.

### SpinBot

Moves in tight circles by combining constant forward movement with constant turning. Fires maximum firepower (3.0) whenever the gun is cool. The circular movement makes it hard to hit with simple targeting, but it is predictable against advanced targeting.

### TrackFire

Turns the gun to track scanned enemies and fires when the gun is approximately aimed. Adjusts fire power based on energy remaining. A step up from MyFirstBot with dedicated gun tracking logic.

### RamFire

Aggressively drives toward the nearest scanned enemy and attempts to ram them. Uses head-on movement to close distance. Fires at close range with high firepower. Gains energy from hits while dealing ram damage. Effective against stationary or slow bots.

### Crazy

Moves in unpredictable zigzag patterns with random distance and turn amounts. Designed to be hard to target. Fires opportunistically when enemies are scanned. Relies on evasion rather than precise targeting.

### VelocityBot

Demonstrates speed control and turn rate management. Adjusts target speed and turn rates based on enemy positions. Shows how to use the relationship between speed and turn rate (faster movement = slower turning) strategically.
