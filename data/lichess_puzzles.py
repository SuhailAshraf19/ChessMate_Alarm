"""
data/lichess_puzzles.py — Lichess fetch and local cache helpers.
"""

import json
import os
import ssl
import time
import threading
from collections import deque
import urllib.request
from urllib.error import HTTPError
from typing import Optional

import chess
from kivy.app import App
from kivy.logger import Logger
from kivy.utils import platform

_BASE_DIR   = os.path.join(os.path.dirname(__file__), "..", "user_data")
_CACHE_FILE = os.path.join(_BASE_DIR, "puzzle_cache.json")

_LICHESS_DAILY = "https://lichess.org/api/puzzle/daily"
_LICHESS_NEXT  = "https://lichess.org/api/puzzle/next"
_HEADERS = {
    "Accept":     "application/json",
    "User-Agent": "ChessMateAlarm/1.0 (open-source alarm app)",
}

_TARGET_WINDOW = 300
_BUNDLED_CACHE_VERSION = 9
_BANK_TARGET_READY = 20
_READY_POOL_MIN = 5
_CACHE_FLOOR = 50
_POOL_LOCK = threading.Lock()
_FETCH_LOCK = threading.Lock()
_FETCH_QUEUE_LOCK = threading.Lock()
_READY_PUZZLES = []
_FETCH_IN_FLIGHT = False
_LAST_PUZZLE = None
_REPEAT_COUNTER = 0
_SOLVED_IDS = set()
_RATE_LIMIT_UNTIL = 0.0
_BUNDLED_QUEUE_USED = False
_CACHE_META_FILE = os.path.join(_BASE_DIR, "puzzle_cache_seed.json")
_SEEN_IDS_FILE = os.path.join(_BASE_DIR, "puzzle_seen_ids.json")
_CACHE_TARGET = _CACHE_FLOOR
_FETCH_REQUESTS = deque()
_FETCH_WORKER_RUNNING = False
_CACHE_MONITOR_STARTED = False
_SEEN_IDS = set()
_SEEN_IDS_LOADED = False

_BUNDLED_STARTER_PUZZLES = [
    {"id": "bundled_01", "fen": "r6k/pp2r2p/4Rp1Q/3p4/8/1N1P2R1/PqP2bPP/7K b - - 0 24", "solution": ["f2g3", "e6e7", "b2b1", "b3c1", "b1c1", "h6c1"], "rating": 1935, "themes": ["crushing", "hangingPiece", "long", "middlegame"], "source": "bundled"},
    {"id": "bundled_02", "fen": "5rk1/1p3ppp/pq3b2/8/8/1P1Q1N2/P4PPP/3R2K1 w - - 2 27", "solution": ["d3d6", "f8d8", "d6d8", "f6d8"], "rating": 1414, "themes": ["advantage", "endgame", "short"], "source": "bundled"},
    {"id": "bundled_03", "fen": "8/4R3/1p2P3/p4r2/P6p/1P3Pk1/4K3/8 w - - 1 64", "solution": ["e7f7", "f5e5", "e2f1", "e5e6"], "rating": 1385, "themes": ["advantage", "endgame", "rookEndgame", "short"], "source": "bundled"},
    {"id": "bundled_04", "fen": "r2qr1k1/b1p2ppp/pp4n1/P1P1p3/4P1n1/B2P2Pb/3NBP1P/RN1QR1K1 b - - 1 16", "solution": ["b6c5", "e2g4", "h3g4", "d1g4"], "rating": 1084, "themes": ["advantage", "middlegame", "short"], "source": "bundled"},
    {"id": "bundled_05", "fen": "6k1/5p1p/4p3/4q3/3nN3/2Q3P1/PP3P1P/6K1 w - - 2 37", "solution": ["e4d2", "d4e2", "g1f1", "e2c3"], "rating": 1550, "themes": ["crushing", "endgame", "fork", "short"], "source": "bundled"},
    {"id": "bundled_06", "fen": "2Q2bk1/5p1p/p5p1/2p3P1/2r1B3/7P/qPQ2P2/2K4R b - - 0 32", "solution": ["c4c2", "e4c2", "a2a1", "c2b1"], "rating": 1582, "themes": ["advantage", "endgame", "short"], "source": "bundled"},
    {"id": "bundled_07", "fen": "8/8/4k1p1/2KpP2p/5PP1/8/8/8 w - - 0 53", "solution": ["g4h5", "g6h5", "f4f5", "e6e5", "f5f6", "e5f6"], "rating": 1574, "themes": ["crushing", "endgame", "long", "pawnEndgame"], "source": "bundled"},
    {"id": "bundled_08", "fen": "4r3/1k6/pp3r2/1b2P2p/3R1p2/P1R2P2/1P4PP/6K1 w - - 0 35", "solution": ["e5f6", "e8e1", "g1f2", "e1f1"], "rating": 1376, "themes": ["endgame", "mate", "mateIn2", "operaMate", "short"], "source": "bundled"},
    {"id": "bundled_09", "fen": "r4rk1/pp3ppp/2n1b3/q1pp2B1/8/P1Q2NP1/1PP1PP1P/2KR3R w - - 0 15", "solution": ["g5e7", "a5c3", "b2c3", "c6e7"], "rating": 1414, "themes": ["advantage", "master", "middlegame", "short"], "source": "bundled"},
    {"id": "bundled_10", "fen": "5rk1/p5p1/3bpr1p/1Pp4q/3pR3/1P1Q1N2/P4PPP/4R1K1 w - - 4 22", "solution": ["e4e6", "f6f3", "g2f3", "h5h2", "g1f1", "h2h3", "f1e2", "h3e6"], "rating": 2071, "themes": ["advantage", "interference", "kingsideAttack", "middlegame", "veryLong"], "source": "bundled"},
    {"id": "bundled_11", "fen": "r1bqk2r/pp1nbNp1/2p1p2p/8/2BP4/1PN3P1/P3QP1P/3R1RK1 b kq - 0 19", "solution": ["e8f7", "e2e6", "f7f8", "e6f7"], "rating": 1575, "themes": ["mate", "mateIn2", "middlegame", "short"], "source": "bundled"},
    {"id": "bundled_12", "fen": "5k2/1p4pp/p5n1/5Q2/3BpP2/1P2PP1K/P1q4P/7r b - - 1 33", "solution": ["f8g8", "f5d5", "g8f8", "d4c5", "c2c5", "d5c5"], "rating": 2152, "themes": ["crushing", "endgame", "long"], "source": "bundled"},
    {"id": "bundled_13", "fen": "3r3r/pQNk1ppp/1qnb1n2/1B6/8/8/PPP3PP/3R1R1K w - - 5 19", "solution": ["d1d6", "d7d6", "b7b6", "a7b6"], "rating": 1437, "themes": ["advantage", "hangingPiece", "middlegame", "short"], "source": "bundled"},
    {"id": "bundled_14", "fen": "5r1k/5rp1/p7/1b2B2p/1P1P1Pq1/2R1Q3/P3p1P1/2R3K1 w - - 0 41", "solution": ["e3g3", "f7f4", "e5f4", "f8f4"], "rating": 1957, "themes": ["crushing", "middlegame", "short"], "source": "bundled"},
    {"id": "bundled_15", "fen": "3R4/8/K7/pB2b3/1p6/1P2k3/3p4/8 w - - 4 58", "solution": ["a6a5", "e5c7", "a5b4", "c7d8"], "rating": 1110, "themes": ["crushing", "endgame", "fork", "master", "short"], "source": "bundled"},
    {"id": "bundled_16", "fen": "8/7R/8/5p2/4bk1P/8/2r2K2/6R1 w - - 7 51", "solution": ["f2f1", "f4f3", "f1e1", "c2c1", "e1d2", "c1g1"], "rating": 2054, "themes": ["crushing", "endgame", "exposedKing", "long", "skewer"], "source": "bundled"},
    {"id": "bundled_17", "fen": "2R2r1k/pQ4pp/5rp1/3B4/q2n4/7P/P4PP1/5RK1 w - - 3 30", "solution": ["c8c7", "d4e2", "g1h2", "a4f4", "h2h1", "e2g3", "f2g3", "f4f1"], "rating": 1562, "themes": ["advantage", "middlegame", "veryLong"], "source": "bundled"},
    {"id": "bundled_18", "fen": "r2qr1k1/b1p2ppp/pp4n1/P1P1p3/4P1n1/B2P2Pb/3NBP1P/RN1QR1K1 b - - 1 16", "solution": ["b6c5", "e2g4", "h3g4", "d1g4"], "rating": 1084, "themes": ["advantage", "middlegame", "short"], "source": "bundled"},
    {"id": "bundled_19", "fen": "8/2p1k3/6p1/1p1P1p2/1P3P2/3K2Pp/7P/8 b - - 1 43", "solution": ["e7d6", "d3d4", "g6g5", "f4g5"], "rating": 944, "themes": ["crushing", "endgame", "pawnEndgame", "short", "zugzwang"], "source": "bundled"},
    {"id": "bundled_20", "fen": "3R4/8/K7/pB2b3/1p6/1P2k3/3p4/8 w - - 4 58", "solution": ["a6a5", "e5c7", "a5b4", "c7d8"], "rating": 1110, "themes": ["crushing", "endgame", "fork", "master", "short"], "source": "bundled"},
]
def _parse_lichess_response(data: dict, source: str = "lichess") -> Optional[dict]:
    """
    Parse Lichess API puzzle response.

    Lichess /api/puzzle/next  and  /api/puzzle/daily  both return:
    {
      "puzzle": {
        "id": "...",
        "rating": 1500,
        "themes": [...],
        "solution": ["e2e4", "d7d5", ...],   ← player moves + engine replies
        "initialPly": 12
      },
      "game": { "pgn": "..." }
    }

    The FEN is derived by replaying the PGN to initialPly using python-chess.
    The turn in that FEN tells us who the solver is.
    """
    try:
        p         = data.get("puzzle") or data
        puzzle_id = p.get("id", "unknown")
        rating    = int(p.get("rating", 1500))
        solution  = list(p.get("solution", []))
        themes    = p.get("themes", [])

        fen = p.get("fen") or p.get("initialFen") or ""
        if not fen:
            game = data.get("game") or {}
            pgn = game.get("pgn") or ""
            initial_ply = int(p.get("initialPly", 0) or 0)
            if pgn and initial_ply >= 0:
                fen = _fen_from_lichess_game(pgn, p.get("initialFen"), initial_ply)

        if not fen or not solution:
            Logger.warning(
                f"LichessPuzzles: skipping puzzle {puzzle_id}, missing fen or solution"
            )
            return None

        puzzle = {
            "id":         puzzle_id,
            "fen":        fen,
            "solution":   solution,
            "rating":     rating,
            "themes":     themes,
            "source":     source,
        }
        if not _is_valid_puzzle_line(puzzle):
            Logger.warning(
                f"LichessPuzzles: dropping invalid puzzle id={puzzle_id} source={source}"
            )
            return None
        return puzzle
    except Exception:
        Logger.exception("LichessPuzzles: failed parsing Lichess response")
        return None


def _is_valid_puzzle_line(puzzle: dict) -> bool:
    try:
        fen = str(puzzle.get("fen", "")).strip()
        solution = list(puzzle.get("solution", []))
        if not fen or not solution:
            return False
        board = chess.Board(fen)
        for move_text in solution:
            move_str = str(move_text)[:5]
            move = chess.Move.from_uci(move_str)
            if move not in board.legal_moves:
                first_move = str(solution[0]) if solution else ""
                turn = fen.split()[1] if len(fen.split()) > 1 else "?"
                Logger.warning(
                    f"LichessPuzzles: invalid_solution id={puzzle.get('id', '')} turn={turn} first_move={first_move} bad_move={move_str}"
                )
                return False
            board.push(move)
        return True
    except Exception:
        try:
            fen = str(puzzle.get("fen", "")).strip()
            turn = fen.split()[1] if len(fen.split()) > 1 else "?"
            first_move = str((puzzle.get("solution") or [""])[0])
            Logger.warning(
                f"LichessPuzzles: invalid_solution id={puzzle.get('id', '')} turn={turn} first_move={first_move}"
            )
        except Exception:
            pass
        return False


def _fen_from_lichess_game(pgn: str, initial_fen: Optional[str], initial_ply: int) -> str:
    """
    Reconstruct the puzzle position from the game PGN.

    Lichess returns SAN moves in game.pgn and the ply index where the puzzle
    starts. We replay the game from the initial FEN, if provided, and stop at
    initialPly.
    """
    try:
        board = chess.Board(initial_fen) if initial_fen else chess.Board()
    except Exception:
        board = chess.Board()

    tokens = []
    for token in str(pgn).replace("\n", " ").split():
        if token.endswith("."):
            continue
        if token in {"1-0", "0-1", "1/2-1/2", "*"}:
            continue
        tokens.append(token)

    for idx, san in enumerate(tokens):
        if idx >= int(initial_ply):
            break
        try:
            board.push_san(san)
        except Exception:
            Logger.warning(
                f"LichessPuzzles: failed replaying SAN move {san!r} at ply {idx}"
            )
            return ""

    return board.fen()


def _get_json(url: str, timeout: int = 8) -> Optional[dict]:
    global _RATE_LIMIT_UNTIL
    now = time.time()
    if now < _RATE_LIMIT_UNTIL:
        Logger.warning(
            f"LichessPuzzles: cooldown active, skipping request to {url}"
        )
        return None
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        context = ssl._create_unverified_context() if platform == "android" else None
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
                Logger.warning(f"LichessPuzzles: {url} returned HTTP {resp.status}")
        except Exception as exc:
            if "CERTIFICATE_VERIFY_FAILED" in str(exc):
                Logger.warning(
                    f"LichessPuzzles: SSL verify failed for {url}, retrying without certificate validation"
                )
                insecure = ssl._create_unverified_context()
                with urllib.request.urlopen(req, timeout=timeout, context=insecure) as resp:
                    if resp.status == 200:
                        return json.loads(resp.read().decode("utf-8"))
                    Logger.warning(f"LichessPuzzles: {url} returned HTTP {resp.status}")
            else:
                raise
    except HTTPError as exc:
        if exc.code == 429:
            _RATE_LIMIT_UNTIL = time.time() + 60
            Logger.warning(
                f"LichessPuzzles: rate limited by {url} (429), pausing requests for 60s"
            )
        else:
            Logger.warning(f"LichessPuzzles: HTTP error from {url}: {exc.code}")
    except Exception as exc:
        Logger.warning(f"LichessPuzzles: request failed for {url}: {exc}")
    return None


def _load_cache() -> list:
    try:
        with open(_CACHE_FILE) as f:
            d = json.load(f)
            return d if isinstance(d, list) else []
    except Exception:
        return []


def _load_seen_ids() -> set[str]:
    global _SEEN_IDS_LOADED, _SEEN_IDS
    if _SEEN_IDS_LOADED:
        return set(_SEEN_IDS)
    try:
        with open(_SEEN_IDS_FILE) as f:
            data = json.load(f)
            if isinstance(data, list):
                _SEEN_IDS = {str(puzzle_id) for puzzle_id in data if str(puzzle_id)}
    except Exception:
        _SEEN_IDS = set()
    _SEEN_IDS_LOADED = True
    return set(_SEEN_IDS)


def _save_seen_ids(seen_ids: set[str]) -> None:
    global _SEEN_IDS_LOADED, _SEEN_IDS
    _SEEN_IDS = {str(puzzle_id) for puzzle_id in seen_ids if str(puzzle_id)}
    _SEEN_IDS_LOADED = True
    os.makedirs(_BASE_DIR, exist_ok=True)
    try:
        with open(_SEEN_IDS_FILE, "w") as f:
            json.dump(sorted(_SEEN_IDS), f)
    except Exception:
        pass


def _remember_seen_ids(puzzle_ids: set[str] | list[str]) -> None:
    seen = _load_seen_ids()
    for puzzle_id in puzzle_ids:
        if puzzle_id:
            seen.add(str(puzzle_id))
    _save_seen_ids(seen)


def _current_target_rating(default: int = 1200) -> int:
    try:
        app = App.get_running_app()
        store = getattr(app, "store", None)
        if store and hasattr(store, "get_score"):
            return int(store.get_score())
    except Exception:
        pass
    return int(default)


def _pending_fetch_count() -> int:
    with _FETCH_QUEUE_LOCK:
        queued = len(_FETCH_REQUESTS)
    return queued + (1 if _FETCH_WORKER_RUNNING else 0)


def log_cache_status(tag: str = "manual") -> None:
    try:
        cache_count = len(_load_cache())
        pending = _pending_fetch_count()
        seen = len(_load_seen_ids())
        Logger.info(
            f"LichessPuzzles: cache_status tag={tag} cache_count={cache_count} seen_ids={seen} pending_fetches={pending} floor={_CACHE_FLOOR}"
        )
    except Exception:
        Logger.exception("LichessPuzzles: failed to log cache status")


def _load_cache_seed_version() -> int:
    try:
        with open(_CACHE_META_FILE) as f:
            data = json.load(f)
            return int(data.get("version", 0))
    except Exception:
        return 0


def _save_cache_seed_version(version: int):
    os.makedirs(_BASE_DIR, exist_ok=True)
    try:
        with open(_CACHE_META_FILE, "w") as f:
            json.dump({"version": int(version)}, f)
    except Exception:
        pass


def _save_cache(puzzles: list):
    os.makedirs(_BASE_DIR, exist_ok=True)
    try:
        existing = {str(p.get("id", "")): p for p in _load_cache() if p.get("id")}
        for p in puzzles:
            puzzle_id = str(p.get("id", ""))
            if puzzle_id:
                existing[puzzle_id] = p
        combined = _dedupe_keep_order(list(existing.values()))[-300:]
        with open(_CACHE_FILE, "w") as f:
            json.dump(combined, f)
    except Exception:
        pass


def _write_cache(puzzles: list):
    os.makedirs(_BASE_DIR, exist_ok=True)
    try:
        combined = _dedupe_keep_order(puzzles)[-300:]
        with open(_CACHE_FILE, "w") as f:
            json.dump(combined, f)
    except Exception:
        pass


def _cache_ids() -> set[str]:
    return {
        _base_puzzle_id(str(puzzle.get("id", "")))
        for puzzle in _load_cache()
        if puzzle.get("id")
    }


def _append_to_cache(puzzles: list) -> None:
    if not puzzles:
        return
    existing = _load_cache()
    before = len(existing)
    seen = {
        _base_puzzle_id(str(p.get("id", "")))
        for p in existing
        if p.get("id")
    }
    seen |= _load_seen_ids()
    for puzzle in puzzles:
        puzzle_id = _base_puzzle_id(str(puzzle.get("id", "")))
        if not puzzle_id or puzzle_id in seen:
            continue
        normalized = dict(puzzle)
        if normalized.get("source") != "lichess":
            normalized["source"] = "cache"
        existing.append(normalized)
        seen.add(puzzle_id)
    _save_seen_ids(seen)
    _write_cache(existing[-300:])
    Logger.info(
        f"LichessPuzzles: cache_append before={before} added={len(puzzles)} after={len(existing[-300:])}"
    )


def _normalize_cached_puzzle(puzzle: dict) -> dict:
    normalized = dict(puzzle)
    if normalized.get("source") != "lichess":
        normalized["source"] = "cache"
    return normalized


def _valid_cached_puzzles(puzzles: list) -> list:
    valid = []
    for puzzle in puzzles:
        normalized = _normalize_cached_puzzle(puzzle)
        if _is_valid_puzzle_line(normalized):
            valid.append(normalized)
    return valid


def _load_valid_cache(prune: bool = False) -> list:
    cache = _load_cache()
    valid = _valid_cached_puzzles(cache)
    if prune and len(valid) != len(cache):
        try:
            _write_cache(valid)
            Logger.warning(
                f"LichessPuzzles: pruned_invalid_cache removed={len(cache) - len(valid)} remaining={len(valid)}"
            )
        except Exception:
            Logger.exception("LichessPuzzles: failed pruning invalid cache")
    return valid


def _remove_from_cache(puzzle_id: str) -> None:
    base_id = _base_puzzle_id(str(puzzle_id))
    if not base_id:
        return
    cache = [
        puzzle for puzzle in _load_cache()
        if _base_puzzle_id(str(puzzle.get("id", ""))) != base_id
    ]
    _write_cache(cache)
    _remember_seen_ids({base_id})
    Logger.info(f"LichessPuzzles: cache_remove id={base_id} remaining={len(cache)}")


def _fetch_live_puzzle(exclude_ids: Optional[set[str]] = None) -> Optional[dict]:
    exclude_ids = set(exclude_ids or set()) | _SOLVED_IDS | _load_seen_ids() | _cache_ids()
    for url in [_LICHESS_NEXT]:
        data = _get_json(url)
        if not data:
            continue
        puzzle = _parse_lichess_response(data, source="lichess")
        if not puzzle:
            continue
        puzzle_id = _base_puzzle_id(str(puzzle.get("id", "")))
        if puzzle_id and puzzle_id not in exclude_ids:
            Logger.info(f"LichessPuzzles: fetched_live id={puzzle_id} rating={puzzle.get('rating', 0)}")
            return puzzle
    return None


def _fallback_bundled_puzzles(target_rating: int, needed: int, exclude_ids: Optional[set[str]] = None) -> list:
    taken = []
    excluded = set(exclude_ids or set()) | _SOLVED_IDS
    for puzzle in _bundle_order(target_rating):
        puzzle_id = _base_puzzle_id(str(puzzle.get("id", "")))
        if not puzzle_id or puzzle_id in excluded:
            continue
        taken.append(dict(puzzle))
        if len(taken) >= needed:
            break
    return taken


def _fallback_from_cache(count: int, exclude_ids: Optional[set[str]] = None) -> list:
    excluded = set(exclude_ids or set()) | _SOLVED_IDS
    cache = _load_cache()
    result = []
    for puzzle in cache:
        puzzle_id = _base_puzzle_id(str(puzzle.get("id", "")))
        if not puzzle_id or puzzle_id in excluded:
            continue
        result.append(dict(puzzle))
        if len(result) >= count:
            break
    return result


def _queue_fetch_request(target_rating: int, callback=None, exclude_ids: Optional[set[str]] = None) -> bool:
    global _FETCH_WORKER_RUNNING
    with _FETCH_QUEUE_LOCK:
        if _FETCH_WORKER_RUNNING or _FETCH_REQUESTS:
            Logger.info(
                f"LichessPuzzles: fetch already pending, skipping new request target={target_rating} queue_size={len(_FETCH_REQUESTS)}"
            )
            return False
        _FETCH_REQUESTS.append(
            {
                "target_rating": int(target_rating),
                "callback": callback,
                "exclude_ids": set(exclude_ids or set()),
            }
        )
        Logger.info(
            f"LichessPuzzles: queued_fetch target={target_rating} queue_size={len(_FETCH_REQUESTS)}"
        )
        if _FETCH_WORKER_RUNNING:
            return True
        _FETCH_WORKER_RUNNING = True

    threading.Thread(target=_process_fetch_queue, daemon=True).start()
    return True


def _process_fetch_queue():
    global _FETCH_WORKER_RUNNING
    while True:
        with _FETCH_QUEUE_LOCK:
            if not _FETCH_REQUESTS:
                _FETCH_WORKER_RUNNING = False
                return
            request = _FETCH_REQUESTS.popleft()

        target_rating = request["target_rating"]
        callback = request["callback"]
        exclude_ids = set(request["exclude_ids"]) | _cache_ids() | _SOLVED_IDS | _load_seen_ids()

        puzzle = None
        try:
            Logger.info(
                f"LichessPuzzles: processing_fetch target={target_rating} exclude={len(exclude_ids)} cache_count={len(_load_cache())}"
            )
            puzzle = _fetch_live_puzzle(exclude_ids=exclude_ids)
        except Exception:
            Logger.exception("LichessPuzzles: live fetch failed while processing queue")

        if puzzle:
            try:
                _append_to_cache([puzzle])
            except Exception:
                Logger.exception("LichessPuzzles: failed appending live puzzle to cache")
            if callback:
                try:
                    callback(dict(puzzle))
                except Exception:
                    Logger.exception("LichessPuzzles: fetch callback failed")
            continue

        try:
            cache = _load_cache()
        except Exception:
            cache = []

        if not cache:
            try:
                seed_bundled_puzzle_cache(target_rating)
                cache = _load_cache()
            except Exception:
                cache = []

        if callback and cache:
            try:
                Logger.info(
                    f"LichessPuzzles: fallback_from_cache target={target_rating} cache_count={len(cache)}"
                )
                callback(_normalize_cached_puzzle(cache[0]))
            except Exception:
                Logger.exception("LichessPuzzles: fallback callback failed")
        elif callback:
            Logger.warning("LichessPuzzles: no puzzle available for callback after fetch failure")


def _base_puzzle_id(puzzle_id: str) -> str:
    return puzzle_id.split("::repeat::", 1)[0]


def delete_puzzle(puzzle_id: str, target_rating: Optional[int] = None):
    global _READY_PUZZLES, _LAST_PUZZLE, _SOLVED_IDS
    resolved_rating = int(target_rating or 1000)
    base_id = _base_puzzle_id(puzzle_id)
    if base_id:
        _SOLVED_IDS.add(base_id)
    cache_before = len(_load_cache())
    with _POOL_LOCK:
        _READY_PUZZLES = [
            p for p in _READY_PUZZLES
            if _base_puzzle_id(str(p.get("id", ""))) != base_id
        ]
        if _LAST_PUZZLE and _base_puzzle_id(str(_LAST_PUZZLE.get("id", ""))) == base_id:
            _LAST_PUZZLE = None
    _remove_from_cache(base_id)
    try:
        cache_count = len(_load_cache())
        if cache_count == 0:
            seed_bundled_puzzle_cache(resolved_rating)
            cache_count = len(_load_cache())
            Logger.info(
                f"LichessPuzzles: cache_restored_from_bundle target={resolved_rating} cache_puzzles={cache_count}"
            )
        ensure_puzzle_buffer(resolved_rating, _CACHE_TARGET)
        Logger.info(
            f"LichessPuzzles: delete_puzzle solved_id={base_id} target={resolved_rating} cache_before={cache_before} cache_after={cache_count}"
        )
    except Exception:
        Logger.exception("LichessPuzzles: failed to replenish cache after delete")


def _rating_distance(puzzle: dict, target_rating: int) -> int:
    return abs(int(puzzle.get("rating", 1500)) - int(target_rating))


def _matches_target(puzzle: dict, target_rating: int) -> bool:
    return _rating_distance(puzzle, target_rating) <= _TARGET_WINDOW


def _dedupe_keep_order(puzzles: list) -> list:
    seen = set()
    deduped = []
    for puzzle in puzzles:
        puzzle_id = _base_puzzle_id(str(puzzle.get("id", "")))
        if not puzzle_id:
            continue
        if puzzle_id in seen:
            continue
        seen.add(puzzle_id)
        deduped.append(puzzle)
    return deduped


def _prioritize_puzzles(puzzles: list, target_rating: int) -> list:
    puzzles = _dedupe_keep_order(puzzles)
    matching = [p for p in puzzles if _matches_target(p, target_rating)]
    fallback = [p for p in puzzles if not _matches_target(p, target_rating)]
    matching.sort(key=lambda p: _rating_distance(p, target_rating))
    fallback.sort(key=lambda p: _rating_distance(p, target_rating))
    return matching + fallback


def _bundle_order(target_rating: int = 1000) -> list:
    return _prioritize_puzzles(list(_BUNDLED_STARTER_PUZZLES), target_rating)


def _bundle_ids() -> set[str]:
    return {
        _base_puzzle_id(str(puzzle.get("id", "")))
        for puzzle in _BUNDLED_STARTER_PUZZLES
        if puzzle.get("id")
    }


def _clear_bundled_exclusions() -> None:
    global _SOLVED_IDS
    bundle_ids = _bundle_ids()
    if not bundle_ids:
        return
    _SOLVED_IDS = {puzzle_id for puzzle_id in _SOLVED_IDS if puzzle_id not in bundle_ids}
    try:
        seen = _load_seen_ids()
        seen = {puzzle_id for puzzle_id in seen if puzzle_id not in bundle_ids}
        _save_seen_ids(seen)
    except Exception:
        Logger.exception("LichessPuzzles: failed clearing bundled exclusions")


def _bundle_unique_queue(target_rating: int = 1000, desired: int = _BANK_TARGET_READY) -> list:
    base = _bundle_order(target_rating)
    if not base:
        return []
    queue = []
    for puzzle in base:
        queue.append(dict(puzzle))
        if len(queue) >= desired:
            break
    return queue


def _filter_excluded(puzzles: list, exclude_ids: set[str] | None) -> list:
    if not exclude_ids:
        return list(puzzles)
    return [
        puzzle for puzzle in puzzles
        if puzzle.get("id") not in exclude_ids
    ]


def _cached_candidates(target_rating: int) -> list:
    cache = _load_valid_cache(prune=True)
    if _SOLVED_IDS:
        cache = [
            puzzle for puzzle in cache
            if _base_puzzle_id(str(puzzle.get("id", ""))) not in _SOLVED_IDS
        ]
    return _prioritize_puzzles(_valid_cached_puzzles(cache), target_rating)


def _queue_candidates(exclude_ids: Optional[set[str]] = None) -> list:
    cache = _load_valid_cache(prune=True)
    exclude = set(exclude_ids or set()) | _SOLVED_IDS
    queued = []
    for puzzle in cache:
        puzzle_id = str(puzzle.get("id", ""))
        if not puzzle_id or puzzle_id in exclude:
            continue
        normalized = _normalize_cached_puzzle(puzzle)
        if _is_valid_puzzle_line(normalized):
            queued.append(normalized)
    return queued


def seed_bundled_puzzle_cache(target_rating: int = 1000) -> bool:
    """
    Ensure every install starts with a 20-puzzle local bank.
    Returns True when the on-disk cache was written.
    """
    cache = _load_cache()
    seed_ids = {_base_puzzle_id(str(p.get("id", ""))) for p in _bundle_unique_queue(target_rating)}
    cached_ids = {_base_puzzle_id(str(p.get("id", ""))) for p in cache}
    if _load_cache_seed_version() == _BUNDLED_CACHE_VERSION and seed_ids.issubset(cached_ids) and len(cache) >= _BANK_TARGET_READY:
        Logger.info(
            f"LichessPuzzles: seed skipped version={_BUNDLED_CACHE_VERSION} cache_count={len(cache)} target={target_rating}"
        )
        return False

    seeded = [_normalize_cached_puzzle(p) for p in _bundle_unique_queue(target_rating)]
    _write_cache(seeded)
    _save_cache_seed_version(_BUNDLED_CACHE_VERSION)
    Logger.info(
        f"LichessPuzzles: seeded puzzle bank with {len(seeded)} bundled puzzles target={target_rating}"
    )
    return True


def _bundled_candidates(target_rating: int) -> list:
    bundled = [
        puzzle for puzzle in _BUNDLED_STARTER_PUZZLES
        if _base_puzzle_id(str(puzzle.get("id", ""))) not in _SOLVED_IDS
    ]
    return _prioritize_puzzles(bundled, target_rating)


def _fetch_unique_puzzles(
    target_rating: int,
    count: int,
    exclude_ids: Optional[set[str]] = None,
) -> list:
    exclude = set(exclude_ids or set()) | _SOLVED_IDS | _load_seen_ids() | _cache_ids()
    fetched = []
    attempts = 0
    max_attempts = max(6, int(count) * 4)

    while len(fetched) < int(count) and attempts < max_attempts:
        attempts += 1
        puzzle = fetch_puzzle_from_lichess(exclude_ids=exclude)
        if not puzzle:
            continue
        puzzle_id = _base_puzzle_id(str(puzzle.get("id", "")))
        if not puzzle_id or puzzle_id in exclude:
            continue
        exclude.add(puzzle_id)
        fetched.append(puzzle)

    if len(fetched) < count:
        Logger.warning(
            f"LichessPuzzles: only fetched {len(fetched)}/{count} unique puzzles for target={target_rating}"
        )
    return _prioritize_puzzles(fetched, target_rating)


def fetch_puzzle_from_lichess(
    exclude_ids: Optional[set[str]] = None,
) -> Optional[dict]:
    exclude_ids = set(exclude_ids or set()) | _SOLVED_IDS | _load_seen_ids() | _cache_ids()
    if not _FETCH_LOCK.acquire(blocking=False):
        Logger.warning("LichessPuzzles: fetch already in progress, skipping parallel request")
        return None
    try:
        puzzle = _fetch_live_puzzle(exclude_ids=exclude_ids)
        if puzzle:
            _append_to_cache([puzzle])
            return puzzle
        Logger.warning("LichessPuzzles: no puzzle returned from Lichess endpoints")
        return None
    finally:
        try:
            _FETCH_LOCK.release()
        except Exception:
            pass


def _fill_ready_pool(target_rating: int, min_ready: int):
    global _FETCH_IN_FLIGHT, _READY_PUZZLES, _LAST_PUZZLE

    with _POOL_LOCK:
        existing = list(_READY_PUZZLES)

    cached = _prioritize_puzzles(existing + _cached_candidates(target_rating), target_rating)

    needed = max(0, min_ready - len(cached))
    fetched = _fetch_unique_puzzles(
        target_rating,
        needed,
        exclude_ids={_base_puzzle_id(str(p.get("id", ""))) for p in cached},
    )
    if fetched and not _LAST_PUZZLE:
        _LAST_PUZZLE = fetched[-1]

    with _POOL_LOCK:
        merged = _prioritize_puzzles(fetched + cached, target_rating)
        _READY_PUZZLES = merged
        _FETCH_IN_FLIGHT = False


def ensure_puzzle_buffer(target_rating: int = 1200, min_ready: int = _CACHE_FLOOR):
    try:
        cache = _load_valid_cache(prune=True)
    except Exception:
        cache = []

    if not cache:
        try:
            seed_bundled_puzzle_cache(target_rating)
            cache = _load_valid_cache(prune=True)
        except Exception:
            Logger.exception("LichessPuzzles: failed seeding bundled cache")
            return

    usable_cache = [
        puzzle for puzzle in cache
        if _base_puzzle_id(str(puzzle.get("id", ""))) not in _SOLVED_IDS
    ]
    current = len(usable_cache)
    pending = _pending_fetch_count()
    if current >= int(min_ready):
        Logger.info(
            f"LichessPuzzles: ensure_cache_floor cache_count={current} floor={min_ready} pending_fetches={pending} needed_fetches=0 target={target_rating}"
        )
        return
    if pending > 0:
        Logger.info(
            f"LichessPuzzles: ensure_cache_floor cache_count={current} floor={min_ready} pending_fetches={pending} needed_fetches=0 target={target_rating} status=waiting"
        )
        return
    needed = max(0, int(min_ready) - current)
    Logger.info(
        f"LichessPuzzles: ensure_cache_floor cache_count={current} floor={min_ready} pending_fetches={pending} needed_fetches={needed} target={target_rating}"
    )
    try:
        _fetch_unique_puzzles(
            target_rating,
            needed,
            exclude_ids=_cache_ids() | _SOLVED_IDS | _load_seen_ids(),
        )
    except Exception:
        Logger.exception("LichessPuzzles: failed filling puzzle buffer")


def queue_puzzle_fetch(
    target_rating: int = 1200,
    callback=None,
    exclude_ids: Optional[set[str]] = None,
) -> bool:
    try:
        _queue_fetch_request(target_rating, callback=callback, exclude_ids=exclude_ids)
        return True
    except Exception:
        Logger.exception("LichessPuzzles: failed to queue puzzle fetch")
        return False


def get_puzzles_for_alarm(
    target_rating: int = 1200,
    count: int = 3,
    allow_repeat_last: bool = False,
    exclude_ids: Optional[set[str]] = None,
) -> list:
    global _LAST_PUZZLE
    exclude_ids = set(exclude_ids or set()) | _SOLVED_IDS

    taken = []
    taken_ids = set()

    live = _fetch_unique_puzzles(
        target_rating,
        count,
        exclude_ids=exclude_ids,
    )
    for puzzle in live:
        puzzle_id = _base_puzzle_id(str(puzzle.get("id", "")))
        if not puzzle_id or puzzle_id in exclude_ids or puzzle_id in taken_ids:
            continue
        taken.append(puzzle)
        taken_ids.add(puzzle_id)
        if len(taken) >= count:
            break

    cache = _load_valid_cache(prune=True)
    seeded_from_bundle = False
    if not cache and len(taken) < count:
        try:
            seed_bundled_puzzle_cache(target_rating)
            cache = _load_valid_cache(prune=True)
            seeded_from_bundle = bool(cache)
        except Exception:
            Logger.exception("LichessPuzzles: could not seed bundled cache")
            cache = []

    for puzzle in cache:
        puzzle_id = _base_puzzle_id(str(puzzle.get("id", "")))
        if not puzzle_id or puzzle_id in exclude_ids or puzzle_id in taken_ids:
            continue
        normalized = _normalize_cached_puzzle(puzzle)
        if not _is_valid_puzzle_line(normalized):
            continue
        taken.append(normalized)
        taken_ids.add(puzzle_id)
        if len(taken) >= count:
            break

    if len(taken) < count:
        live_needed = count - len(taken)
        live = _fetch_unique_puzzles(
            target_rating,
            live_needed,
            exclude_ids=exclude_ids | taken_ids,
        )
        for puzzle in live:
            puzzle_id = _base_puzzle_id(str(puzzle.get("id", "")))
            if not puzzle_id or puzzle_id in exclude_ids or puzzle_id in taken_ids:
                continue
            taken.append(puzzle)
            taken_ids.add(puzzle_id)
            if len(taken) >= count:
                break

    if len(taken) < count and not cache:
        bundled = [
            _normalize_cached_puzzle(p)
            for p in _fallback_bundled_puzzles(
                target_rating,
                _BANK_TARGET_READY,
                exclude_ids=exclude_ids,
            )
        ]
        if bundled:
            try:
                _write_cache(bundled[:_BANK_TARGET_READY])
            except Exception:
                pass
            taken.extend(bundled[: max(0, count - len(taken))])

    if taken:
        _LAST_PUZZLE = taken[-1]

    Logger.info(
        f"LichessPuzzles: get_for_alarm cache_puzzles={len(cache)} returned={len(taken)} target={target_rating} allow_repeat_last={allow_repeat_last}"
    )

    if allow_repeat_last and len(taken) < count and _LAST_PUZZLE:
        while len(taken) < count:
            taken.append(_clone_repeat_puzzle(_LAST_PUZZLE))

    if seeded_from_bundle:
        Logger.info(
            f"LichessPuzzles: bundled_fallback_active target={target_rating} cache_puzzles={len(cache)}"
        )
    ensure_puzzle_buffer(target_rating, _CACHE_TARGET)
    return taken[:count]


def get_fresh_replacement_puzzle(
    target_rating: int,
    exclude_ids: Optional[set[str]] = None,
) -> Optional[dict]:
    try:
        puzzle = _fetch_live_puzzle(exclude_ids=exclude_ids)
        if puzzle:
            _append_to_cache([puzzle])
            return puzzle
    except Exception:
        Logger.exception("LichessPuzzles: replacement fetch failed")

    cache = _load_valid_cache(prune=True)
    if cache:
        return cache[0]

    bundled = _fallback_bundled_puzzles(target_rating, 1, exclude_ids=exclude_ids)
    if not bundled:
        return None
    try:
        _write_cache(bundled)
    except Exception:
        pass
    return _normalize_cached_puzzle(bundled[0])


def start_cache_monitor(interval: int = 10) -> bool:
    global _CACHE_MONITOR_STARTED
    if _CACHE_MONITOR_STARTED:
        return False
    _CACHE_MONITOR_STARTED = True

    def _run():
        while True:
            try:
                target_rating = _current_target_rating()
                log_cache_status(tag=f"monitor target={target_rating}")
                ensure_puzzle_buffer(target_rating, _CACHE_FLOOR)
            except Exception:
                Logger.exception("LichessPuzzles: cache monitor failed")
            time.sleep(max(1, int(interval)))

    threading.Thread(target=_run, daemon=True).start()
    return True
