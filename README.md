# ♔ ChessMate Alarm

**A Kivy alarm app that won't let you sleep in — solve real chess puzzles to dismiss the alarm.**

---

## Features

- Set multiple alarms with repeat days (weekdays, weekends, custom)
- Puzzles sourced live from **Lichess** (4M+ puzzle database, CC0 licensed)
- Intelligent offline fallback — bundled puzzles ensure the alarm always works
- Choose **how many puzzles** to solve (1–10) — make mornings harder if you dare
- Three difficulty levels: **Easy** (≤1400), **Medium** (1400–1800), **Hard** (1800+)
- Hint button highlights the correct piece and destination
- Snooze mode (optional)
- Dark "chess clock at midnight" theme

---

## Puzzle Sources

### 1. Lichess Live API (when online)
```
GET https://lichess.org/api/puzzle/next
GET https://lichess.org/api/puzzle/daily
```
- **No API key required** — completely free and open
- Returns puzzles with FEN, UCI solution moves, rating, and themes
- Rate-limit friendly: fetches 1 puzzle at a time, pre-caches on app start

### 2. Offline Cache
Puzzles fetched while online are saved to `user_data/puzzle_cache.json`.
Up to **200 puzzles** are cached locally — so even a week without internet
won't exhaust your puzzle supply.

### 3. Bundled Fallback
~20 hand-picked puzzles baked into `data/lichess_puzzles.py` (easy/medium/hard).
These are taken from the Lichess puzzle database (CC0) and ensure the alarm
works correctly on first install with zero network access.

---

## Lichess Puzzle Database (Optional Offline Bulk Download)

For full offline use, you can download the entire Lichess puzzle CSV:

```bash
# ~300 MB compressed, ~1 GB uncompressed
curl -O https://database.lichess.org/lichess_db_puzzle.csv.zst
unzstd lichess_db_puzzle.csv.zst

# Then import into the app cache:
python tools/import_csv.py lichess_db_puzzle.csv --count 500 --difficulty medium
```

CSV format:
```
PuzzleId,FEN,Moves,Rating,RatingDeviation,Popularity,NbPlays,Themes,GameUrl,OpeningTags
00sOo,r3r1k1/...,e4f6 g7f6 ...,1234,75,85,1000,fork mateIn2,...
```

---

## Installation

### Desktop (for testing)
```bash
pip install kivy chess
python main.py
```

### Android (APK)
```bash
pip install buildozer cython
buildozer android debug deploy run
```

Requires: Android Studio, Java 17, NDK r25c.

---

## Project Structure

```
chess_alarm/
├── main.py                     # App entry point
├── requirements.txt
├── buildozer.spec              # Android packaging config
│
├── data/
│   ├── lichess_puzzles.py      # Lichess API + cache + bundled puzzles
│   ├── store.py                # Alarm + settings persistence (JSON)
│   └── puzzles.py              # (legacy, superseded by lichess_puzzles.py)
│
├── screens/
│   ├── home.py                 # Alarm list
│   ├── add_alarm.py            # Create / edit alarm
│   ├── settings.py             # Puzzle count, difficulty, volume
│   ├── ringing.py              # Fullscreen alarm alert
│   └── puzzle.py               # Interactive chess board + game logic
│
├── utils/
│   ├── chess_engine.py         # FEN parser, board state, move validation
│   └── scheduler.py            # Background alarm time-check thread
│
└── user_data/                  # Created at runtime (gitignored)
    ├── alarms.json
    ├── settings.json
    └── puzzle_cache.json       # Cached Lichess puzzles
```

---

## How Puzzle Solving Works

Each puzzle comes with a list of **UCI moves** (e.g. `["e4f6", "g8f6", "d1h5"]`).

- **Even-indexed moves** (0, 2, 4, …) are **your moves**
- **Odd-indexed moves** (1, 3, 5, …) are the **engine's reply** (auto-played)

You tap a piece, then tap the destination square. The app checks if your move
matches the expected solution move. Wrong moves flash red; correct moves trigger
the engine reply and advance the sequence.

---

## Lichess Attribution

Puzzles are sourced from [lichess.org](https://lichess.org) and the
[Lichess Puzzle Database](https://database.lichess.org/#puzzles).
Licensed under **CC0 (Public Domain)**. ♞