"""
Battle Observer Web UI - Live dashboard for Tank Royale battles.

Connects to Tank Royale as a WebSocket observer, tracks battle statistics,
and serves a live web dashboard at http://localhost:8080.

Usage:
    python tools/battle_observer_ui.py [--url ws://localhost:7654] [--port 8080] [--secret SECRET]

Press Ctrl+C to stop.
"""

import argparse
import asyncio
import json
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

try:
    import aiohttp
    from aiohttp import web
except ImportError:
    print("Error: aiohttp package required. Install with:")
    print("  pip install aiohttp")
    sys.exit(1)

try:
    import websockets
except ImportError:
    print("Error: websockets package required. Install with:")
    print("  pip install websockets")
    sys.exit(1)


# ── Data Classes ──


@dataclass
class BotStats:
    """Per-bot statistics tracked across all rounds in a battle."""

    name: str = ""
    version: str = ""
    bot_id: int = 0

    # Live state (from tick bot states)
    energy: float = 100.0
    alive: bool = True
    x: float = 0.0
    y: float = 0.0
    direction: float = 0.0
    body_color: str = "#888888"

    # Accuracy tracking
    shots_fired: int = 0
    shots_hit: int = 0
    shots_hit_wall: int = 0
    shots_hit_bullet: int = 0

    # Kill tracking
    kills: int = 0
    deaths: int = 0
    ram_kills: int = 0

    # Damage tracking
    bullet_damage_dealt: float = 0.0
    bullet_damage_taken: float = 0.0
    ram_damage_dealt: float = 0.0
    ram_damage_taken: float = 0.0

    # Round tracking
    rounds_survived: int = 0
    rounds_won: int = 0

    # From server results (end of game)
    rank: int = 0
    total_score: float = 0.0
    survival_score: float = 0.0
    last_survivor_bonus: float = 0.0
    bullet_damage_score: float = 0.0
    bullet_kill_bonus: float = 0.0
    ram_damage_score: float = 0.0
    ram_kill_bonus: float = 0.0
    first_places: int = 0
    second_places: int = 0
    third_places: int = 0

    @property
    def accuracy(self) -> float:
        if self.shots_fired == 0:
            return 0.0
        return (self.shots_hit / self.shots_fired) * 100.0

    @property
    def total_damage_dealt(self) -> float:
        return self.bullet_damage_dealt + self.ram_damage_dealt

    @property
    def total_damage_taken(self) -> float:
        return self.bullet_damage_taken + self.ram_damage_taken

    @property
    def damage_ratio(self) -> float:
        if self.total_damage_taken == 0:
            return float("inf") if self.total_damage_dealt > 0 else 0.0
        return self.total_damage_dealt / self.total_damage_taken

    def to_dict(self, *, is_alive: bool | None = None) -> dict:
        alive = is_alive if is_alive is not None else self.alive
        energy = self.energy if alive else 0.0
        return {
            "name": self.name,
            "version": self.version,
            "botId": self.bot_id,
            "energy": energy,
            "alive": alive,
            "x": self.x,
            "y": self.y,
            "direction": self.direction,
            "bodyColor": self.body_color,
            "shotsFired": self.shots_fired,
            "shotsHit": self.shots_hit,
            "shotsHitWall": self.shots_hit_wall,
            "shotsHitBullet": self.shots_hit_bullet,
            "kills": self.kills,
            "deaths": self.deaths,
            "ramKills": self.ram_kills,
            "bulletDamageDealt": round(self.bullet_damage_dealt, 1),
            "bulletDamageTaken": round(self.bullet_damage_taken, 1),
            "ramDamageDealt": round(self.ram_damage_dealt, 1),
            "ramDamageTaken": round(self.ram_damage_taken, 1),
            "totalDamageDealt": round(self.total_damage_dealt, 1),
            "totalDamageTaken": round(self.total_damage_taken, 1),
            "damageRatio": round(self.damage_ratio, 2) if self.damage_ratio != float("inf") else None,
            "accuracy": round(self.accuracy, 1),
            "roundsSurvived": self.rounds_survived,
            "roundsWon": self.rounds_won,
            "rank": self.rank,
            "totalScore": round(self.total_score, 0),
            "survivalScore": round(self.survival_score, 0),
            "lastSurvivorBonus": round(self.last_survivor_bonus, 0),
            "bulletDamageScore": round(self.bullet_damage_score, 0),
            "bulletKillBonus": round(self.bullet_kill_bonus, 0),
            "ramDamageScore": round(self.ram_damage_score, 0),
            "ramKillBonus": round(self.ram_kill_bonus, 0),
            "firstPlaces": self.first_places,
            "secondPlaces": self.second_places,
            "thirdPlaces": self.third_places,
        }


@dataclass
class BattleState:
    """Tracks the state of the current battle."""

    bots: dict[int, BotStats] = field(default_factory=dict)
    participants: dict[int, dict] = field(default_factory=dict)
    num_rounds: int = 0
    current_round: int = 0
    current_turn: int = 0
    arena_width: int = 0
    arena_height: int = 0
    alive_bots: set[int] = field(default_factory=set)
    active: bool = False
    status: str = "waiting"  # waiting, running, complete
    battle_count: int = 0

    def reset(self) -> None:
        self.bots.clear()
        self.participants.clear()
        self.num_rounds = 0
        self.current_round = 0
        self.current_turn = 0
        self.alive_bots.clear()
        self.active = False
        self.status = "waiting"

    def get_bot(self, bot_id: int) -> BotStats:
        if bot_id not in self.bots:
            self.bots[bot_id] = BotStats(bot_id=bot_id)
        return self.bots[bot_id]

    def to_dict(self) -> dict:
        bots_list = sorted(self.bots.values(), key=lambda b: b.total_score, reverse=True)
        return {
            "status": self.status,
            "battleCount": self.battle_count,
            "numRounds": self.num_rounds,
            "currentRound": self.current_round,
            "currentTurn": self.current_turn,
            "arenaWidth": self.arena_width,
            "arenaHeight": self.arena_height,
            "bots": [b.to_dict(is_alive=b.bot_id in self.alive_bots) for b in bots_list],
            "awards": self._compute_awards() if self.status == "complete" else None,
        }

    def _compute_awards(self) -> list[dict]:
        bots = list(self.bots.values())
        if not bots:
            return []

        awards = []

        # MVP
        mvp = max(bots, key=lambda b: b.total_score)
        awards.append({
            "title": "MVP",
            "subtitle": "Total Score",
            "bot": mvp.name,
            "value": f"{mvp.total_score:.0f} points",
            "icon": "trophy",
            "color": "#ffd700",
        })

        # Most Victories
        most_wins = max(bots, key=lambda b: b.first_places)
        if most_wins.first_places > 0:
            awards.append({
                "title": "Most Victories",
                "subtitle": "Rounds Won",
                "bot": most_wins.name,
                "value": f"{most_wins.first_places}/{self.num_rounds} rounds",
                "icon": "crown",
                "color": "#4caf50",
            })

        # Most Kills
        most_kills = max(bots, key=lambda b: b.kills)
        if most_kills.kills > 0:
            awards.append({
                "title": "Most Kills",
                "subtitle": "Eliminations",
                "bot": most_kills.name,
                "value": f"{most_kills.kills} kills",
                "icon": "skull",
                "color": "#f44336",
            })

        # Most Damage
        most_dmg = max(bots, key=lambda b: b.total_damage_dealt)
        if most_dmg.total_damage_dealt > 0:
            awards.append({
                "title": "Most Damage",
                "subtitle": "Total Dealt",
                "bot": most_dmg.name,
                "value": f"{most_dmg.total_damage_dealt:.1f} damage",
                "icon": "sword",
                "color": "#ff5722",
            })

        # Most Accurate
        bots_with_shots = [b for b in bots if b.shots_fired >= 5]
        if bots_with_shots:
            most_acc = max(bots_with_shots, key=lambda b: b.accuracy)
            awards.append({
                "title": "Most Accurate",
                "subtitle": "Hit Rate",
                "bot": most_acc.name,
                "value": f"{most_acc.accuracy:.1f}% ({most_acc.shots_hit}/{most_acc.shots_fired})",
                "icon": "target",
                "color": "#e040fb",
            })

        # Best Damage Ratio
        bots_with_taken = [b for b in bots if b.total_damage_taken > 0 and b.damage_ratio != float("inf")]
        if bots_with_taken:
            best_ratio = max(bots_with_taken, key=lambda b: b.damage_ratio)
            awards.append({
                "title": "Best Ratio",
                "subtitle": "Damage Dealt/Taken",
                "bot": best_ratio.name,
                "value": f"{best_ratio.damage_ratio:.2f}x",
                "icon": "shield",
                "color": "#2196f3",
            })

        return awards


# ── Console Output (matching CLI version) ──

BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RESET = "\033[0m"


def print_round_summary(state: BattleState, round_num: int) -> None:
    alive = [state.bots[bid].name for bid in state.alive_bots if bid in state.bots]
    dead = [b.name for b in state.bots.values() if b.bot_id not in state.alive_bots]
    winner_name = alive[0] if len(alive) == 1 else "Multiple survived"
    print(
        f"  {DIM}Round {round_num:>2} | "
        f"Winner: {RESET}{BOLD}{winner_name}{RESET} "
        f"{DIM}| Eliminated: {', '.join(dead) if dead else 'None'}{RESET}"
    )


def print_battle_summary(state: BattleState) -> None:
    bots = list(state.bots.values())
    if not bots:
        return
    ranked = sorted(bots, key=lambda b: b.total_score, reverse=True)
    line = "=" * 80
    print(f"\n{BOLD}{CYAN}{line}{RESET}")
    print(f"{BOLD}{CYAN}  BATTLE SUMMARY  ({state.num_rounds} rounds, {state.arena_width}x{state.arena_height} arena){RESET}")
    print(f"{BOLD}{CYAN}{line}{RESET}")
    print(f"\n{BOLD}  FINAL RANKINGS{RESET}")
    for i, bot in enumerate(ranked):
        prefix = ">>> " if i == 0 else "    "
        print(f"  {prefix}#{i+1:<4} {bot.name:<20} {bot.total_score:>10.0f} pts")
    print(f"\n{BOLD}{CYAN}{line}{RESET}\n")


# ── Event Processing ──


def process_tick_events(state: BattleState, events: list[dict]) -> bool:
    """Process events from a TickEventForObserver. Returns True if a key event occurred."""
    key_event = False
    for event in events:
        event_type = event.get("type", "")

        if event_type == "BulletFiredEvent":
            owner_id = event.get("bullet", {}).get("ownerId", -1)
            bot = state.get_bot(owner_id)
            bot.shots_fired += 1

        elif event_type == "BulletHitBotEvent":
            bullet = event.get("bullet", {})
            owner_id = bullet.get("ownerId", -1)
            victim_id = event.get("victimId", -1)
            damage = event.get("damage", 0.0)

            shooter = state.get_bot(owner_id)
            shooter.shots_hit += 1
            shooter.bullet_damage_dealt += damage

            victim = state.get_bot(victim_id)
            victim.bullet_damage_taken += damage

        elif event_type == "BulletHitWallEvent":
            bullet = event.get("bullet", {})
            owner_id = bullet.get("ownerId", -1)
            bot = state.get_bot(owner_id)
            bot.shots_hit_wall += 1

        elif event_type == "BulletHitBulletEvent":
            bullet = event.get("bullet", {})
            owner_id = bullet.get("ownerId", -1)
            bot = state.get_bot(owner_id)
            bot.shots_hit_bullet += 1

        elif event_type == "BotHitBotEvent":
            bot_id = event.get("botId", -1)
            victim_id = event.get("victimId", -1)
            damage = event.get("damage", 0.6)
            rammed = event.get("isRammed", False)
            if rammed:
                rammer = state.get_bot(bot_id)
                rammer.ram_damage_dealt += damage
                victim = state.get_bot(victim_id)
                victim.ram_damage_taken += damage

        elif event_type == "BotDeathEvent":
            victim_id = event.get("victimId", -1)
            victim = state.get_bot(victim_id)
            victim.deaths += 1
            victim.alive = False
            victim.energy = 0.0
            state.alive_bots.discard(victim_id)
            key_event = True

    return key_event


def update_bot_states(state: BattleState, bot_states: list[dict]) -> None:
    """Update live bot state (energy, position, color) from tick data."""
    for bs in bot_states:
        bot_id = bs.get("id", -1)
        if bot_id in state.bots:
            bot = state.bots[bot_id]
            energy = bs.get("energy", bot.energy)
            bot.energy = energy
            bot.x = bs.get("x", bot.x)
            bot.y = bs.get("y", bot.y)
            bot.direction = bs.get("direction", bot.direction)
            # Bot appearing in tick data with positive energy is alive
            if energy > 0:
                state.alive_bots.add(bot_id)
            # Colors come as hex strings or objects with a 'value' field
            color = bs.get("bodyColor")
            if isinstance(color, str):
                bot.body_color = color
            elif isinstance(color, dict) and "value" in color:
                bot.body_color = color["value"]


# ── WebSocket Observer + Web Server ──


class BattleObserverUI:
    def __init__(self, server_url: str, port: int, secret: str | None = None):
        self.server_url = server_url
        self.port = port
        self.secret = secret
        self.state = BattleState()
        self.browser_clients: set[web.WebSocketResponse] = set()
        self.last_broadcast_tick = 0
        self.broadcast_interval = 8  # Send every N ticks (~4 updates/sec at 30 TPS)
        self.static_dir = Path(__file__).parent / "static"

    async def broadcast(self, force: bool = False) -> None:
        """Send state to all connected browser clients."""
        if not self.browser_clients:
            return

        # Throttle tick updates unless forced
        if not force and (self.state.current_turn - self.last_broadcast_tick) < self.broadcast_interval:
            return

        self.last_broadcast_tick = self.state.current_turn
        data = json.dumps(self.state.to_dict())
        dead_clients = set()

        for ws in self.browser_clients:
            try:
                await ws.send_str(data)
            except (ConnectionResetError, ConnectionError):
                dead_clients.add(ws)

        self.browser_clients -= dead_clients

    # ── Tank Royale Observer Task ──

    async def observe_tank_royale(self) -> None:
        """Connect to Tank Royale server as observer and track battle stats."""
        print(f"{BOLD}Battle Observer UI{RESET}")
        print(f"Connecting to {self.server_url}...")

        while True:
            try:
                async with websockets.connect(self.server_url) as ws:
                    print(f"{GREEN}Connected to Tank Royale server.{RESET}")

                    async for raw_msg in ws:
                        msg = json.loads(raw_msg)
                        msg_type = msg.get("type", "")

                        if msg_type == "ServerHandshake":
                            session_id = msg.get("sessionId", "")
                            handshake = {
                                "type": "ObserverHandshake",
                                "sessionId": session_id,
                                "name": "Battle Observer UI",
                                "version": "1.0.0",
                            }
                            if self.secret:
                                handshake["secret"] = self.secret
                            await ws.send(json.dumps(handshake))
                            server_name = msg.get("name", "Unknown")
                            server_version = msg.get("version", "?")
                            print(f"{DIM}Server: {server_name} v{server_version}{RESET}")

                        elif msg_type == "GameStartedEventForObserver":
                            self.state.reset()
                            self.state.active = True
                            self.state.battle_count += 1
                            self.state.status = "running"

                            setup = msg.get("gameSetup", {})
                            self.state.arena_width = setup.get("arenaWidth", 800)
                            self.state.arena_height = setup.get("arenaHeight", 600)
                            self.state.num_rounds = setup.get("numberOfRounds", 10)

                            participants = msg.get("participants", [])
                            for p in participants:
                                pid = p.get("id", -1)
                                self.state.participants[pid] = p
                                bot = self.state.get_bot(pid)
                                bot.name = p.get("name", f"Bot-{pid}")
                                bot.version = p.get("version", "?")

                            bot_names = [self.state.bots[pid].name for pid in self.state.bots]
                            print(f"\n{BOLD}{YELLOW}{'=' * 80}{RESET}")
                            print(f"{BOLD}  BATTLE #{self.state.battle_count} STARTED{RESET}")
                            print(f"  {self.state.num_rounds} rounds | {self.state.arena_width}x{self.state.arena_height} arena")
                            print(f"  Combatants: {', '.join(bot_names)}")
                            print(f"{BOLD}{YELLOW}{'=' * 80}{RESET}\n")

                            await self.broadcast(force=True)

                        elif msg_type == "RoundStartedEventForObserver":
                            self.state.current_round = msg.get("roundNumber", 0)
                            self.state.current_turn = 0
                            self.state.alive_bots = set(self.state.bots.keys())
                            for bot in self.state.bots.values():
                                bot.alive = True
                                bot.energy = 100.0
                            await self.broadcast(force=True)

                        elif msg_type == "TickEventForObserver":
                            if not self.state.active:
                                continue
                            self.state.current_turn = msg.get("turnNumber", 0)

                            # Update bot live states
                            bot_states = msg.get("botStates", [])
                            update_bot_states(self.state, bot_states)

                            events = msg.get("events", [])
                            key_event = process_tick_events(self.state, events)

                            await self.broadcast(force=key_event)

                        elif msg_type == "RoundEndedEventForObserver":
                            round_num = msg.get("roundNumber", 0)

                            for bot_id in self.state.alive_bots:
                                if bot_id in self.state.bots:
                                    self.state.bots[bot_id].rounds_survived += 1

                            if len(self.state.alive_bots) == 1:
                                winner_id = next(iter(self.state.alive_bots))
                                if winner_id in self.state.bots:
                                    self.state.bots[winner_id].rounds_won += 1

                            print_round_summary(self.state, round_num)
                            await self.broadcast(force=True)

                        elif msg_type == "GameEndedEventForObserver":
                            self.state.num_rounds = msg.get("numberOfRounds", self.state.num_rounds)
                            results = msg.get("results", [])

                            for result in results:
                                rid = result.get("id", -1)
                                if rid in self.state.bots:
                                    bot = self.state.bots[rid]
                                    bot.rank = result.get("rank", 0)
                                    bot.total_score = result.get("totalScore", 0)
                                    bot.survival_score = result.get("survival", 0)
                                    bot.last_survivor_bonus = result.get("lastSurvivorBonus", 0)
                                    bot.bullet_damage_score = result.get("bulletDamage", 0)
                                    bot.bullet_kill_bonus = result.get("bulletKillBonus", 0)
                                    bot.ram_damage_score = result.get("ramDamage", 0)
                                    bot.ram_kill_bonus = result.get("ramKillBonus", 0)
                                    bot.first_places = result.get("firstPlaces", 0)
                                    bot.second_places = result.get("secondPlaces", 0)
                                    bot.third_places = result.get("thirdPlaces", 0)
                                    bot.name = result.get("name", bot.name)

                            # Estimate kills from kill bonus
                            for bot in self.state.bots.values():
                                if bot.bullet_kill_bonus > 0 and bot.shots_hit > 0:
                                    avg_dmg = bot.bullet_damage_dealt / bot.shots_hit * 5
                                    if avg_dmg > 0:
                                        bot.kills = max(bot.kills, round(bot.bullet_kill_bonus / (avg_dmg * 0.2)))

                            self.state.status = "complete"
                            self.state.active = False
                            print_battle_summary(self.state)
                            await self.broadcast(force=True)

                        elif msg_type == "GameAbortedEvent":
                            print(f"\n{RED}Battle aborted.{RESET}\n")
                            self.state.status = "waiting"
                            self.state.active = False
                            await self.broadcast(force=True)

            except websockets.exceptions.ConnectionClosed:
                print(f"\n{YELLOW}Disconnected. Reconnecting in 5s...{RESET}")
                await asyncio.sleep(5)
            except ConnectionRefusedError:
                print(f"{RED}Connection refused. Is Tank Royale running at {self.server_url}?{RESET}")
                await asyncio.sleep(5)
            except OSError as e:
                print(f"{RED}Connection error: {e}{RESET}")
                await asyncio.sleep(5)

    # ── HTTP/WebSocket Server ──

    async def handle_index(self, request: web.Request) -> web.FileResponse:
        return web.FileResponse(self.static_dir / "dashboard.html")

    async def handle_ws(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.browser_clients.add(ws)
        print(f"{DIM}Browser connected ({len(self.browser_clients)} clients){RESET}")

        # Send current state immediately
        try:
            await ws.send_str(json.dumps(self.state.to_dict()))
        except (ConnectionResetError, ConnectionError):
            pass

        try:
            async for msg in ws:
                pass  # We don't expect messages from browser
        finally:
            self.browser_clients.discard(ws)
            print(f"{DIM}Browser disconnected ({len(self.browser_clients)} clients){RESET}")

        return ws

    async def start_web_server(self) -> None:
        app = web.Application()
        app.router.add_get("/", self.handle_index)
        app.router.add_get("/ws", self.handle_ws)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self.port)
        await site.start()
        print(f"{GREEN}Dashboard running at http://localhost:{self.port}{RESET}")

    async def run(self) -> None:
        await self.start_web_server()
        await self.observe_tank_royale()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Battle Observer Web UI - Live dashboard for Tank Royale battles"
    )
    parser.add_argument(
        "--url",
        default="ws://localhost:7654",
        help="WebSocket URL of the Tank Royale server (default: ws://localhost:7654)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="HTTP port for the web dashboard (default: 8080)",
    )
    parser.add_argument(
        "--secret",
        default=None,
        help="Observer secret for server authentication (if required)",
    )
    args = parser.parse_args()

    def signal_handler(sig, frame):
        print(f"\n{BOLD}Observer UI stopped.{RESET}")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    observer = BattleObserverUI(args.url, args.port, args.secret)
    asyncio.run(observer.run())


if __name__ == "__main__":
    main()
