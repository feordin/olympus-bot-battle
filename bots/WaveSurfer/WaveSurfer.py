"""
WaveSurfer — A wave-surfing defensive bot for Robocode Tank Royale.

Strategy overview:
  Movement: Wave surfing. Detects enemy fire by monitoring energy drops,
            tracks expanding bullet "waves", and moves to the position on
            each wave with the lowest historical hit probability using
            GuessFactor statistics.
  Gun:      Linear predictive targeting. Leads the target based on current
            speed and heading.
  Radar:    Tight 1v1 radar lock with a small overshoot sweep to maintain
            continuous scans.
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional

from robocode_tank_royale.bot_api import Bot
from robocode_tank_royale.bot_api.color import Color
from robocode_tank_royale.bot_api.events import (
    BotDeathEvent,
    HitBotEvent,
    HitWallEvent,
    ScannedBotEvent,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NUM_BINS = 47  # GuessFactor bins covering -1.0 … +1.0
MIDDLE_BIN = NUM_BINS // 2  # Index corresponding to GuessFactor 0
WALL_MARGIN = 40.0  # Stay this far from walls when surfing
BOT_RADIUS = 18.0  # Bounding circle radius per game rules


# ---------------------------------------------------------------------------
# Wave data class
# ---------------------------------------------------------------------------

@dataclass
class Wave:
    """Represents an expanding bullet wave fired by the enemy."""

    origin_x: float  # Enemy position when it fired
    origin_y: float
    fire_time: int  # Turn number when the bullet was fired
    bullet_speed: float  # 20 - 3 * firepower
    direction_to_target: float  # Absolute angle from enemy to us at fire time
    lateral_direction: int  # Our lateral movement direction at fire time (+1 / -1)

    def distance_traveled(self, current_turn: int) -> float:
        """Distance the bullet has traveled since it was fired."""
        return (current_turn - self.fire_time) * self.bullet_speed

    def has_reached(self, bot_x: float, bot_y: float, current_turn: int) -> bool:
        """True if the wave has passed the bot's position."""
        dist_to_bot = math.hypot(bot_x - self.origin_x, bot_y - self.origin_y)
        return self.distance_traveled(current_turn) >= dist_to_bot - BOT_RADIUS


# ---------------------------------------------------------------------------
# WaveSurfer bot
# ---------------------------------------------------------------------------

class WaveSurfer(Bot):
    """
    Wave-surfing defensive bot.

    Detects enemy fire via energy-drop monitoring, tracks expanding bullet
    waves, and dodges to the lowest-danger GuessFactor position.  Uses linear
    predictive targeting for offense.
    """

    def __init__(self) -> None:
        super().__init__()

        # --- Enemy state ---
        self._enemy_x: float = 0.0
        self._enemy_y: float = 0.0
        self._enemy_speed: float = 0.0
        self._enemy_direction: float = 0.0
        self._enemy_energy: float = 100.0
        self._enemy_id: int = -1
        self._has_target: bool = False
        self._last_enemy_energy: float = 100.0

        # --- Wave surfing ---
        self._waves: List[Wave] = []
        self._danger_bins: List[float] = [0.0] * NUM_BINS
        self._surf_direction: int = 1  # +1 = clockwise orbit, -1 = counter-clockwise

        # --- Radar ---
        self._scan_direction: int = 1
        self._ticks_since_scan: int = 0

    # ===================================================================
    # Main loop
    # ===================================================================

    def run(self) -> None:
        # Surfer theme: ocean blue / teal
        self.body_color = Color.from_rgb(0x00, 0x7A, 0x99)
        self.turret_color = Color.from_rgb(0x00, 0x55, 0x77)
        self.radar_color = Color.from_rgb(0x00, 0xCC, 0xCC)
        self.bullet_color = Color.from_rgb(0x99, 0xFF, 0xFF)
        self.scan_color = Color.from_rgb(0x00, 0xEE, 0xDD)
        self.tracks_color = Color.from_rgb(0x00, 0x44, 0x55)
        self.gun_color = Color.from_rgb(0x00, 0x66, 0x88)

        # Fully decouple body / gun / radar
        self.adjust_gun_for_body_turn = True
        self.adjust_radar_for_body_turn = True
        self.adjust_radar_for_gun_turn = True

        # Per-round resets (bins persist across rounds within a battle)
        self._waves.clear()
        self._has_target = False
        self._last_enemy_energy = 100.0
        self._ticks_since_scan = 0
        self._surf_direction = 1

        while self.running:
            self._ticks_since_scan += 1

            if self._has_target and self._ticks_since_scan < 30:
                self._do_surfing()
                self._do_gun()
                self._do_radar()
            else:
                self._hunt()

            self.go()

    # ===================================================================
    # Scanning — tight 1v1 radar lock
    # ===================================================================

    def _do_radar(self) -> None:
        """Narrow radar lock on the tracked enemy with slight overshoot."""
        radar_bearing = self.radar_bearing_to(self._enemy_x, self._enemy_y)
        extra = 15.0 * self._scan_direction
        self.set_turn_radar_left(radar_bearing + extra)

    def _hunt(self) -> None:
        """No target or stale scan — spin radar and orbit loosely."""
        self.set_turn_radar_left(45 * self._scan_direction)
        self.set_forward(150)
        self.set_turn_right(20)

    # ===================================================================
    # Wave surfing movement
    # ===================================================================

    def _do_surfing(self) -> None:
        """Evaluate the closest incoming wave and dodge to the safest bin."""
        # Remove waves that have already passed
        self._retire_passed_waves()

        # Find the closest active wave
        wave = self._closest_wave()

        if wave is not None:
            # Evaluate danger for both orbital directions
            danger_cw = self._evaluate_danger(wave, +1)
            danger_ccw = self._evaluate_danger(wave, -1)

            if danger_cw < danger_ccw:
                self._surf_direction = +1
            elif danger_ccw < danger_cw:
                self._surf_direction = -1
            # If equal, keep current direction (don't oscillate)

        # Execute orbital movement around the enemy
        self._orbit_enemy()

    def _orbit_enemy(self) -> None:
        """Move perpendicular to the enemy, with wall smoothing."""
        bearing = self.bearing_to(self._enemy_x, self._enemy_y)
        distance = self.distance_to(self._enemy_x, self._enemy_y)

        # Desired perpendicular heading: bearing ± 90°
        # Positive surf_direction → clockwise orbit (turn so enemy is to our left)
        offset = 90.0 * self._surf_direction

        # Slight inward/outward adjustment to maintain ~350-unit orbital distance
        preferred_dist = 350.0
        if distance < preferred_dist - 50:
            offset += 15.0  # Push outward a bit
        elif distance > preferred_dist + 80:
            offset -= 15.0  # Pull inward a bit

        # The turn needed to face our desired orbital heading
        ideal_turn = self._normalize(bearing + offset)

        # Wall smoothing: if our projected position would hit a wall, invert
        ahead_x = self.x + math.sin(math.radians(self.direction + ideal_turn)) * 160
        ahead_y = self.y + math.cos(math.radians(self.direction + ideal_turn)) * 160

        if not self._in_safe_zone(ahead_x, ahead_y):
            # Reverse orbital direction temporarily
            ideal_turn = self._normalize(bearing - offset)
            self._surf_direction *= -1

        self.set_turn_left(ideal_turn)

        # Always keep moving — speed makes us harder to hit
        if abs(ideal_turn) < 60:
            self.set_forward(150)
        else:
            self.set_forward(80)

    def _evaluate_danger(self, wave: Wave, direction: int) -> float:
        """Predict where we'd be if we orbit in `direction`, return danger."""
        # Simulate a few ticks of movement in the given direction
        sim_x, sim_y = self._project_position(direction, ticks=12)

        # Clamp to arena
        sim_x = max(WALL_MARGIN, min(self.arena_width - WALL_MARGIN, sim_x))
        sim_y = max(WALL_MARGIN, min(self.arena_height - WALL_MARGIN, sim_y))

        gf = self._guess_factor(wave, sim_x, sim_y)
        return self._get_danger(gf)

    def _project_position(self, direction: int, ticks: int) -> tuple:
        """Rough projection of our position after `ticks` turns of orbiting."""
        # Simplified: assume we move at ~6 units/tick perpendicular to enemy
        bearing_to_enemy = math.radians(self.direction_to(self._enemy_x, self._enemy_y))
        perp_angle = bearing_to_enemy + direction * (math.pi / 2)

        speed = 6.0
        proj_x = self.x + math.sin(perp_angle) * speed * ticks
        proj_y = self.y + math.cos(perp_angle) * speed * ticks
        return proj_x, proj_y

    # ===================================================================
    # GuessFactor statistics
    # ===================================================================

    def _guess_factor(self, wave: Wave, target_x: float, target_y: float) -> float:
        """
        Calculate the GuessFactor for a position relative to a wave.

        GF ranges from -1.0 (max counter-clockwise) to +1.0 (max clockwise)
        where the sign is relative to the lateral direction at fire time.
        """
        # Angle from the wave origin to the target position
        angle_to_target = math.degrees(
            math.atan2(target_x - wave.origin_x, target_y - wave.origin_y)
        )

        # Offset from where we were when the enemy fired
        offset = self._normalize(angle_to_target - wave.direction_to_target)

        # Max escape angle: the widest angle we could reach at this bullet speed
        max_escape_angle = self._max_escape_angle(wave.bullet_speed)

        if max_escape_angle == 0:
            return 0.0

        # Normalize to -1..+1 using lateral direction
        gf = (offset / max_escape_angle) * wave.lateral_direction
        return max(-1.0, min(1.0, gf))

    @staticmethod
    def _max_escape_angle(bullet_speed: float) -> float:
        """Maximum escape angle given bullet speed (in degrees)."""
        if bullet_speed <= 0:
            return 0.0
        # asin(bot_max_speed / bullet_speed), clamped
        ratio = 8.0 / bullet_speed
        if ratio >= 1.0:
            return 90.0
        return math.degrees(math.asin(ratio))

    def _get_danger(self, gf: float) -> float:
        """Look up the danger value for a GuessFactor from the bins."""
        index = self._gf_to_bin(gf)
        # Weighted sum of the target bin and neighbors for smoothing
        danger = 0.0
        for i in range(max(0, index - 2), min(NUM_BINS, index + 3)):
            dist = abs(i - index)
            weight = 1.0 / (1.0 + dist)
            danger += self._danger_bins[i] * weight
        return danger

    def _log_wave_hit(self, wave: Wave) -> None:
        """Record the GuessFactor where a wave crossed us into the bins."""
        gf = self._guess_factor(wave, self.x, self.y)
        index = self._gf_to_bin(gf)

        # Increment the hit bin and smooth into neighbors
        for i in range(max(0, index - 2), min(NUM_BINS, index + 3)):
            dist = abs(i - index)
            self._danger_bins[i] += 1.0 / (1.0 + dist * 0.5)

    @staticmethod
    def _gf_to_bin(gf: float) -> int:
        """Convert a GuessFactor (-1..+1) to a bin index."""
        index = int(round((gf + 1.0) * (NUM_BINS - 1) / 2.0))
        return max(0, min(NUM_BINS - 1, index))

    # ===================================================================
    # Wave management
    # ===================================================================

    def _retire_passed_waves(self) -> None:
        """Remove waves that have passed the bot, logging their hit data."""
        still_active: List[Wave] = []
        for wave in self._waves:
            if wave.has_reached(self.x, self.y, self.turn_number):
                self._log_wave_hit(wave)
            else:
                still_active.append(wave)
        self._waves = still_active

    def _closest_wave(self) -> Optional[Wave]:
        """Return the wave closest to reaching us, or None."""
        closest: Optional[Wave] = None
        closest_dist = float("inf")

        for wave in self._waves:
            dist_from_origin = math.hypot(self.x - wave.origin_x, self.y - wave.origin_y)
            dist_remaining = dist_from_origin - wave.distance_traveled(self.turn_number)
            if dist_remaining < closest_dist:
                closest_dist = dist_remaining
                closest = wave

        return closest

    # ===================================================================
    # Gun — linear predictive targeting
    # ===================================================================

    def _do_gun(self) -> None:
        """Aim with linear prediction and fire when aligned."""
        distance = self.distance_to(self._enemy_x, self._enemy_y)

        # Conservative firepower — survival-oriented bot
        if distance < 150:
            power = 3.0
        elif distance < 400:
            power = 2.0
        else:
            power = 1.5

        # Don't overspend energy
        power = min(power, self.energy - 0.2)
        if power < 0.1:
            power = 0.1

        bullet_speed = 20.0 - 3.0 * power
        travel_time = distance / bullet_speed

        # Linear prediction: enemy continues at current speed and heading
        # Robocode heading: 0 = north (up), clockwise. Convert to trig:
        #   dx = speed * sin(heading_rad)
        #   dy = speed * cos(heading_rad)
        heading_rad = math.radians(self._enemy_direction)
        future_x = self._enemy_x + math.sin(heading_rad) * self._enemy_speed * travel_time
        future_y = self._enemy_y + math.cos(heading_rad) * self._enemy_speed * travel_time

        # Clamp to arena
        margin = 20.0
        future_x = max(margin, min(self.arena_width - margin, future_x))
        future_y = max(margin, min(self.arena_height - margin, future_y))

        gun_bearing = self.gun_bearing_to(future_x, future_y)
        self.set_turn_gun_left(gun_bearing)

        if abs(gun_bearing) < 10 and self.gun_heat == 0:
            self.set_fire(power)

    # ===================================================================
    # Event handlers
    # ===================================================================

    def on_scanned_bot(self, e: ScannedBotEvent) -> None:
        """Update enemy state and detect fire (energy drop → create wave)."""
        # --- Fire detection ---
        energy_drop = self._last_enemy_energy - e.energy
        if 0.1 <= energy_drop <= 3.0:
            # Enemy likely fired — create a bullet wave
            bullet_speed = 20.0 - 3.0 * energy_drop
            abs_bearing = math.degrees(
                math.atan2(self.x - e.x, self.y - e.y)
            )

            # Determine our lateral direction relative to the enemy
            lateral_dir = self._lateral_direction(e.x, e.y)

            self._waves.append(
                Wave(
                    origin_x=float(e.x),
                    origin_y=float(e.y),
                    fire_time=self.turn_number,
                    bullet_speed=bullet_speed,
                    direction_to_target=abs_bearing,
                    lateral_direction=lateral_dir,
                )
            )

        # --- Update enemy state ---
        self._enemy_x = float(e.x)
        self._enemy_y = float(e.y)
        self._enemy_speed = float(e.speed)
        self._enemy_direction = float(e.direction)
        self._enemy_energy = float(e.energy)
        self._enemy_id = e.scanned_bot_id
        self._last_enemy_energy = float(e.energy)
        self._has_target = True
        self._ticks_since_scan = 0

        # Toggle radar sweep direction for tight lock
        self._scan_direction *= -1

    def on_hit_wall(self, e: HitWallEvent) -> None:
        """Bounce off walls — reverse and flip orbit direction."""
        del e
        self.set_back(60)
        self._surf_direction *= -1

    def on_hit_bot(self, e: HitBotEvent) -> None:
        """Point-blank fire when colliding with an enemy."""
        gun_bearing = self.gun_bearing_to(float(e.x), float(e.y))
        self.set_turn_gun_left(gun_bearing)
        if abs(gun_bearing) < 30:
            self.set_fire(3.0)
        self.set_back(50)

    def on_bot_death(self, e: BotDeathEvent) -> None:
        """Clear target if it was destroyed."""
        if e.victim_id == self._enemy_id:
            self._has_target = False
            self._ticks_since_scan = 100

    # ===================================================================
    # Helpers
    # ===================================================================

    def _lateral_direction(self, enemy_x: float, enemy_y: float) -> int:
        """
        Return +1 or -1 indicating our lateral movement direction relative
        to the enemy.  Based on our velocity projected perpendicular to the
        bearing from the enemy to us.
        """
        angle_enemy_to_us = math.atan2(self.x - enemy_x, self.y - enemy_y)
        # Our velocity vector direction (Robocode heading → trig)
        heading_rad = math.radians(self.direction)
        vx = self.speed * math.sin(heading_rad)
        vy = self.speed * math.cos(heading_rad)

        # Lateral component: cross-product sign
        # Perpendicular to (enemy→us): rotate 90° CW
        lateral = vx * math.cos(angle_enemy_to_us) - vy * math.sin(angle_enemy_to_us)
        return 1 if lateral >= 0 else -1

    def _in_safe_zone(self, x: float, y: float) -> bool:
        """True if (x, y) is comfortably inside the arena walls."""
        return (
            WALL_MARGIN < x < self.arena_width - WALL_MARGIN
            and WALL_MARGIN < y < self.arena_height - WALL_MARGIN
        )

    @staticmethod
    def _normalize(angle: float) -> float:
        """Normalize an angle to -180 … +180."""
        while angle > 180:
            angle -= 360
        while angle < -180:
            angle += 360
        return angle


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    bot = WaveSurfer()
    bot.start()


if __name__ == "__main__":
    main()
