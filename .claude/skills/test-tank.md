# Skill: test-tank

Review and evaluate a Robocode Tank Royale bot.

## Trigger
User says "test tank", "review bot", "evaluate bot", "check my bot", or similar.

## Workflow

1. **Identify the bot** - Ask which bot to test, or find bots in `C:\repos\bots\bots\`

2. **Read the bot's source code** and all its files

3. **Static analysis** - Check for:
   - All 4 required files present (`.py`, `.json`, `.cmd`, `.sh`)
   - Correct class structure (extends Bot, has run(), has main())
   - `while self.running:` loop in run()
   - No blocking operations in event handlers
   - Proper firepower ranges (0.1-3.0)
   - Gun heat awareness (checking gun_heat before firing)
   - No division by zero in distance calculations
   - Wall boundary awareness
   - Proper use of blocking vs non-blocking methods

4. **Strategy evaluation** - Analyze:
   - Movement: How predictable? Wall-aware? Evasive?
   - Gun: Aiming method? Firepower management? Lead targeting?
   - Scanning: Coverage? Lock-on? Efficiency?
   - Energy management: Conservative or aggressive?
   - Weaknesses: What strategies would beat this bot?

5. **Rate the bot** (1-10) on:
   - Survivability
   - Damage output
   - Accuracy
   - Energy efficiency
   - Adaptability

6. **Suggest improvements** with specific code examples

7. **Recommend test opponents** from sample bots:
   - Target (stationary) - baseline aiming test
   - SpinBot (circular) - tracking test
   - Walls (wall-following) - predictable target test
   - Crazy (erratic) - handling unpredictable targets
   - RamFire (aggressive) - close combat test
   - Corners (camping) - patience/approach test

## Running a Battle

To test a bot in an actual battle:

1. Ensure Tank Royale GUI is running (or start it):
   ```
   java -jar robocode-tank-royale-gui-0.36.1.jar
   ```

2. Add bot directories to Config > Bot Root Directories:
   - Add `C:\repos\bots\bots` (your bots)
   - Add `C:\repos\tank-royale\sample-bots\python` (sample opponents)

3. Select bots and start the battle

4. Use the Tank Royale Viewer (`C:\repos\tank-royale-viewer`) for broadcast-quality viewing:
   ```
   cd C:\repos\tank-royale-viewer && npm run dev
   ```
