# Skill: new-tank

Create a new Robocode Tank Royale bot in Python.

## Trigger
User says "new tank", "create bot", "build a bot", "new bot", or similar.

## Workflow

1. **Gather requirements** - Ask the user:
   - Bot name (PascalCase, e.g., "DodgeBot")
   - Strategy type (aggressive, defensive, evasive, balanced, custom)
   - Special behaviors (wall-following, corner camping, ramming, tracking, etc.)

2. **Read reference docs** for context:
   - `C:\repos\bots\CLAUDE.md`
   - `C:\repos\bots\docs\robocode-reference.md`

3. **Create the bot directory and all 4 files** under `C:\repos\bots\bots\BotName\`:

   ### BotName.py
   - Class extends `Bot` from `robocode_tank_royale.bot_api`
   - Implement `run()` with `while self.running:` loop
   - Use the three-strategy pattern (movement, gun, scanning)
   - Prefer non-blocking setters + `go()` for advanced bots
   - Implement relevant event handlers
   - Include type hints and comments explaining the strategy
   - Entry point: `def main(): BotName().start()` with `if __name__ == "__main__": main()`

   ### BotName.json
   ```json
   {
     "name": "Bot Name",
     "version": "1.0",
     "authors": ["Author"],
     "description": "Strategy description",
     "homepage": "",
     "countryCodes": ["us"],
     "platform": "Python",
     "programmingLang": "Python 3"
   }
   ```

   ### BotName.cmd
   ```batch
   @echo off
   python BotName.py %*
   ```

   ### BotName.sh
   ```sh
   #!/usr/bin/env sh
   python3 "$(dirname "$0")/BotName.py" "$@"
   ```

4. **Explain the strategy** to the user:
   - Movement pattern and why
   - Aiming approach and expected accuracy
   - Scanning coverage
   - Strengths and weaknesses
   - Suggested opponents for testing

## Strategy Templates

### Aggressive
- Close range, high firepower
- Ram enemies for bonus points
- Track and chase targets

### Defensive
- Maintain distance
- Conservative firing (low power, fast bullets)
- Strong evasion pattern

### Evasive
- Wave surfing or random oscillation
- Fire only when confident
- Survive to win

### Balanced
- Moderate distance
- Adaptive firepower based on distance
- Mix of evasion and pursuit

### Wall Rider
- Follow walls for predictable positioning
- Gun pointed inward
- Good for melee battles
