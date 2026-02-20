# Initial Prompt

Before the below prompt, I cloned the robocode and tank-royale repos locally and added the to the VS Code workspace

This empty repo will be the place that I build bot tanks for a robocode tank battle.  As a first step I want you to learn about robocode, the other two folders in this workspace have code related to robocode, and should have readmes. Also, this URL:     
   https://robocode.dev/tutorial/getting-started.html, this URL : https://robocode.dev/tutorial/my-first-bot.html, and this URL:  https://robocode.dev/tutorial/beyond-the-basics.html have additional information.  Setup the bots repo with skills            
  related to tank building, create an agent for building a new tank, an agent for testing a finished tank (perhaps with knowledge of how to run a battle to evaluate a new tank?), and summary documents of how robocode works which would be useful for        
  claude to use going forward.  Finally, I want to write my bot in python, so look at this documenation for how to build a bot: https://robocode.dev/api/python/    

## Key output
● Everything is set up. Here's a summary of what was created:
                                                                                                                                                                                                                                                                  Repo Structure                                                                                                                                                                                                                                                  
  C:\repos\bots\                                                                                                                                                                                                                                                
  ├── CLAUDE.md                          # Project instructions for Claude
  ├── .gitignore                         # Python/IDE/OS ignores
  ├── requirements.txt                   # robocode-tank-royale dependency
  ├── bots.code-workspace                # VS Code workspace (pre-existing)
  ├── bots/                              # Where your bots live (empty, ready)
  ├── docs/
  │   └── robocode-reference.md          # Comprehensive game & API reference
  ├── scripts/
  │   └── new-bot.sh                     # Scaffolding script for new bots
  └── .claude/
      ├── agents/
      │   ├── tank-builder.md            # Agent for building new bots
      │   └── tank-tester.md             # Agent for testing/evaluating bots
      └── skills/
          ├── new-tank.md                # Skill for creating a new bot
          └── test-tank.md               # Skill for testing/reviewing a bot

  What's Included

  Reference Documentation (docs/robocode-reference.md):
  - Complete game mechanics (energy, physics, bullets, scanning, collisions)
  - Full Python API reference (all methods, properties, events, constants)
  - Event system with priorities and best practices
  - Bot architecture recommendations (three-strategy pattern)
  - All 9 sample bot strategies explained

  Tank Builder Agent (.claude/agents/tank-builder.md):
  - Complete API quick reference embedded for context
  - Bot file structure template with all 4 required files
  - Design guidelines and strategy templates (aggressive, defensive, evasive, balanced, wall rider)
  - Knows to use non-blocking setters + go() for advanced bots

  Tank Tester Agent (.claude/agents/tank-tester.md):
  - Static code review checklist (13 items)
  - Strategy analysis framework
  - Performance metrics to evaluate
  - Improvement suggestions for movement, gun, and scanning
  - Comparative testing matrix against sample bots
  - Instructions for running battles via the GUI and viewer

  Skills:
  - new-tank - Guided workflow for creating a bot (gathers requirements, creates all files)
  - test-tank - Guided workflow for reviewing and evaluating a bot

  Scaffolding Script (scripts/new-bot.sh):
  - Creates all 4 bot files from a single command: ./scripts/new-bot.sh BotName "Description" "Author"

  You're all set to start building tanks! Just say something like "build me a new bot" or describe the strategy you want and we'll create it.

  # Tank prompt
   I want to create a highly aggressive tank which does not care for it's own safety.  It's goal is simply to deal as much damage as possible.  The rate of fire should be as rapid as possible, and it needs to be aggressive in finding another target to      
  shoot at.     

  ## Key output
  Berserker is ready. Here's the strategy breakdown: 
                                                                                                                                                                                                                                                                  Movement                                                                                                                                                                                                                                                        
  - Charges directly at enemies at full speed - no evasion, no retreat                                                                                                                                                                                          
  - Turns toward target and rams through them  
  - Bounces off walls without hesitation and keeps hunting

  Gun (Maximum DPS)

  - Fires at power 3.0 up close (16 damage per shot) - the mathematically optimal damage-per-turn ratio
  - Scales to 2.5 at mid-range, 2.0 at long range (faster bullets for distant targets)
  - Leads targets - predicts future position based on enemy speed and direction
  - Fires as soon as the gun is roughly aimed (15-degree tolerance) - doesn't waste turns waiting for perfect alignment
  - Point-blank 3.0 shots on ram contact

  Radar

  - Tight radar lock when tracking a target (narrow sweep to maintain scan arc)
  - Full-speed radar spin (45 deg/turn) when hunting for a new victim
  - Immediately switches to hunt mode when current target dies

  Strengths

  - Massive damage output, especially up close
  - Relentless pursuit - enemies can't escape
  - Fast target acquisition with aggressive radar sweep
  - Ram bonus points on collision

  Weaknesses (by design)

  - No bullet dodging - will take heavy damage
  - No wall avoidance strategy
  - Predictable linear movement toward target
  - Energy can drain fast from constant max-power fire

  To test it, add C:\repos\bots\bots as a bot root directory in Tank Royale GUI and pit it against the sample bots. It should dominate stationary/slow targets and trade blows aggressively with everything else.