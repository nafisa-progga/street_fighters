# Brawler

A fun and exciting 2D fighting game built using Python and the Pygame library!

## 🚀 About the Project
This is a 2-player local fighting game project where **P1-Warrior** and **P2-Wizard** face off across rounds with sprite animations, health bars, sound effects, a main menu, and a post-match victory screen with rematch and main menu options.

## 🛠️ Built With
- Python
- Pygame

## 🙏 Acknowledgments & Credits
- Tutorial Series: Built by following the amazing tutorial playlist by Coding With Russ. You can check out the playlist here: Coding With Russ Playlist.
- Creator: Coding With Russ on YouTube.

## 🎮 Game Rules, Instructions & How to Play
### Match Rules
- Each match consists of up to **3 rounds**.
- Each fighter starts every round with **100 health** (`10` damage per successful attack).
- Winning a round awards a point to the surviving fighter (`Rounds won`).
- Whoever wins the most rounds across the 3 rounds wins the match.
- At the end of the match, the victory screen displays the **VICTORY** banner, plays the victory sound, announces the winner, resets both fighters to their idle first frame, scales the winner up, and downsizes the loser.
- Once a match ends, use **REMATCH** to play another match or **MAIN MENU** to return to the start screen.

### Controls
**Player 1 — Warrior:**
- Move Left / Right: `A` / `D`
- Jump: `W`
- Attack 1 / Attack 2: `E` / `Q`

**Player 2 — Wizard:**
- Move Left / Right: `Left Arrow` / `Right Arrow`
- Jump: `Up Arrow`
- Attack 1 / Attack 2: `Down Arrow` / `Right Ctrl`

## 📦 Things to Install (For Running From Source)
- **Python 3.x** (tested with Python 3.12)
- **Pygame**

## ⚙️ How to Play & Run

### Option 1: Play via `.exe` (No Python Installation Required)
1. Download or locate `dist/Brawler.exe` from this repository.
2. Double-click `Brawler.exe` to launch the game and click **START** on the main menu (or **EXIT** to quit).

### Option 2: Run From Source
1. Make sure you have Python and Pygame installed on your system:
   ```bash
   pip install pygame