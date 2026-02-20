import math

from robocode_tank_royale.bot_api import Bot
from robocode_tank_royale.bot_api.color import Color
from robocode_tank_royale.bot_api.events import (
    ScannedBotEvent,
    HitBotEvent,
    HitWallEvent,
    BotDeathEvent,
    BulletHitBotEvent,
)


class Berserker(Bot):
    """
    Pure aggression tank. Charges enemies, fires at maximum rate, and never
    retreats. Maximizes damage output at the cost of self-preservation.

    Strategy:
    - Movement: Always charge directly at the last scanned enemy
    - Gun: Lock onto target, fire at max power (3.0) when close, adapt at range
    - Radar: Tight lock on current target, wide sweep when no target
    - Philosophy: Die in a blaze of glory
    """

    def __init__(self) -> None:
        super().__init__()
        self._target_x: float = 0.0
        self._target_y: float = 0.0
        self._target_energy: float = 100.0
        self._target_id: int = -1
        self._target_speed: float = 0.0
        self._target_direction: float = 0.0
        self._has_target: bool = False
        self._scan_direction: int = 1  # 1 or -1 for sweep direction
        self._ticks_since_scan: int = 0

    def run(self) -> None:
        # War paint: blood red body, black gun, fire-orange radar
        self.body_color = Color.from_rgb(0xCC, 0x00, 0x00)
        self.turret_color = Color.from_rgb(0x20, 0x20, 0x20)
        self.radar_color = Color.from_rgb(0xFF, 0x66, 0x00)
        self.bullet_color = Color.from_rgb(0xFF, 0xFF, 0x00)
        self.scan_color = Color.from_rgb(0xFF, 0x33, 0x00)
        self.tracks_color = Color.from_rgb(0x44, 0x00, 0x00)
        self.gun_color = Color.from_rgb(0x44, 0x44, 0x44)

        # Decouple gun and radar from body so we can aim while charging
        self.adjust_gun_for_body_turn = True
        self.adjust_radar_for_body_turn = True
        self.adjust_radar_for_gun_turn = True

        self._has_target = False
        self._ticks_since_scan = 0

        while self.running:
            self._ticks_since_scan += 1

            if self._has_target and self._ticks_since_scan < 30:
                self._charge_target()
                self._aim_and_fire()
                self._lock_radar()
            else:
                # No target or stale data: hunt aggressively
                self._hunt()

            self.go()

    # ── Movement: charge straight at the enemy ──

    def _charge_target(self) -> None:
        bearing = self.bearing_to(self._target_x, self._target_y)
        distance = self.distance_to(self._target_x, self._target_y)

        # Turn toward target and charge at full speed
        self.set_turn_left(bearing)

        if abs(bearing) < 40:
            # Close enough angle to charge
            self.set_forward(distance + 50)
        else:
            # Need to turn more — move a bit to avoid sitting still
            self.set_forward(50)

    # ── Gun: lead the target and fire as soon as possible ──

    def _aim_and_fire(self) -> None:
        distance = self.distance_to(self._target_x, self._target_y)

        # Choose firepower: max damage always, but ensure we can actually fire
        # At max power (3.0): 16 damage, best damage-per-turn ratio
        if distance < 150:
            power = 3.0
        elif distance < 400:
            power = 2.5
        else:
            power = 2.0

        # Don't spend more energy than we have (minus a small reserve)
        power = min(power, self.energy - 0.1)
        if power < 0.1:
            power = 0.1

        # Lead the target: predict where it will be when the bullet arrives
        bullet_speed = 20.0 - 3.0 * power
        travel_time = distance / bullet_speed

        # Predict future position based on enemy speed and direction
        future_x = self._target_x + math.cos(math.radians(self._target_direction)) * self._target_speed * travel_time
        future_y = self._target_y + math.sin(math.radians(self._target_direction)) * self._target_speed * travel_time

        # Clamp to arena bounds
        margin = 20.0
        future_x = max(margin, min(self.arena_width - margin, future_x))
        future_y = max(margin, min(self.arena_height - margin, future_y))

        # Turn gun to predicted position
        gun_bearing = self.gun_bearing_to(future_x, future_y)
        self.set_turn_gun_left(gun_bearing)

        # Fire as soon as gun is roughly aimed (don't wait for perfect alignment)
        if abs(gun_bearing) < 15 and self.gun_heat == 0:
            self.set_fire(power)

    # ── Radar: tight lock on target, wide sweep when hunting ──

    def _lock_radar(self) -> None:
        # Narrow radar lock: point at target with slight overshoot to maintain scan arc
        radar_bearing = self.radar_bearing_to(self._target_x, self._target_y)
        # Add extra sweep to ensure we don't lose the target
        extra = 15.0 * self._scan_direction
        self.set_turn_radar_left(radar_bearing + extra)

    def _hunt(self) -> None:
        # No target: spin radar as fast as possible while moving aggressively
        self.set_turn_radar_left(45 * self._scan_direction)
        # Move around to find targets — zigzag forward
        self.set_forward(200)
        self.set_turn_right(30)

    # ── Events ──

    def on_scanned_bot(self, e: ScannedBotEvent) -> None:
        # Always lock onto the scanned bot — we want ANY target
        self._target_x = float(e.x)
        self._target_y = float(e.y)
        self._target_energy = float(e.energy)
        self._target_id = e.scanned_bot_id
        self._target_speed = float(e.speed)
        self._target_direction = float(e.direction)
        self._has_target = True
        self._ticks_since_scan = 0

        # Reverse sweep direction for radar lock
        self._scan_direction *= -1

    def on_hit_bot(self, e: HitBotEvent) -> None:
        # Rammed an enemy — point-blank fire at maximum power!
        gun_bearing = self.gun_bearing_to(float(e.x), float(e.y))
        self.set_turn_gun_left(gun_bearing)
        if abs(gun_bearing) < 30:
            self.set_fire(3.0)
        # Keep pushing through them
        self.set_forward(40)

    def on_hit_wall(self, e: HitWallEvent) -> None:
        # Don't care about walls — just bounce off and keep going
        del e
        self.set_back(50)
        self.set_turn_right(90)

    def on_bot_death(self, e: BotDeathEvent) -> None:
        # If our target died, clear it and hunt for the next victim
        if e.victim_id == self._target_id:
            self._has_target = False
            self._ticks_since_scan = 100  # Force immediate hunt mode

    def on_bullet_hit(self, e: BulletHitBotEvent) -> None:
        # Track the target we just hit — update their energy
        del e
        # Energy gain is handled by the engine, just keep firing


def main() -> None:
    bot = Berserker()
    bot.start()


if __name__ == "__main__":
    main()
