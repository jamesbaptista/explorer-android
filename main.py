import os
import random
import math
from collections import deque
from dataclasses import dataclass
import pygame

# ---------------------------------------------------------------------------
# Android detection
# ---------------------------------------------------------------------------
ANDROID = os.environ.get("ANDROID_ARGUMENT") is not None

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TILE          = 40
COLS          = 15
ROWS          = 15
HUD_H         = 50          # slightly taller to fit piece counter
WIN_W         = COLS * TILE  # 600
WIN_H         = ROWS * TILE + HUD_H  # 650
FPS           = 60
NUM_PIECES    = 5            # nugget pieces to collect

FLASH_DURATION  = 75   # frames for pitfall red flash
PIECE_DURATION  = 120  # frames for piece-found sequence (2 s @ 60 fps)
# The flying icon travels from the tile to the HUD in the first PIECE_FLY frames
PIECE_FLY       = 55   # frames for the fly animation portion

DIFFICULTY = {
    "Easy":   15,
    "Medium": 20,
    "Hard":   25,
}

# Relative path — works on both desktop (CWD = project folder) and Android
NUGGET_IMAGE_PATH = "gold_nugget.png"

# ---------------------------------------------------------------------------
# Android D-pad zone
# ---------------------------------------------------------------------------
DPAD_H    = 160   # extra pixels at bottom for D-pad (Android only)
BTN_SIZE  = 64    # D-pad button square size
BTN_GAP   = 6

_extra  = DPAD_H if ANDROID else 0
TOTAL_H = WIN_H + _extra

DPAD_CX = WIN_W // 2           # D-pad cluster horizontal centre
DPAD_CY = WIN_H + DPAD_H // 2  # D-pad cluster vertical centre

# pygame.Rect is safe before pygame.init()
DPAD_RECTS = {
    pygame.K_UP:    pygame.Rect(DPAD_CX - BTN_SIZE // 2,
                                DPAD_CY - BTN_SIZE - BTN_GAP,
                                BTN_SIZE, BTN_SIZE),
    pygame.K_DOWN:  pygame.Rect(DPAD_CX - BTN_SIZE // 2,
                                DPAD_CY + BTN_GAP,
                                BTN_SIZE, BTN_SIZE),
    pygame.K_LEFT:  pygame.Rect(DPAD_CX - BTN_SIZE * 3 // 2 - BTN_GAP,
                                DPAD_CY - BTN_SIZE // 2,
                                BTN_SIZE, BTN_SIZE),
    pygame.K_RIGHT: pygame.Rect(DPAD_CX + BTN_SIZE // 2 + BTN_GAP,
                                DPAD_CY - BTN_SIZE // 2,
                                BTN_SIZE, BTN_SIZE),
}
DPAD_LABELS = {
    pygame.K_UP:    "▲",
    pygame.K_DOWN:  "▼",
    pygame.K_LEFT:  "◀",
    pygame.K_RIGHT: "▶",
}

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
C_BG           = ( 18,  14,  10)
C_HUD_BG       = ( 22,  18,  12)
C_HUD_LINE     = ( 80,  60,  30)
C_TEXT         = (235, 215, 165)
C_TEXT_DIM     = (140, 110,  70)

C_ROCK_BASE    = (105,  98,  88)
C_ROCK_MID     = ( 88,  82,  72)
C_ROCK_DARK    = ( 60,  55,  48)
C_ROCK_LIGHT   = (148, 140, 128)
C_ROCK_HILIGHT = (180, 172, 158)
C_ROCK_SHADOW  = ( 40,  36,  30)
C_ROCK_CRACK   = ( 50,  45,  38)

C_FLOOR_BASE   = (148, 108,  62)
C_FLOOR_DARK   = (112,  82,  45)
C_FLOOR_GRAIN  = (130,  94,  52)

C_PIT_DARK     = ( 20,   8,   4)
C_PIT_MID      = ( 45,  18,  10)
C_PIT_RIM      = ( 80,  40,  20)
C_PIT_WARNING  = (200,  60,  20)

C_GOLD_BRIGHT  = (255, 230,  60)
C_GOLD_MID     = (230, 185,  20)
C_GOLD_DARK    = (160, 110,   0)
C_GOLD_SHEEN   = (255, 248, 180)

C_SKIN         = (220, 170, 110)
C_HAT          = ( 80,  52,  22)
C_HAT_BAND     = (180, 140,  60)
C_SHIRT        = ( 60,  90, 140)
C_PACK         = (130,  80,  35)
C_BOOT         = ( 55,  38,  18)

C_FLASH_RED    = (200,  40,  20)

C_BTN_NORM     = ( 50,  38,  18)
C_BTN_HOVER    = ( 90,  68,  28)
C_BTN_SEL      = (140, 100,  20)
C_BTN_BORDER   = (180, 140,  60)

START_POS = (7, 7)


# ---------------------------------------------------------------------------
# Font loader — bundled TTFs on Android, SysFont on desktop
# ---------------------------------------------------------------------------
def _load_fonts() -> dict:
    if ANDROID:
        reg  = "assets/mono.ttf"
        bold = "assets/mono_bold.ttf"
        return {
            "title": pygame.font.Font(bold, 46),
            "hud":   pygame.font.Font(bold, 18),
            "big":   pygame.font.Font(bold, 30),
            "med":   pygame.font.Font(reg,  18),
            "small": pygame.font.Font(reg,  15),
            "body":  pygame.font.Font(reg,  17),
            "btn":   pygame.font.Font(bold, 17),
        }
    else:
        return {
            "title": pygame.font.SysFont("consolas", 46, bold=True),
            "hud":   pygame.font.SysFont("consolas", 18, bold=True),
            "big":   pygame.font.SysFont("consolas", 30, bold=True),
            "med":   pygame.font.SysFont("consolas", 18),
            "small": pygame.font.SysFont("consolas", 15),
            "body":  pygame.font.SysFont("consolas", 17),
            "btn":   pygame.font.SysFont("consolas", 17, bold=True),
        }


# ---------------------------------------------------------------------------
# BFS / placement
# ---------------------------------------------------------------------------
def _bfs_reachable(start: tuple, goal: tuple, blocked: set) -> bool:
    if start == goal:
        return True
    visited = {start}
    q = deque([start])
    while q:
        cx, cy = q.popleft()
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nb = (cx+dx, cy+dy)
            if nb == goal:
                return True
            if (0 <= nb[0] < COLS and 0 <= nb[1] < ROWS
                    and nb not in blocked and nb not in visited):
                visited.add(nb)
                q.append(nb)
    return False


def place_items(num_pitfalls: int) -> tuple:
    """
    Returns (piece_positions: list[tuple], pitfall_set: set).
    Places NUM_PIECES nugget pieces each guaranteed reachable from START_POS.
    Pitfalls are placed ensuring every piece remains reachable.
    """
    all_cells = {(c, r) for c in range(COLS) for r in range(ROWS)}
    forbidden = {START_POS}

    # Place nugget pieces one at a time
    pieces = []
    pool = list(all_cells - forbidden)
    random.shuffle(pool)
    for cell in pool:
        if len(pieces) >= NUM_PIECES:
            break
        if _bfs_reachable(START_POS, cell, set()):
            pieces.append(cell)
            forbidden.add(cell)

    # Place pitfalls ensuring every piece is still reachable
    pitfalls: set = set()
    candidates = list(all_cells - forbidden)
    random.shuffle(candidates)

    for cell in candidates:
        if len(pitfalls) >= num_pitfalls:
            break
        trial = pitfalls | {cell}
        # All pieces must still be reachable
        if all(_bfs_reachable(START_POS, p, trial) for p in pieces):
            pitfalls.add(cell)

    return pieces, pitfalls


# ---------------------------------------------------------------------------
# Tile surface cache
# ---------------------------------------------------------------------------
def _make_rock_surface(seed: int) -> pygame.Surface:
    rng = random.Random(seed)
    surf = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
    surf.fill(C_ROCK_BASE)
    cx, cy = TILE // 2, TILE // 2
    n_pts = rng.randint(6, 9)

    pts = [(cx + rng.randint(12,17)*math.cos(2*math.pi*i/n_pts+rng.uniform(-0.25,0.25)),
            cy + rng.randint(12,17)*math.sin(2*math.pi*i/n_pts+rng.uniform(-0.25,0.25)))
           for i in range(n_pts)]
    pygame.draw.polygon(surf, C_ROCK_MID, pts)

    hi_pts = [(cx-2 + rng.randint(7,12)*math.cos(2*math.pi*i/n_pts+rng.uniform(-0.15,0.15)),
               cy-2 + rng.randint(7,12)*math.sin(2*math.pi*i/n_pts+rng.uniform(-0.15,0.15)))
              for i in range(n_pts)]
    pygame.draw.polygon(surf, C_ROCK_LIGHT, hi_pts)

    hx = cx + rng.randint(-6,-2); hy = cy + rng.randint(-6,-2)
    pygame.draw.circle(surf, C_ROCK_HILIGHT, (hx, hy), rng.randint(2,4))

    sh_pts = [(cx+4 + rng.randint(6,11)*math.cos(2*math.pi*i/n_pts+rng.uniform(-0.1,0.1)),
               cy+4 + rng.randint(6,11)*math.sin(2*math.pi*i/n_pts+rng.uniform(-0.1,0.1)))
              for i in range(n_pts)]
    pygame.draw.polygon(surf, C_ROCK_DARK, sh_pts)
    pygame.draw.polygon(surf, C_ROCK_MID, pts)
    pygame.draw.polygon(surf, C_ROCK_LIGHT, hi_pts)
    pygame.draw.circle(surf, C_ROCK_HILIGHT, (hx, hy), rng.randint(2,4))

    for _ in range(rng.randint(1,2)):
        sx=cx+rng.randint(-7,7); sy=cy+rng.randint(-7,7)
        pygame.draw.line(surf, C_ROCK_CRACK, (sx,sy),
                         (sx+rng.randint(-6,6), sy+rng.randint(-6,6)), 1)

    pygame.draw.rect(surf, C_ROCK_SHADOW, surf.get_rect(), 1)
    return surf


def _make_floor_surface(seed: int) -> pygame.Surface:
    rng = random.Random(seed + 10000)
    surf = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
    surf.fill(C_FLOOR_BASE)
    for _ in range(rng.randint(3,6)):
        x1=rng.randint(0,TILE); y1=rng.randint(0,TILE)
        pygame.draw.line(surf, C_FLOOR_GRAIN, (x1,y1),
                         (x1+rng.randint(-8,8), y1+rng.randint(-3,3)), 1)
    for _ in range(rng.randint(2,4)):
        pygame.draw.circle(surf, C_FLOOR_DARK,
                           (rng.randint(3,TILE-3), rng.randint(3,TILE-3)), 1)
    pygame.draw.rect(surf, C_FLOOR_DARK, surf.get_rect(), 1)
    return surf


def _make_pit_surface() -> pygame.Surface:
    surf = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
    surf.fill(C_FLOOR_BASE)
    rng = random.Random(42)
    for _ in range(4):
        x1=rng.randint(0,TILE); y1=rng.randint(0,TILE)
        pygame.draw.line(surf, C_FLOOR_GRAIN, (x1,y1),
                         (x1+rng.randint(-6,6), y1+rng.randint(-3,3)), 1)
    cx, cy = TILE//2, TILE//2
    pygame.draw.ellipse(surf, C_PIT_DARK, (cx-14, cy-11, 28, 22))
    pygame.draw.ellipse(surf, C_PIT_MID,  (cx-12, cy-9,  24, 18))
    pygame.draw.ellipse(surf, C_PIT_RIM,  (cx-14, cy-11, 28, 22), 2)
    w = 6
    pygame.draw.line(surf, C_PIT_WARNING, (cx-w, cy-w), (cx+w, cy+w), 2)
    pygame.draw.line(surf, C_PIT_WARNING, (cx+w, cy-w), (cx-w, cy+w), 2)
    pygame.draw.rect(surf, C_FLOOR_DARK, surf.get_rect(), 1)
    return surf


def _make_piece_surface() -> pygame.Surface:
    """Small glowing gold shard shown on the floor when a piece is uncovered."""
    surf = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
    surf.fill(C_FLOOR_BASE)
    rng = random.Random(77)
    for _ in range(4):
        x1=rng.randint(0,TILE); y1=rng.randint(0,TILE)
        pygame.draw.line(surf, C_FLOOR_GRAIN, (x1,y1),
                         (x1+rng.randint(-6,6), y1+rng.randint(-3,3)), 1)
    cx, cy = TILE//2, TILE//2
    # nugget shard — irregular polygon
    pts = []
    for i in range(7):
        a = 2*math.pi*i/7 + 0.2
        r = 9 if i % 2 == 0 else 5
        pts.append((cx + r*math.cos(a), cy + r*math.sin(a)))
    pygame.draw.polygon(surf, C_GOLD_MID,    pts)
    pygame.draw.polygon(surf, C_GOLD_BRIGHT, pts, 2)
    pygame.draw.circle(surf, C_GOLD_SHEEN, (cx-2, cy-3), 2)
    pygame.draw.rect(surf, C_FLOOR_DARK, surf.get_rect(), 1)
    return surf


_rock_cache:    dict = {}
_floor_cache:   dict = {}
_pit_surf:      pygame.Surface | None = None
_piece_surf:    pygame.Surface | None = None
_nugget_sprite: pygame.Surface | None = None


def build_tile_cache():
    global _pit_surf, _piece_surf, _nugget_sprite
    for row in range(ROWS):
        for col in range(COLS):
            seed = row * COLS + col
            _rock_cache[(col,row)]  = _make_rock_surface(seed)
            _floor_cache[(col,row)] = _make_floor_surface(seed)
    _pit_surf   = _make_pit_surface()
    _piece_surf = _make_piece_surface()

    if NUGGET_IMAGE_PATH:
        try:
            raw = pygame.image.load(NUGGET_IMAGE_PATH)
            _nugget_sprite = raw.convert_alpha()
        except Exception as e:
            print(f"[explorer] Could not load nugget image: {e}")
            _nugget_sprite = None


# ---------------------------------------------------------------------------
# Procedural gold nugget fallback
# ---------------------------------------------------------------------------
def draw_gold_nugget(surf, cx, cy, radius, angle):
    sq = 0.65
    pygame.draw.ellipse(surf,(10,8,4),(cx-radius,cy+int(radius*sq)-4,radius*2,int(radius*sq*0.5)))
    pygame.draw.ellipse(surf,C_GOLD_DARK,(cx-radius,cy-int(radius*sq),radius*2,int(radius*sq*2)))
    off=int(radius*0.15*math.cos(angle)); offy=int(radius*0.1*math.sin(angle))
    r2=int(radius*0.85)
    pygame.draw.ellipse(surf,C_GOLD_MID,(cx-r2+off,cy-int(r2*sq)+offy,r2*2,int(r2*sq*2)))
    shx=int(radius*0.35*math.cos(angle-0.4)); shy=int(radius*0.25*math.sin(angle-0.4)*sq)
    r3=int(radius*0.55)
    pygame.draw.ellipse(surf,C_GOLD_BRIGHT,(cx-r3+shx,cy-int(r3*sq)+shy,r3*2,int(r3*sq*2)))
    hx=cx+int(radius*0.35*math.cos(angle-0.8)); hy=cy+int(radius*0.25*math.sin(angle-0.8)*sq)
    pygame.draw.circle(surf,C_GOLD_SHEEN,(hx,hy),max(2,radius//5))
    pygame.draw.ellipse(surf,C_GOLD_DARK,(cx-radius,cy-int(radius*sq),radius*2,int(radius*sq*2)),2)


# ---------------------------------------------------------------------------
# Star particles
# ---------------------------------------------------------------------------
@dataclass
class Star:
    x: float; y: float
    vx: float; vy: float
    life: float; decay: float
    size: int; color: tuple


def make_stars(cx, cy, count=30):
    stars = []
    for _ in range(count):
        a  = random.uniform(0, 2*math.pi)
        sp = random.uniform(1.0, 4.5)
        stars.append(Star(x=cx, y=cy, vx=math.cos(a)*sp, vy=math.sin(a)*sp,
                          life=1.0, decay=random.uniform(0.008,0.022),
                          size=random.randint(2,5),
                          color=random.choice([C_GOLD_BRIGHT,C_GOLD_MID,
                                               C_GOLD_SHEEN,(255,255,200),(255,200,80)])))
    return stars


def update_stars(stars):
    for s in stars:
        s.x+=s.vx; s.y+=s.vy; s.vy+=0.06; s.life-=s.decay
    stars[:] = [s for s in stars if s.life > 0]


def draw_stars(surf, stars):
    for s in stars:
        alpha = max(0, int(s.life*255))
        r,g,b = s.color
        for radius, a_mul in ((s.size+2, 0.3),(s.size, 1.0)):
            col = (r,g,b,int(alpha*a_mul))
            tmp = pygame.Surface((radius*2,radius*2), pygame.SRCALPHA)
            pygame.draw.circle(tmp, col, (radius,radius), radius)
            surf.blit(tmp, (int(s.x)-radius, int(s.y)-radius))


# ---------------------------------------------------------------------------
# Simple UI button helper
# ---------------------------------------------------------------------------
@dataclass
class Button:
    rect: pygame.Rect
    label: str
    selected: bool = False

    def is_hovered(self, mx, my) -> bool:
        return self.rect.collidepoint(mx, my)

    def draw(self, surf, font, hovered=False):
        if self.selected:
            col = C_BTN_SEL
        elif hovered:
            col = C_BTN_HOVER
        else:
            col = C_BTN_NORM
        pygame.draw.rect(surf, col, self.rect, border_radius=6)
        pygame.draw.rect(surf, C_BTN_BORDER, self.rect, 2, border_radius=6)
        txt = font.render(self.label, True, C_TEXT)
        surf.blit(txt, txt.get_rect(center=self.rect.center))


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class GameState:
    player_x: int
    player_y: int
    player_dir: int
    visited: set
    piece_positions: list        # list of (col, row) — 5 nugget pieces
    collected_pieces: set        # pieces the player has stepped on
    pitfall_positions: set
    revealed_pitfalls: set
    death_count: int
    num_pitfalls: int            # difficulty setting
    screen_state: str            # "playing" | "flash" | "piece" | "win"
    flash_timer: int
    piece_timer: int             # countdown for piece-found sequence
    piece_origin: tuple          # grid (col,row) where the piece was found
    win_angle: float
    win_stars: list
    star_spawn_timer: int


# ---------------------------------------------------------------------------
# Game setup / reset
# ---------------------------------------------------------------------------
def new_game(num_pitfalls: int) -> GameState:
    pieces, pitfalls = place_items(num_pitfalls)
    return GameState(
        player_x=START_POS[0], player_y=START_POS[1], player_dir=1,
        visited={START_POS},
        piece_positions=pieces, collected_pieces=set(),
        pitfall_positions=pitfalls, revealed_pitfalls=set(),
        death_count=0, num_pitfalls=num_pitfalls,
        screen_state="playing",
        flash_timer=0, piece_timer=0, piece_origin=(0, 0),
        win_angle=0.0, win_stars=[], star_spawn_timer=0,
    )


def reset_game(state: GameState):
    """Fresh map, same difficulty — called from win screen."""
    pieces, pitfalls = place_items(state.num_pitfalls)
    state.player_x, state.player_y, state.player_dir = START_POS[0], START_POS[1], 1
    state.visited = {START_POS}
    state.piece_positions = pieces
    state.collected_pieces = set()
    state.pitfall_positions = pitfalls
    state.revealed_pitfalls = set()
    state.death_count = 0
    state.screen_state = "playing"
    state.flash_timer = 0; state.piece_timer = 0; state.piece_origin = (0, 0)
    state.win_angle = 0.0; state.win_stars = []; state.star_spawn_timer = 0


# ---------------------------------------------------------------------------
# Game logic
# ---------------------------------------------------------------------------
def handle_pitfall(state: GameState):
    state.death_count += 1
    state.revealed_pitfalls.add((state.player_x, state.player_y))
    state.player_x, state.player_y = START_POS
    state.visited.add(START_POS)
    state.screen_state = "flash"
    state.flash_timer = FLASH_DURATION


def handle_keydown(key: int, state: GameState):
    if state.screen_state in ("win", "flash", "piece"):
        if state.screen_state == "win" and key in (pygame.K_RETURN, pygame.K_SPACE):
            reset_game(state)
        return

    dx, dy = 0, 0
    if   key == pygame.K_UP:    dy=-1; state.player_dir=0
    elif key == pygame.K_DOWN:  dy= 1; state.player_dir=1
    elif key == pygame.K_LEFT:  dx=-1; state.player_dir=2
    elif key == pygame.K_RIGHT: dx= 1; state.player_dir=3

    if dx == 0 and dy == 0:
        return

    new_x = state.player_x + dx
    new_y = state.player_y + dy
    if not (0 <= new_x < COLS and 0 <= new_y < ROWS):
        return

    state.player_x = new_x; state.player_y = new_y
    pos = (new_x, new_y)
    state.visited.add(pos)

    if pos in state.pitfall_positions:
        handle_pitfall(state)
    elif pos in state.piece_positions and pos not in state.collected_pieces:
        state.collected_pieces.add(pos)
        state.piece_origin = pos
        state.piece_timer = PIECE_DURATION  # 2 s
        state.screen_state = "piece"
        if len(state.collected_pieces) == NUM_PIECES:
            # All pieces found — trigger win
            state.win_stars = make_stars(new_x*TILE+TILE//2, HUD_H+new_y*TILE+TILE//2, 40)
            state.win_angle = 0.0
            state.screen_state = "win"


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------
def draw_tile(screen, state: GameState, col: int, row: int):
    pos  = (col, row)
    dest = (col*TILE, HUD_H + row*TILE)

    if pos not in state.visited:
        screen.blit(_rock_cache[pos], dest)
    else:
        screen.blit(_floor_cache[pos], dest)
        if pos in state.revealed_pitfalls:
            screen.blit(_pit_surf, dest)
        elif pos in state.piece_positions and pos not in state.collected_pieces:
            screen.blit(_piece_surf, dest)


def draw_player(screen, state: GameState):
    px = state.player_x * TILE; py = HUD_H + state.player_y * TILE
    cx = px + TILE//2;          cy = py + TILE//2
    d  = state.player_dir

    pygame.draw.ellipse(screen, (10,8,4), (cx-9, cy+8, 18, 6))

    boff = {0:[(-4,4),(3,4)], 1:[(-4,-6),(3,-6)], 2:[(2,-3),(2,3)], 3:[(-4,-3),(-4,3)]}
    for bx,by in boff[d]:
        pygame.draw.rect(screen, C_BOOT, (cx+bx, cy+by, 5, 4))

    pygame.draw.circle(screen, C_SHIRT,      (cx,cy), 8)
    pygame.draw.circle(screen, (40,65,110),  (cx,cy), 8, 1)

    pack_off = {0:(0,5), 1:(0,-7), 2:(6,0), 3:(-7,0)}
    px2,py2 = pack_off[d]
    pygame.draw.rect(screen, C_PACK,       (cx+px2-3, cy+py2-3, 7, 6))
    pygame.draw.rect(screen, (100,58,20),  (cx+px2-3, cy+py2-3, 7, 6), 1)

    head_off = {0:(0,-6), 1:(0,6), 2:(-6,0), 3:(6,0)}
    hx,hy = cx+head_off[d][0], cy+head_off[d][1]
    pygame.draw.circle(screen, C_SKIN,       (hx,hy), 5)
    pygame.draw.circle(screen, (180,130,80), (hx,hy), 5, 1)

    brim_off   = {0:(0,-3), 1:(0,3), 2:(-3,0), 3:(3,0)}
    crown_off  = {0:(0,-2), 1:(0,2), 2:(-2,0), 3:(2,0)}
    bx2,by2 = hx+brim_off[d][0], hy+brim_off[d][1]
    pygame.draw.ellipse(screen, C_HAT,      (bx2-6, by2-3, 12, 6))
    pygame.draw.ellipse(screen, C_HAT_BAND, (bx2-4, by2-3,  8, 6))
    kx,ky = bx2+crown_off[d][0], by2+crown_off[d][1]
    pygame.draw.circle(screen, C_HAT,      (kx,ky), 4)
    pygame.draw.circle(screen, C_HAT_BAND, (kx,ky), 4, 1)


def draw_hud(screen, state: GameState, font_hud, font_small, restart_btn: Button):
    pygame.draw.rect(screen, C_HUD_BG, (0, 0, WIN_W, HUD_H))
    pygame.draw.line(screen, C_HUD_LINE, (0, HUD_H-1), (WIN_W, HUD_H-1), 2)

    # Title
    title = font_hud.render("EXPLORER", True, C_GOLD_BRIGHT)
    screen.blit(title, (10, HUD_H//2 - title.get_height()//2))

    # Piece counter — small nugget icons (filled/empty)
    icon_r = 7
    icon_y = HUD_H // 2
    icon_x_start = 105
    for i in range(NUM_PIECES):
        ix = icon_x_start + i * (icon_r*2 + 6)
        if i < len(state.collected_pieces):
            pygame.draw.circle(screen, C_GOLD_BRIGHT, (ix, icon_y), icon_r)
            pygame.draw.circle(screen, C_GOLD_DARK,   (ix, icon_y), icon_r, 1)
        else:
            pygame.draw.circle(screen, C_HUD_BG,    (ix, icon_y), icon_r)
            pygame.draw.circle(screen, C_TEXT_DIM,  (ix, icon_y), icon_r, 1)

    # Pit counter
    pit_x = icon_x_start + NUM_PIECES*(icon_r*2+6) + 12
    pits = font_small.render(f"Pits: {state.death_count}", True, C_TEXT)
    screen.blit(pits, (pit_x, HUD_H//2 - pits.get_height()//2))

    # Restart button — no hover highlight on Android (no mouse cursor)
    if not ANDROID:
        mx, my = pygame.mouse.get_pos()
        restart_btn.draw(screen, font_small, hovered=restart_btn.is_hovered(mx, my))
    else:
        restart_btn.draw(screen, font_small, hovered=False)


def draw_flash_overlay(screen, state: GameState, font_big, font_med):
    t = state.flash_timer / FLASH_DURATION
    vign = pygame.Surface((WIN_W, WIN_H-HUD_H), pygame.SRCALPHA)
    vign.fill((*C_FLASH_RED, int(150*t)))
    screen.blit(vign, (0, HUD_H))

    if t > 0.33:
        pw, ph = 380, 110
        px = (WIN_W-pw)//2; py = (WIN_H-ph)//2
        pan = pygame.Surface((pw,ph), pygame.SRCALPHA)
        pan.fill((30,8,4,230))
        screen.blit(pan, (px,py))
        pygame.draw.rect(screen, C_PIT_WARNING, (px,py,pw,ph), 2)
        head = font_big.render("YOU FELL IN A PIT!", True, (255,80,40))
        screen.blit(head, (px+(pw-head.get_width())//2, py+14))
        sub = font_med.render(
            f"Pits fallen: {state.death_count}  —  back to the start!", True, C_TEXT)
        screen.blit(sub, (px+(pw-sub.get_width())//2, py+14+head.get_height()+8))


def _hud_icon_centre(piece_index: int) -> tuple:
    """Pixel centre of the Nth HUD piece icon (0-based)."""
    icon_r = 7
    icon_x_start = 105
    ix = icon_x_start + piece_index * (icon_r * 2 + 6)
    iy = HUD_H // 2
    return (ix, iy)


def draw_piece_banner(screen, state: GameState, font_big, font_med):
    """
    Two-second piece-found sequence:
      • Frames PIECE_DURATION→(PIECE_DURATION-PIECE_FLY): gold shard flies from
        the tile up to the matching HUD icon slot, with ease-out interpolation.
      • Simultaneously the announcement banner fades IN over ~15 frames then
        holds, then fades OUT over the last 20 frames.
    """
    t_norm  = state.piece_timer / PIECE_DURATION   # 1.0 → 0.0
    found   = len(state.collected_pieces)           # already includes this piece
    p_index = found - 1                             # 0-based index of the slot just filled

    # ── Banner ───────────────────────────────────────────────────────────────
    FADE_IN  = 15
    FADE_OUT = 20
    elapsed  = PIECE_DURATION - state.piece_timer   # frames since event (0…PIECE_DURATION)

    if elapsed < FADE_IN:
        banner_alpha = int(220 * elapsed / FADE_IN)
    elif state.piece_timer < FADE_OUT:
        banner_alpha = int(220 * state.piece_timer / FADE_OUT)
    else:
        banner_alpha = 220

    head_surf = font_big.render("NUGGET PIECE FOUND!", True, C_GOLD_BRIGHT)
    sub_txt   = (f"{found} of {NUM_PIECES} pieces collected"
                 + ("  —  find the rest!" if found < NUM_PIECES else "  —  all found!"))
    sub_surf  = font_med.render(sub_txt, True, C_TEXT)

    PAD_X, PAD_Y = 28, 16
    pw = max(head_surf.get_width(), sub_surf.get_width()) + PAD_X * 2
    ph = PAD_Y + head_surf.get_height() + 8 + sub_surf.get_height() + PAD_Y
    px = (WIN_W - pw) // 2
    py = HUD_H + (WIN_H - HUD_H - ph) // 2   # centred in the grid area

    pan = pygame.Surface((pw, ph), pygame.SRCALPHA)
    pan.fill((10, 30, 8, banner_alpha))
    screen.blit(pan, (px, py))
    border_col = (*C_GOLD_MID, banner_alpha)
    pygame.draw.rect(screen, border_col, (px, py, pw, ph), 2, border_radius=6)

    # Text (respect alpha by drawing onto an alpha surface)
    for surf, ty in (
        (head_surf, py + PAD_Y),
        (sub_surf,  py + PAD_Y + head_surf.get_height() + 8),
    ):
        tmp = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        tmp.blit(surf, (0, 0))
        tmp.set_alpha(banner_alpha)
        screen.blit(tmp, (px + (pw - surf.get_width()) // 2, ty))

    # ── Flying piece icon ────────────────────────────────────────────────────
    # fly_t goes 0→1 over the first PIECE_FLY frames, then stays at 1
    fly_frames_elapsed = min(elapsed, PIECE_FLY)
    fly_t_raw = fly_frames_elapsed / PIECE_FLY        # linear 0→1
    fly_t     = 1 - (1 - fly_t_raw) ** 3             # ease-out cubic

    # Start: centre of the tile the piece was on
    col, row = state.piece_origin
    sx = col * TILE + TILE // 2
    sy = HUD_H + row * TILE + TILE // 2

    # End: the HUD icon for this piece slot
    ex, ey = _hud_icon_centre(p_index)

    fx = sx + (ex - sx) * fly_t
    fy = sy + (ey - sy) * fly_t

    # Icon: small gold shard, shrinks from 14px radius to 7px (icon_r) as it flies
    icon_r_start, icon_r_end = 14, 7
    icon_r = int(icon_r_start + (icon_r_end - icon_r_start) * fly_t)

    # Glow ring behind it
    glow_r = icon_r + 4
    glow_surf = pygame.Surface((glow_r*2, glow_r*2), pygame.SRCALPHA)
    pygame.draw.circle(glow_surf, (*C_GOLD_BRIGHT, 80), (glow_r, glow_r), glow_r)
    screen.blit(glow_surf, (int(fx) - glow_r, int(fy) - glow_r))

    # Shard polygon (same shape as the tile icon)
    pts_fly = []
    for i in range(7):
        a = 2 * math.pi * i / 7 + 0.2
        r = icon_r if i % 2 == 0 else int(icon_r * 0.55)
        pts_fly.append((int(fx) + int(r * math.cos(a)),
                        int(fy) + int(r * math.sin(a))))
    pygame.draw.polygon(screen, C_GOLD_MID,    pts_fly)
    pygame.draw.polygon(screen, C_GOLD_BRIGHT, pts_fly, 2)


def draw_win_screen(screen, state: GameState, font_big, font_med, font_small):
    ov = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    ov.fill((8,6,2,220))
    screen.blit(ov, (0,0))

    for y in (60, WIN_H-60):
        pygame.draw.line(screen, C_GOLD_MID, (40,y), (WIN_W-40,y), 1)

    title = font_big.render("NUGGET RESTORED!", True, C_GOLD_BRIGHT)
    screen.blit(title, ((WIN_W-title.get_width())//2, 72))

    nugget_cx = WIN_W//2; nugget_cy = WIN_H//2 - 20
    if _nugget_sprite is not None:
        base_size = 120
        pulse = base_size + 15*math.sin(state.win_angle*2.5)
        scale = pulse / max(_nugget_sprite.get_width(), _nugget_sprite.get_height())
        scaled = pygame.transform.rotozoom(_nugget_sprite, 0, scale)
        screen.blit(scaled, scaled.get_rect(center=(nugget_cx, nugget_cy)))
    else:
        draw_gold_nugget(screen, nugget_cx, nugget_cy, 42, state.win_angle)

    stat_txt = ("Flawless run — not a single pit!" if state.death_count == 0
                else f"Fell into {state.death_count} pit(s) along the way.")
    stat = font_med.render(stat_txt, True, C_TEXT)
    screen.blit(stat, ((WIN_W-stat.get_width())//2, nugget_cy+68))

    # Restart prompt — button on Android, text hint on desktop
    if ANDROID:
        btn_r = pygame.Rect((WIN_W-200)//2, WIN_H-90, 200, 44)
        pygame.draw.rect(screen, C_BTN_NORM, btn_r, border_radius=8)
        pygame.draw.rect(screen, C_BTN_BORDER, btn_r, 2, border_radius=8)
        lbl = font_med.render("PLAY AGAIN", True, C_TEXT)
        screen.blit(lbl, lbl.get_rect(center=btn_r.center))
    else:
        prompt = font_small.render("SPACE or ENTER  —  new map", True, C_TEXT_DIM)
        screen.blit(prompt, ((WIN_W-prompt.get_width())//2, WIN_H-72))

    draw_stars(screen, state.win_stars)


def draw_dpad(screen, font_big):
    """Draw the on-screen D-pad in the zone below the grid (Android only)."""
    zone = pygame.Rect(0, WIN_H, WIN_W, DPAD_H)
    pygame.draw.rect(screen, C_HUD_BG, zone)
    pygame.draw.line(screen, C_HUD_LINE, (0, WIN_H), (WIN_W, WIN_H), 2)

    for key, rect in DPAD_RECTS.items():
        pygame.draw.rect(screen, C_BTN_NORM, rect, border_radius=8)
        pygame.draw.rect(screen, C_BTN_BORDER, rect, 2, border_radius=8)
        lbl = font_big.render(DPAD_LABELS[key], True, C_TEXT)
        screen.blit(lbl, lbl.get_rect(center=rect.center))


# ---------------------------------------------------------------------------
# Menu / title screen
# ---------------------------------------------------------------------------
def draw_menu(screen, fonts, diff_buttons: list, start_btn: Button,
              quit_btn: Button, nugget_angle: float):
    screen.fill(C_BG)

    font_title, font_body, font_btn, font_small = fonts

    # Decorative lines
    for y in (70, WIN_H-55):
        pygame.draw.line(screen, C_GOLD_MID, (30,y), (WIN_W-30,y), 1)

    # Title
    title = font_title.render("EXPLORER", True, C_GOLD_BRIGHT)
    screen.blit(title, ((WIN_W-title.get_width())//2, 14))

    sub = font_small.render("The Lost Gold Nugget", True, C_GOLD_MID)
    screen.blit(sub, ((WIN_W-sub.get_width())//2, 14+title.get_height()+4))

    # Pulsing nugget
    if _nugget_sprite is not None:
        pulse = 72 + 8*math.sin(nugget_angle*2.5)
        scale = pulse / max(_nugget_sprite.get_width(), _nugget_sprite.get_height())
        img = pygame.transform.rotozoom(_nugget_sprite, 0, scale)
        screen.blit(img, img.get_rect(center=(WIN_W//2, 210)))
    else:
        draw_gold_nugget(screen, WIN_W//2, 210, 40, nugget_angle)

    # Story text
    lines = [
        "Use the arrow keys to move the explorer,",
        "search for the five pieces of the famed",
        "lost gold nugget. But beware of pitfalls!",
    ]
    ty = 270
    for line in lines:
        t = font_body.render(line, True, C_TEXT)
        screen.blit(t, ((WIN_W-t.get_width())//2, ty))
        ty += t.get_height() + 4

    # Difficulty label
    dlbl = font_body.render("Select Difficulty:", True, C_TEXT_DIM)
    screen.blit(dlbl, ((WIN_W-dlbl.get_width())//2, ty+14))

    # Difficulty buttons
    if not ANDROID:
        mx, my = pygame.mouse.get_pos()
        for btn in diff_buttons:
            btn.draw(screen, font_btn, hovered=(not btn.selected and btn.is_hovered(mx,my)))
        start_btn.draw(screen, font_btn, hovered=start_btn.is_hovered(mx,my))
        quit_btn.draw(screen, font_btn, hovered=quit_btn.is_hovered(mx,my))
    else:
        for btn in diff_buttons:
            btn.draw(screen, font_btn, hovered=False)
        start_btn.draw(screen, font_btn, hovered=False)
        quit_btn.draw(screen, font_btn, hovered=False)


# ---------------------------------------------------------------------------
# Master render (in-game)
# ---------------------------------------------------------------------------
def render(screen, state: GameState, font_hud, font_big, font_med,
           font_small, restart_btn: Button):
    screen.fill(C_BG)
    for row in range(ROWS):
        for col in range(COLS):
            draw_tile(screen, state, col, row)
    draw_player(screen, state)
    draw_hud(screen, state, font_hud, font_small, restart_btn)

    if state.screen_state == "flash":
        draw_flash_overlay(screen, state, font_big, font_med)
    elif state.screen_state == "piece":
        draw_piece_banner(screen, state, font_big, font_med)
    elif state.screen_state == "win":
        draw_win_screen(screen, state, font_big, font_med, font_small)

    if ANDROID:
        draw_dpad(screen, font_big)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    pygame.init()
    screen = pygame.display.set_mode((WIN_W, TOTAL_H))
    pygame.display.set_caption("Explorer — The Lost Gold Nugget")
    clock = pygame.time.Clock()

    f = _load_fonts()
    font_title = f["title"]
    font_hud   = f["hud"]
    font_big   = f["big"]
    font_med   = f["med"]
    font_small = f["small"]
    font_body  = f["body"]
    font_btn   = f["btn"]

    build_tile_cache()

    # ---- Menu buttons ----
    btn_w, btn_h = 130, 36
    diff_names = list(DIFFICULTY.keys())
    total_diff_w = len(diff_names)*(btn_w+14) - 14
    diff_x0 = (WIN_W - total_diff_w)//2
    diff_y   = 398
    diff_buttons = [
        Button(pygame.Rect(diff_x0 + i*(btn_w+14), diff_y, btn_w, btn_h),
               label=f"{n}  ({DIFFICULTY[n]})",
               selected=(n == "Easy"))
        for i, n in enumerate(diff_names)
    ]
    selected_diff = "Easy"

    start_btn   = Button(pygame.Rect((WIN_W-120)//2 - 70, WIN_H-100, 120, 40), "START")
    quit_btn    = Button(pygame.Rect((WIN_W-120)//2 + 70, WIN_H-100, 120, 40), "QUIT")
    restart_btn = Button(pygame.Rect(WIN_W-105, 7, 98, 32), "↩ Menu")

    menu_fonts = (font_title, font_body, font_btn, font_small)

    # ---- App state machine ----
    app_state  = "menu"   # "menu" | "playing"
    game_state: GameState | None = None
    nugget_angle = 0.0

    running = True
    while running:
        clock.tick(FPS)
        mx, my = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                # Android back button / desktop Escape
                if event.key == pygame.K_ESCAPE:
                    if app_state == "playing":
                        app_state = "menu"
                        game_state = None
                    else:
                        running = False
                    continue

                if app_state == "playing" and game_state:
                    handle_keydown(event.key, game_state)

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:

                if app_state == "menu":
                    # Difficulty selection
                    for btn in diff_buttons:
                        if btn.is_hovered(mx, my):
                            selected_diff = btn.label.split()[0]
                            for b in diff_buttons:
                                b.selected = (b == btn)

                    if start_btn.is_hovered(mx, my):
                        num_pits = DIFFICULTY[selected_diff]
                        game_state = new_game(num_pits)
                        app_state = "playing"

                    if quit_btn.is_hovered(mx, my):
                        running = False

                elif app_state == "playing" and game_state:
                    # D-pad touch (Android) — check before other buttons
                    if ANDROID:
                        dpad_handled = False
                        for key, rect in DPAD_RECTS.items():
                            if rect.collidepoint(mx, my):
                                handle_keydown(key, game_state)
                                dpad_handled = True
                                break
                        if dpad_handled:
                            continue

                    # Restart → back to menu
                    if restart_btn.is_hovered(mx, my):
                        app_state = "menu"
                        game_state = None
                    # Win screen new-map click
                    elif game_state.screen_state == "win":
                        if (WIN_W//4 < mx < 3*WIN_W//4 and
                                WIN_H-90 < my < WIN_H-50):
                            reset_game(game_state)

        # ---- Updates ----
        nugget_angle += 0.025

        if app_state == "playing" and game_state:
            gs = game_state
            if gs.screen_state == "flash":
                gs.flash_timer -= 1
                if gs.flash_timer <= 0:
                    gs.screen_state = "playing"

            elif gs.screen_state == "piece":
                gs.piece_timer -= 1
                if gs.piece_timer <= 0:
                    gs.screen_state = "playing"
                    gs.piece_origin = (0, 0)

            elif gs.screen_state == "win":
                gs.win_angle += 0.03
                update_stars(gs.win_stars)
                gs.star_spawn_timer -= 1
                if gs.star_spawn_timer <= 0:
                    # Keep star spawns within the grid area, not D-pad zone
                    gs.win_stars += make_stars(WIN_W//2, HUD_H + (WIN_H - HUD_H)//2, 8)
                    gs.star_spawn_timer = 30

        # ---- Draw ----
        if app_state == "menu":
            draw_menu(screen, menu_fonts, diff_buttons,
                      start_btn, quit_btn, nugget_angle)
        else:
            render(screen, game_state, font_hud, font_big, font_med,
                   font_small, restart_btn)

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
