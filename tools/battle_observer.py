"""
Battle Observer - Connects to Tank Royale server as a WebSocket observer
and produces detailed battle statistics including accuracy tracking.

Usage:
    python tools/battle_observer.py [--url ws://localhost:7654] [--secret SECRET]

The observer will connect to the server, watch battles, and print a detailed
summary after each battle ends. It tracks statistics that the server doesn't
natively report, like per-bot accuracy (shots fired vs hits).

Press Ctrl+C to disconnect and exit.
"""

import argparse
import asyncio
import json
import signal
import sys
from collections import defaultdict
from dataclasses import dataclass, field

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

    # Accuracy tracking (not available from server results)
    shots_fired: int = 0
    shots_hit: int = 0
    shots_hit_wall: int = 0
    shots_hit_bullet: int = 0

    # Kill tracking
    kills: int = 0
    deaths: int = 0
    ram_kills: int = 0

    # Damage tracking (per-tick granular)
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

    def reset(self) -> None:
        self.bots.clear()
        self.participants.clear()
        self.num_rounds = 0
        self.current_round = 0
        self.current_turn = 0
        self.alive_bots.clear()
        self.active = False

    def get_bot(self, bot_id: int) -> BotStats:
        if bot_id not in self.bots:
            self.bots[bot_id] = BotStats(bot_id=bot_id)
        return self.bots[bot_id]


# ── Statistics Display ──

BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
RESET = "\033[0m"

TROPHY = ">>>"
SKULL = " X "
BULLET = " * "
TARGET = "(+)"
SWORD = "/->"
SHIELD = "[=]"


def print_battle_summary(state: BattleState) -> None:
    """Print a comprehensive battle summary with awards."""
    bots = list(state.bots.values())
    if not bots:
        print("No battle data to display.")
        return

    line = "=" * 80
    thin = "-" * 80

    print(f"\n{BOLD}{CYAN}{line}{RESET}")
    print(f"{BOLD}{CYAN}  BATTLE SUMMARY  ({state.num_rounds} rounds, {state.arena_width}x{state.arena_height} arena){RESET}")
    print(f"{BOLD}{CYAN}{line}{RESET}")

    # ── Final Rankings ──
    ranked = sorted(bots, key=lambda b: b.total_score, reverse=True)
    print(f"\n{BOLD}{WHITE}  FINAL RANKINGS{RESET}")
    print(f"  {thin[:76]}")
    print(f"  {'Rank':<6} {'Bot':<20} {'Score':>10} {'1st':>5} {'2nd':>5} {'3rd':>5} {'Kills':>7} {'Deaths':>7}")
    print(f"  {thin[:76]}")
    for i, bot in enumerate(ranked):
        rank_str = f"#{i + 1}"
        color = [YELLOW, DIM + WHITE, DIM + YELLOW, DIM][min(i, 3)]
        prefix = f"{TROPHY} " if i == 0 else "    "
        print(
            f"  {color}{prefix}{rank_str:<4} {bot.name:<20} {bot.total_score:>10.0f} "
            f"{bot.first_places:>5} {bot.second_places:>5} {bot.third_places:>5} "
            f"{bot.kills:>7} {bot.deaths:>7}{RESET}"
        )

    # ── Awards ──
    print(f"\n{BOLD}{WHITE}  AWARDS{RESET}")
    print(f"  {thin[:76]}")

    # MVP - highest total score
    mvp = max(bots, key=lambda b: b.total_score)
    print(f"  {YELLOW}{TROPHY} MVP (Total Score):{RESET}        {BOLD}{mvp.name}{RESET} ({mvp.total_score:.0f} points)")

    # Most Victories - most first places
    most_wins = max(bots, key=lambda b: b.first_places)
    if most_wins.first_places > 0:
        print(f"  {GREEN}{TROPHY} Most Victories:{RESET}          {BOLD}{most_wins.name}{RESET} ({most_wins.first_places}/{state.num_rounds} rounds won)")

    # Most Kills
    most_kills = max(bots, key=lambda b: b.kills)
    if most_kills.kills > 0:
        print(f"  {RED}{SKULL} Most Kills:{RESET}              {BOLD}{most_kills.name}{RESET} ({most_kills.kills} kills)")

    # Most Damage Dealt
    most_dmg = max(bots, key=lambda b: b.total_damage_dealt)
    if most_dmg.total_damage_dealt > 0:
        print(f"  {RED}{SWORD} Most Damage Dealt:{RESET}       {BOLD}{most_dmg.name}{RESET} ({most_dmg.total_damage_dealt:.1f} total)")

    # Most Accurate
    bots_with_shots = [b for b in bots if b.shots_fired >= 5]
    if bots_with_shots:
        most_accurate = max(bots_with_shots, key=lambda b: b.accuracy)
        print(
            f"  {MAGENTA}{TARGET} Most Accurate:{RESET}           {BOLD}{most_accurate.name}{RESET} "
            f"({most_accurate.accuracy:.1f}% - {most_accurate.shots_hit}/{most_accurate.shots_fired} shots)"
        )

    # Best Damage Ratio
    bots_with_taken = [b for b in bots if b.total_damage_taken > 0]
    if bots_with_taken:
        best_ratio = max(bots_with_taken, key=lambda b: b.damage_ratio)
        if best_ratio.damage_ratio != float("inf"):
            print(
                f"  {BLUE}{SHIELD} Best Damage Ratio:{RESET}       {BOLD}{best_ratio.name}{RESET} "
                f"({best_ratio.damage_ratio:.2f}x - dealt {best_ratio.total_damage_dealt:.0f} / took {best_ratio.total_damage_taken:.0f})"
            )

    # Most Trigger Happy
    most_shots = max(bots, key=lambda b: b.shots_fired)
    if most_shots.shots_fired > 0:
        print(f"  {CYAN}{BULLET} Most Shots Fired:{RESET}        {BOLD}{most_shots.name}{RESET} ({most_shots.shots_fired} bullets)")

    # ── Detailed Stats Table ──
    print(f"\n{BOLD}{WHITE}  DETAILED STATISTICS{RESET}")
    print(f"  {thin[:76]}")

    # Damage breakdown
    print(f"\n  {BOLD}Damage Breakdown:{RESET}")
    header = f"  {'Bot':<20} {'Bullet Dmg':>11} {'Ram Dmg':>9} {'Total Dealt':>12} {'Total Taken':>12} {'Ratio':>7}"
    print(header)
    print(f"  {thin[:76]}")
    for bot in ranked:
        ratio_str = f"{bot.damage_ratio:.2f}x" if bot.damage_ratio != float("inf") else "inf"
        print(
            f"  {bot.name:<20} {bot.bullet_damage_dealt:>11.1f} {bot.ram_damage_dealt:>9.1f} "
            f"{bot.total_damage_dealt:>12.1f} {bot.total_damage_taken:>12.1f} {ratio_str:>7}"
        )

    # Accuracy breakdown
    print(f"\n  {BOLD}Accuracy Breakdown:{RESET}")
    header = f"  {'Bot':<20} {'Fired':>7} {'Hit':>7} {'Hit Wall':>9} {'Hit Bullet':>11} {'Accuracy':>9}"
    print(header)
    print(f"  {thin[:76]}")
    for bot in ranked:
        acc_str = f"{bot.accuracy:.1f}%" if bot.shots_fired > 0 else "N/A"
        print(
            f"  {bot.name:<20} {bot.shots_fired:>7} {bot.shots_hit:>7} "
            f"{bot.shots_hit_wall:>9} {bot.shots_hit_bullet:>11} {acc_str:>9}"
        )

    # Survival breakdown
    print(f"\n  {BOLD}Survival Breakdown:{RESET}")
    header = f"  {'Bot':<20} {'Survived':>9} {'Won':>5} {'Kills':>7} {'Deaths':>7} {'Ram Kills':>10}"
    print(header)
    print(f"  {thin[:76]}")
    for bot in ranked:
        print(
            f"  {bot.name:<20} {bot.rounds_survived:>7}/{state.num_rounds:<1} {bot.rounds_won:>5} "
            f"{bot.kills:>7} {bot.deaths:>7} {bot.ram_kills:>10}"
        )

    # Score breakdown
    print(f"\n  {BOLD}Score Breakdown:{RESET}")
    header = (
        f"  {'Bot':<20} {'Survival':>9} {'Last Surv':>10} {'Bullet':>8} "
        f"{'Kill Bon':>9} {'Ram':>6} {'Ram Bon':>8} {'TOTAL':>8}"
    )
    print(header)
    print(f"  {thin[:76]}")
    for bot in ranked:
        print(
            f"  {bot.name:<20} {bot.survival_score:>9.0f} {bot.last_survivor_bonus:>10.0f} "
            f"{bot.bullet_damage_score:>8.0f} {bot.bullet_kill_bonus:>9.0f} "
            f"{bot.ram_damage_score:>6.0f} {bot.ram_kill_bonus:>8.0f} {bot.total_score:>8.0f}"
        )

    print(f"\n{BOLD}{CYAN}{line}{RESET}\n")


def print_round_summary(state: BattleState, round_num: int) -> None:
    """Print a brief summary after each round."""
    alive = [state.bots[bid].name for bid in state.alive_bots if bid in state.bots]
    dead = [b.name for b in state.bots.values() if b.bot_id not in state.alive_bots]

    winner_name = alive[0] if len(alive) == 1 else "Multiple survived"
    print(
        f"  {DIM}Round {round_num:>2} | "
        f"Winner: {RESET}{BOLD}{winner_name}{RESET} "
        f"{DIM}| Eliminated: {', '.join(dead) if dead else 'None'}{RESET}"
    )


# ── Event Processing ──


def process_tick_events(state: BattleState, events: list[dict]) -> None:
    """Process events from a TickEventForObserver to track granular stats."""
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
            state.alive_bots.discard(victim_id)

            # Credit kills to all surviving bots? No - we track via kill bonuses
            # But we can count kills based on bullet/ram kills from the server results


# ── WebSocket Observer ──


async def observe(url: str, secret: str | None = None) -> None:
    """Connect to Tank Royale server as an observer and track battle stats."""
    state = BattleState()
    battle_count = 0

    print(f"{BOLD}Battle Observer{RESET}")
    print(f"Connecting to {url}...")
    print(f"Press Ctrl+C to exit.\n")

    while True:
        try:
            async with websockets.connect(url) as ws:
                print(f"{GREEN}Connected to server.{RESET} Waiting for battles...\n")

                async for raw_msg in ws:
                    msg = json.loads(raw_msg)
                    msg_type = msg.get("type", "")

                    # ── Handshake ──
                    if msg_type == "ServerHandshake":
                        session_id = msg.get("sessionId", "")
                        handshake = {
                            "type": "ObserverHandshake",
                            "sessionId": session_id,
                            "name": "Battle Observer",
                            "version": "1.0.0",
                        }
                        if secret:
                            handshake["secret"] = secret
                        await ws.send(json.dumps(handshake))
                        server_name = msg.get("name", "Unknown")
                        server_version = msg.get("version", "?")
                        print(f"{DIM}Server: {server_name} v{server_version}{RESET}")

                    # ── Game Started ──
                    elif msg_type == "GameStartedEventForObserver":
                        state.reset()
                        state.active = True
                        battle_count += 1

                        setup = msg.get("gameSetup", {})
                        state.arena_width = setup.get("arenaWidth", 800)
                        state.arena_height = setup.get("arenaHeight", 600)
                        state.num_rounds = setup.get("numberOfRounds", 10)

                        participants = msg.get("participants", [])
                        for p in participants:
                            pid = p.get("id", -1)
                            state.participants[pid] = p
                            bot = state.get_bot(pid)
                            bot.name = p.get("name", f"Bot-{pid}")
                            bot.version = p.get("version", "?")

                        bot_names = [state.bots[pid].name for pid in state.bots]
                        print(f"\n{BOLD}{YELLOW}{'=' * 80}{RESET}")
                        print(f"{BOLD}  BATTLE #{battle_count} STARTED{RESET}")
                        print(f"  {state.num_rounds} rounds | {state.arena_width}x{state.arena_height} arena")
                        print(f"  Combatants: {', '.join(bot_names)}")
                        print(f"{BOLD}{YELLOW}{'=' * 80}{RESET}\n")

                    # ── Round Started ──
                    elif msg_type == "RoundStartedEventForObserver":
                        state.current_round = msg.get("roundNumber", 0)
                        state.alive_bots = set(state.bots.keys())

                    # ── Tick (every turn) ──
                    elif msg_type == "TickEventForObserver":
                        if not state.active:
                            continue
                        state.current_turn = msg.get("turnNumber", 0)
                        events = msg.get("events", [])
                        process_tick_events(state, events)

                    # ── Round Ended ──
                    elif msg_type == "RoundEndedEventForObserver":
                        round_num = msg.get("roundNumber", 0)

                        # Track survival
                        for bot_id in state.alive_bots:
                            if bot_id in state.bots:
                                state.bots[bot_id].rounds_survived += 1

                        # Track round winner (last alive)
                        if len(state.alive_bots) == 1:
                            winner_id = next(iter(state.alive_bots))
                            if winner_id in state.bots:
                                state.bots[winner_id].rounds_won += 1

                        print_round_summary(state, round_num)

                    # ── Game Ended ──
                    elif msg_type == "GameEndedEventForObserver":
                        state.num_rounds = msg.get("numberOfRounds", state.num_rounds)
                        results = msg.get("results", [])

                        for result in results:
                            rid = result.get("id", -1)
                            if rid in state.bots:
                                bot = state.bots[rid]
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

                        # Estimate kills from survival score
                        # Survival = 50 * number of opponents defeated while you're alive
                        # This is imperfect but the best proxy available
                        for bot in state.bots.values():
                            num_opponents = len(state.bots) - 1
                            if num_opponents > 0 and state.num_rounds > 0:
                                # Kill bonus gives 20% of total damage to killed bot
                                # If kill bonus > 0, they got kills
                                if bot.bullet_kill_bonus > 0:
                                    # Rough estimate: each kill gives ~20% of avg damage
                                    avg_damage_per_kill = (bot.bullet_damage_dealt / max(bot.shots_hit, 1)) * 5
                                    if avg_damage_per_kill > 0:
                                        bot.kills = max(bot.kills, round(bot.bullet_kill_bonus / (avg_damage_per_kill * 0.2)))
                                # Count deaths from our tracked data (already counted in tick events)

                        print_battle_summary(state)
                        state.active = False

                    # ── Game Aborted ──
                    elif msg_type == "GameAbortedEvent":
                        print(f"\n{RED}Battle aborted.{RESET}\n")
                        state.active = False

        except websockets.exceptions.ConnectionClosed:
            print(f"\n{YELLOW}Disconnected from server. Reconnecting in 5 seconds...{RESET}")
            await asyncio.sleep(5)
        except ConnectionRefusedError:
            print(f"{RED}Connection refused. Is the server running at {url}?{RESET}")
            print(f"Retrying in 5 seconds...")
            await asyncio.sleep(5)
        except OSError as e:
            print(f"{RED}Connection error: {e}{RESET}")
            print(f"Retrying in 5 seconds...")
            await asyncio.sleep(5)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Battle Observer - Watch Tank Royale battles and get detailed statistics"
    )
    parser.add_argument(
        "--url",
        default="ws://localhost:7654",
        help="WebSocket URL of the Tank Royale server (default: ws://localhost:7654)",
    )
    parser.add_argument(
        "--secret",
        default=None,
        help="Observer secret for server authentication (if required)",
    )
    args = parser.parse_args()

    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print(f"\n{BOLD}Observer stopped.{RESET}")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    asyncio.run(observe(args.url, args.secret))


if __name__ == "__main__":
    main()
