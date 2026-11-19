"""DEAD AIR: The Thirteenth Frequency.
A self-contained Pygame / Pygbag-compatible Haunted Maze AI game.

The game intentionally uses only pygame and the Python standard library.
"""
import asyncio
import heapq
import math
import random
import time
from collections import deque

import pygame

WIDTH, HEIGHT = 1280, 800
ROWS = COLS = 15
TILE = 42
OX, OY = 58, 104
PANEL_X = 738
FPS = 60

NAVY = (16, 21, 36)
PATH = (37, 44, 69)
WALL = (94, 109, 153)
CYAN = (103, 232, 249)
CORAL = (255, 109, 121)
AMBER = (255, 200, 87)
VIOLET = (182, 140, 255)
MINT = (135, 242, 192)
WHITE = (228, 237, 251)
MUTED = (147, 163, 196)
BLACK = (11, 14, 25)

# Row/column coordinates are authoritative. A direction is (dr, dc).
DIRS = {"UP": (-1, 0), "RIGHT": (0, 1), "DOWN": (1, 0), "LEFT": (0, -1)}
OPPOSITE = {"UP": "DOWN", "DOWN": "UP", "LEFT": "RIGHT", "RIGHT": "LEFT"}
KEY_DIR = {pygame.K_UP: "UP", pygame.K_w: "UP", pygame.K_RIGHT: "RIGHT", pygame.K_d: "RIGHT",
           pygame.K_DOWN: "DOWN", pygame.K_s: "DOWN", pygame.K_LEFT: "LEFT", pygame.K_a: "LEFT"}
DEFAULT_PROBS = {"shard": 4, "recharge": 6, "feedback": 8, "snare": 7}
PROB_LABELS = {"shard": "Signal Shards", "recharge": "Recharge Cells", "feedback": "Feedback Puddles", "snare": "Static Snares"}


def center(cell):
    r, c = cell
    return (OX + c * TILE + TILE // 2, OY + r * TILE + TILE // 2)


def draw_text(surface, font, message, xy, color=WHITE):
    surface.blit(font.render(str(message), True, color), xy)


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


class MazeGenerator:
    """Iterative DFS recursive backtracking, reciprocal walls, and adjacency graph."""
    def __init__(self, seed):
        self.seed = seed
        self.rng = random.Random(seed)
        self.walls = {(r, c): {d: True for d in DIRS} for r in range(ROWS) for c in range(COLS)}
        visited = {(0, 0)}
        stack = [(0, 0)]
        while stack:
            r, c = stack[-1]
            choices = [(d, (r + dr, c + dc)) for d, (dr, dc) in DIRS.items()
                       if 0 <= r + dr < ROWS and 0 <= c + dc < COLS and (r + dr, c + dc) not in visited]
            if choices:
                d, nxt = self.rng.choice(choices)
                self.walls[(r, c)][d] = False
                self.walls[nxt][OPPOSITE[d]] = False
                visited.add(nxt)
                stack.append(nxt)
            else:
                stack.pop()
        self.graph = {pos: [((pos[0] + dr, pos[1] + dc), d)
                            for d, (dr, dc) in DIRS.items() if not directions_wall[d]]
                      for pos, directions_wall in self.walls.items()}
        assert len(self.distances((0, 0))) == ROWS * COLS, "Maze must be fully connected"

    def neighbors(self, pos):
        return [n for n, _ in self.graph[pos]]

    def direction(self, a, b):
        for n, direction in self.graph[a]:
            if n == b:
                return direction
        return None

    def distances(self, start):
        result = {start: 0}
        q = deque([start])
        while q:
            u = q.popleft()
            for v in self.neighbors(u):
                if v not in result:
                    result[v] = result[u] + 1
                    q.append(v)
        return result

    def line_of_sight(self, a, b):
        if a[0] != b[0] and a[1] != b[1]:
            return False
        if a == b:
            return True
        step_r = (b[0] > a[0]) - (b[0] < a[0])
        step_c = (b[1] > a[1]) - (b[1] < a[1])
        current = a
        while current != b:
            nxt = (current[0] + step_r, current[1] + step_c)
            if nxt not in self.neighbors(current):
                return False
            current = nxt
        return True


class AStarPathfinder:
    """Shared A* implementation, with path reconstruction and node-count telemetry."""
    def __init__(self, maze):
        self.maze = maze

    def find(self, start, target):
        if start not in self.maze.graph or target not in self.maze.graph:
            return [], 0
        queue = [(manhattan(start, target), 0, start)]
        best = {start: 0}
        parent = {}
        explored = 0
        while queue:
            f, g, current = heapq.heappop(queue)
            if g != best.get(current):
                continue
            explored += 1
            if current == target:
                path = [current]
                while current in parent:
                    current = parent[current]
                    path.append(current)
                path.reverse()
                assert all(b in self.maze.neighbors(a) for a, b in zip(path, path[1:]))
                return path, explored
            for nxt in self.maze.neighbors(current):
                candidate_g = g + 1
                if candidate_g < best.get(nxt, math.inf):
                    best[nxt] = candidate_g
                    parent[nxt] = current
                    heapq.heappush(queue, (candidate_g + manhattan(nxt, target), candidate_g, nxt))
        return [], explored


class SpawnManager:
    """Independent object rolls, no overlaps, safe spawn zone, minimum 5 shards."""
    def __init__(self, maze, probabilities):
        self.maze = maze
        self.probabilities = probabilities.copy()
        self.rng = maze.rng

    def generate(self):
        start, exit_cell = (0, 0), (14, 14)
        distances = self.maze.distances(start)
        safe = {cell for cell, d in distances.items() if d <= 2}
        reserved = safe | {exit_cell}
        boss_choices = [cell for cell in distances if distances[cell] >= 12 and cell not in reserved]
        boss = self.rng.choice(boss_choices)
        reserved.add(boss)
        hush_choices = [cell for cell in distances if distances[cell] >= 7 and cell not in reserved]
        hush = self.rng.sample(hush_choices, 2)
        reserved.update(hush)
        free = [cell for cell in distances if cell not in reserved]
        self.rng.shuffle(free)
        objects = {name: set() for name in self.probabilities}
        for cell in free:
            for name in self.probabilities:
                if self.rng.random() < self.probabilities[name] / 100.0:
                    if name == "shard" and len(objects[name]) >= 12:
                        break
                    if name in ("feedback", "snare") and len(objects["feedback"] | objects["snare"]) >= 32:
                        break
                    objects[name].add(cell)
                    break
        if len(objects["shard"]) < 5:
            occupied = set().union(*objects.values())
            candidates = [cell for cell in free if cell not in occupied]
            self.rng.shuffle(candidates)
            objects["shard"].update(candidates[:5 - len(objects["shard"])])
        assert len(objects["shard"]) >= 5
        assert not any(a & b for i, a in enumerate(objects.values()) for b in list(objects.values())[i + 1:])
        return objects, boss, hush


class MarkovPredictor:
    """Laplace-smoothed first-order and second-order Markov models."""
    def __init__(self):
        self.first = {d: {k: 1 for k in DIRS} for d in DIRS}
        self.second = {(a, b): {k: 1 for k in DIRS} for a in DIRS for b in DIRS}
        self.second_observations = {(a, b): 0 for a in DIRS for b in DIRS}
        self.history = []
        self.transitions = 0
        self.hits = 0
        self.attempts = 0
        self.recent = deque(maxlen=30)

    def probabilities(self, previous=None, second_last=None):
        if previous is None:
            previous = self.history[-1] if self.history else None
        if second_last is None and len(self.history) >= 2 and previous == self.history[-1]:
            second_last = self.history[-2]
        if previous not in DIRS:
            return {d: 0.25 for d in DIRS}, "prior"
        if second_last in DIRS and self.second_observations[(second_last, previous)] >= 5:
            row = self.second[(second_last, previous)]
            model = "2-gram"
        else:
            row = self.first[previous]
            model = "1st-order"
        total = sum(row.values())
        return {d: row[d] / total for d in DIRS}, model

    def predict(self):
        probs, model = self.probabilities()
        best = max(DIRS, key=lambda d: probs[d])
        return best, probs[best], probs, model

    def record(self, direction):
        # Accuracy is evaluated BEFORE the model receives the new move.
        if self.history:
            guess, _, _, _ = self.predict()
            hit = int(guess == direction)
            self.attempts += 1
            self.hits += hit
            self.recent.append(hit)
            prev = self.history[-1]
            self.first[prev][direction] += 1
            self.transitions += 1
        if len(self.history) >= 2:
            key = (self.history[-2], self.history[-1])
            self.second[key][direction] += 1
            self.second_observations[key] += 1
        self.history.append(direction)

    def accuracy(self):
        recent = 100 * sum(self.recent) / len(self.recent) if self.recent else 0
        lifetime = 100 * self.hits / self.attempts if self.attempts else 0
        return recent, lifetime


class Player:
    def __init__(self):
        self.pos = (0, 0)
        self.hp = 100
        self.shards = 0
        self.charges = 0
        self.score = 0
        self.move_timer = 0.0
        self.slow_until = 0.0
        self.damage_until = {"feedback": 0, "snare": 0, "hush": 0, "boss": 0}
        self.hazard_cells_last = set()

    def damage(self, amount, source, now, cooldown):
        if now < self.damage_until[source]:
            return False
        self.damage_until[source] = now + cooldown
        self.hp = max(0, self.hp - amount)
        return True


class Hushling:
    def __init__(self, name, pos, pathfinder, rng):
        self.name = name
        self.pos = pos
        self.state = "PATROL"
        self.target = pos
        self.last_seen = None
        self.path = [pos]
        self.nodes = 0
        self.pathfinder = pathfinder
        self.rng = rng
        self.move_timer = 0.0
        self.plan_timer = 0.0
        self.lost_timer = 0.0
        self.search_timer = 0.0
        self.stunned_until = 0.0

    def stun(self, now):
        self.state = "STUNNED"
        self.stunned_until = now + 2.0
        self.move_timer = 0

    def plan(self, target):
        self.target = target
        self.path, self.nodes = self.pathfinder.find(self.pos, target)

    def waypoint(self):
        nearby = {self.pos}
        frontier = {self.pos}
        for _ in range(4):
            frontier = {n for pos in frontier for n in self.pathfinder.maze.neighbors(pos)} - nearby
            nearby |= frontier
        return self.rng.choice(sorted(nearby))

    def update(self, dt, now, player):
        if self.state == "STUNNED":
            if now < self.stunned_until:
                return
            self.state = "PATROL"
            self.plan(self.waypoint())
        maze = self.pathfinder.maze
        dist = manhattan(self.pos, player.pos)
        visible = dist <= 5 and maze.line_of_sight(self.pos, player.pos)
        if visible:
            self.last_seen = player.pos
            self.lost_timer = 0.0
            if self.state != "CHASE":
                self.state = "CHASE"
                self.plan(player.pos)
        elif self.state == "CHASE":
            if dist > 5:
                self.lost_timer += dt
                if self.lost_timer >= 1.5:
                    self.state = "SEARCH"
                    self.search_timer = 0.0
                    self.plan(self.last_seen or player.pos)
        elif self.state == "SEARCH":
            self.search_timer += dt
            if self.search_timer >= 3.0:
                self.state = "PATROL"
                self.plan(self.waypoint())
        if self.state == "PATROL" and (self.pos == self.target or not self.path):
            self.plan(self.waypoint())
        self.plan_timer -= dt
        if self.plan_timer <= 0:
            self.plan_timer = 0.5
            if self.state == "CHASE":
                self.plan(player.pos)
            elif self.state == "SEARCH" and self.last_seen is not None and self.target != self.last_seen:
                self.plan(self.last_seen)
        self.move_timer += dt
        speed = 0.35 if self.state == "CHASE" else 0.55
        if self.move_timer >= speed:
            self.move_timer -= speed
            if len(self.path) > 1 and self.path[0] == self.pos:
                self.pos = self.path[1]
                self.path.pop(0)
            elif self.pos != self.target:
                self.plan(self.target)


class ListenerBoss:
    """Predict 3 steps, rank up to 5 interception cells, navigate using A*."""
    def __init__(self, pos, finder, predictor):
        self.pos = pos
        self.finder = finder
        self.predictor = predictor
        self.state = "INTERCEPT"
        self.target = pos
        self.path = [pos]
        self.nodes = 0
        self.candidates = []
        self.predicted_dir = "UP"
        self.predicted_prob = 0.25
        self.model = "prior"
        self.move_timer = 0.0
        self.plan_timer = 0.0

    def project(self, origin):
        maze = self.finder.maze
        start_context = self.predictor.history[-2:]
        # Each hypothesis is (position, chance, steps, last directions, previous cell).
        branches = [(origin, 1.0, 0, start_context, None)]
        candidates = {}
        for depth in range(1, 4):
            expanded = []
            for pos, likelihood, _, context, previous_cell in branches:
                last = context[-1] if context else None
                earlier = context[-2] if len(context) >= 2 else None
                distribution, _ = self.predictor.probabilities(last, earlier)
                moves = [(nxt, direction) for nxt, direction in maze.graph[pos]]
                options = [(nxt, d) for nxt, d in moves if nxt != previous_cell]
                if options:
                    moves = options
                for nxt, direction in moves:
                    chance = likelihood * distribution[direction]
                    new_context = (context + [direction])[-2:]
                    expanded.append((nxt, chance, depth, new_context, pos))
                    if nxt not in candidates or chance > candidates[nxt][0]:
                        candidates[nxt] = (chance, depth)
            branches = sorted(expanded, key=lambda item: -item[1])[:25]
        ranked = sorted(candidates.items(), key=lambda item: -item[1][0])[:5]
        return [(cell, prob, depth) for cell, (prob, depth) in ranked]

    def replan(self, player_pos):
        self.predicted_dir, self.predicted_prob, _, self.model = self.predictor.predict()
        projected = self.project(player_pos)
        choices = []
        for cell, probability, steps in projected:
            path, expanded = self.finder.find(self.pos, cell)
            if not path:
                continue
            distance = len(path) - 1
            utility = 100 * probability - 4 * distance - 2 * steps
            feasible = 0.48 * distance <= 0.22 * steps + 2.0
            choices.append({"cell": cell, "prob": probability, "steps": steps,
                            "distance": distance, "utility": utility,
                            "feasible": feasible, "path": path, "nodes": expanded})
        choices.sort(key=lambda c: c["utility"], reverse=True)
        self.candidates = choices
        feasible = [c for c in choices if c["feasible"]]
        if feasible:
            selected = feasible[0]
        elif choices:
            selected = choices[0]
        else:
            path, expanded = self.finder.find(self.pos, player_pos)
            selected = {"cell": player_pos, "path": path, "nodes": expanded}
        self.target = selected["cell"]
        self.path = selected["path"]
        self.nodes = selected["nodes"]
        self.state = "INTERCEPT" if projected else "TRACK"

    def update(self, dt, player_pos):
        self.plan_timer -= dt
        if self.plan_timer <= 0:
            self.plan_timer = 0.75
            self.replan(player_pos)
        self.move_timer += dt
        if self.move_timer >= 0.48:
            self.move_timer -= 0.48
            if len(self.path) > 1 and self.path[0] == self.pos:
                self.pos = self.path[1]
                self.path.pop(0)
            elif self.pos != self.target:
                self.replan(player_pos)


class Game:
    def __init__(self, screen):
        self.screen = screen
        self.font = pygame.font.SysFont("consolas", 19)
        self.small = pygame.font.SysFont("consolas", 15)
        self.tiny = pygame.font.SysFont("consolas", 13)
        self.large = pygame.font.SysFont("consolas", 48, bold=True)
        self.mid = pygame.font.SysFont("consolas", 27, bold=True)
        self.probs = DEFAULT_PROBS.copy()
        self.selected = 0
        self.scene = "MENU"
        self.debug = False
        self.paused = False
        self.running = True
        self.clock_time = 0.0
        self.notice = ""
        self.notice_end = 0.0
        self.emp_until = 0.0
        self.final_prediction = ""
        self.seed = 0
        self.mixer_rects = []

    def new_game(self):
        self.seed = random.randrange(1, 99999999)
        self.maze = MazeGenerator(self.seed)
        self.finder = AStarPathfinder(self.maze)
        objects, boss_cell, hush_cells = SpawnManager(self.maze, self.probs).generate()
        self.objects = objects
        self.player = Player()
        self.predictor = MarkovPredictor()
        self.hushlings = [Hushling("A", hush_cells[0], self.finder, self.maze.rng),
                          Hushling("B", hush_cells[1], self.finder, self.maze.rng)]
        self.boss = ListenerBoss(boss_cell, self.finder, self.predictor)
        self.boss.replan(self.player.pos)
        self.clock_time = 0.0
        self.paused = False
        self.scene = "PLAY"
        self.notice = "Find 5 Signal Shards. Restore the transmitter!"
        self.notice_end = 4.0
        self.emp_until = 0.0
        self.final_prediction = ""
        self.debug = False

    def message(self, msg, duration=2.3):
        self.notice = msg
        self.notice_end = self.clock_time + duration

    def adjust_prob(self, index, change):
        key = list(self.probs)[index]
        minimum, maximum = (2, 10) if key == "shard" else (0, 15)
        self.probs[key] = max(minimum, min(maximum, self.probs[key] + change))

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.scene == "MIXER":
                for i, rect in enumerate(self.mixer_rects):
                    if rect.collidepoint(event.pos):
                        self.selected = i
                        key = list(self.probs)[i]
                        low, high = (2, 10) if key == "shard" else (0, 15)
                        ratio = min(1, max(0, (event.pos[0] - rect.x) / rect.w))
                        self.probs[key] = round(low + ratio * (high - low))
        if event.type != pygame.KEYDOWN:
            return
        key = event.key
        if self.scene == "MENU":
            if key in (pygame.K_RETURN, pygame.K_SPACE):
                self.new_game()
            elif key == pygame.K_m:
                self.scene = "MIXER"
            elif key == pygame.K_h:
                self.scene = "HELP"
            elif key in (pygame.K_q, pygame.K_ESCAPE):
                self.running = False
        elif self.scene == "MIXER":
            if key in (pygame.K_UP, pygame.K_w):
                self.selected = (self.selected - 1) % 4
            elif key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected + 1) % 4
            elif key in (pygame.K_LEFT, pygame.K_a):
                self.adjust_prob(self.selected, -1)
            elif key in (pygame.K_RIGHT, pygame.K_d):
                self.adjust_prob(self.selected, 1)
            elif key == pygame.K_RETURN:
                self.new_game()
            elif key in (pygame.K_ESCAPE, pygame.K_m):
                self.scene = "MENU"
        elif self.scene == "HELP":
            if key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_m):
                self.scene = "MENU"
        elif self.scene == "PLAY":
            if key == pygame.K_F1:
                self.debug = not self.debug
            elif key == pygame.K_p:
                self.paused = not self.paused
            elif key in (pygame.K_ESCAPE, pygame.K_q):
                self.scene = "MENU"
            elif not self.paused and key == pygame.K_e:
                self.emp()
            elif not self.paused and key == pygame.K_RETURN and self.player.pos == (14, 14):
                self.check_win()
            elif not self.paused and key in KEY_DIR:
                self.try_move(KEY_DIR[key])
        elif self.scene in ("WIN", "LOSE"):
            if key == pygame.K_r:
                self.new_game()
            elif key in (pygame.K_m, pygame.K_ESCAPE):
                self.scene = "MENU"
            elif key == pygame.K_q:
                self.running = False

    def try_move(self, direction):
        player = self.player
        interval = 0.4 if self.clock_time < player.slow_until else 0.22
        if player.move_timer < interval:
            return
        dr, dc = DIRS[direction]
        nxt = (player.pos[0] + dr, player.pos[1] + dc)
        if nxt not in self.maze.neighbors(player.pos):
            return
        player.pos = nxt
        player.move_timer = 0.0
        self.predictor.record(direction)
        self.resolve_pickups()
        if self.scene == "PLAY":
            self.resolve_contacts()
            if self.scene == "PLAY" and player.pos == (14, 14):
                self.check_win()

    def emp(self):
        if self.player.charges <= 0:
            self.message("No EMP charges! Find a Recharge Cell at full HP.")
            return
        self.player.charges -= 1
        self.emp_until = self.clock_time + 2.0
        distances = self.maze.distances(self.player.pos)
        affected = 0
        for ghost in self.hushlings:
            if distances[ghost.pos] <= 2:
                ghost.stun(self.clock_time)
                affected += 1
        self.message("EMP fired: {} Hushling(s) stunned. Boss immune.".format(affected))

    def resolve_pickups(self):
        pos = self.player.pos
        if pos in self.objects["shard"]:
            self.objects["shard"].remove(pos)
            self.player.shards += 1
            self.player.score += 100
            self.message("Signal Shard recovered! {}/5".format(min(self.player.shards, 5)))
        if pos in self.objects["recharge"]:
            self.objects["recharge"].remove(pos)
            if self.player.hp < 100:
                self.player.hp = min(100, self.player.hp + 20)
                self.message("Battery restored 20 HP.")
            elif self.player.charges < 3:
                self.player.charges += 1
                self.message("EMP charge stored! Press E.")
            else:
                self.message("Battery found, EMP inventory already full.")

    def resolve_contacts(self):
        p, now = self.player, self.clock_time
        if p.pos in self.objects["feedback"] and p.damage(18, "feedback", now, 2.0):
            self.message("FEEDBACK! -18 HP")
        if p.pos in self.objects["snare"] and p.damage(8, "snare", now, 1.5):
            p.slow_until = now + 1.5
            self.message("STATIC SNARE! -8 HP, movement slowed")
        if any(h.pos == p.pos and h.state != "STUNNED" for h in self.hushlings):
            if p.damage(12, "hush", now, 1.5):
                self.message("A Hushling caught you! -12 HP")
        if self.boss.pos == p.pos and p.damage(30, "boss", now, 2.0):
            self.message("THE LISTENER intercepted you! -30 HP")
        if p.hp <= 0:
            self.final_prediction = "{} ({:.0%})".format(self.boss.predicted_dir, self.boss.predicted_prob)
            self.scene = "LOSE"

    def check_win(self):
        if self.player.shards >= 5 and self.player.hp > 0:
            self.player.score += 500 + 5 * self.player.hp
            self.scene = "WIN"
        else:
            self.message("TRANSMITTER LOCKED: {} more shards needed".format(max(0, 5 - self.player.shards)))

    def update(self, dt, held):
        if self.scene != "PLAY" or self.paused:
            return
        dt = min(dt, 0.08)
        self.clock_time += dt
        self.player.move_timer += dt
        interval = 0.4 if self.clock_time < self.player.slow_until else 0.22
        if self.player.move_timer >= interval:
            for key in (pygame.K_UP, pygame.K_RIGHT, pygame.K_DOWN, pygame.K_LEFT,
                        pygame.K_w, pygame.K_d, pygame.K_s, pygame.K_a):
                if held[key]:
                    self.try_move(KEY_DIR[key])
                    break
        for ghost in self.hushlings:
            ghost.update(dt, self.clock_time, self.player)
        self.boss.update(dt, self.player.pos)
        self.resolve_contacts()

    def draw_maze(self):
        pygame.draw.rect(self.screen, PATH, (OX, OY, COLS * TILE, ROWS * TILE))
        for (r, c), walls in self.maze.walls.items():
            x, y = OX + c * TILE, OY + r * TILE
            if walls["UP"]:
                pygame.draw.line(self.screen, WALL, (x, y), (x + TILE, y), 3)
            if walls["LEFT"]:
                pygame.draw.line(self.screen, WALL, (x, y), (x, y + TILE), 3)
            if r == ROWS - 1 and walls["DOWN"]:
                pygame.draw.line(self.screen, WALL, (x, y + TILE), (x + TILE, y + TILE), 3)
            if c == COLS - 1 and walls["RIGHT"]:
                pygame.draw.line(self.screen, WALL, (x + TILE, y), (x + TILE, y + TILE), 3)

    def draw_objects(self):
        for pos in self.objects["feedback"]:
            x, y = center(pos)
            pygame.draw.ellipse(self.screen, (157, 57, 117), (x - 14, y - 9, 28, 18))
            pygame.draw.arc(self.screen, CORAL, (x - 10, y - 9, 20, 18), 0, math.pi, 2)
        for pos in self.objects["snare"]:
            x, y = center(pos)
            pygame.draw.lines(self.screen, AMBER, False, [(x - 12, y + 8), (x - 6, y - 8), (x, y + 6),
                                                          (x + 6, y - 8), (x + 12, y + 8)], 3)
        for pos in self.objects["shard"]:
            x, y = center(pos)
            pygame.draw.polygon(self.screen, CYAN, [(x, y - 13), (x + 10, y), (x, y + 13), (x - 10, y)])
            pygame.draw.circle(self.screen, WHITE, (x, y), 3)
        for pos in self.objects["recharge"]:
            x, y = center(pos)
            pygame.draw.rect(self.screen, MINT, (x - 10, y - 9, 20, 18), border_radius=4)
            pygame.draw.line(self.screen, NAVY, (x - 5, y), (x + 5, y), 2)
            pygame.draw.line(self.screen, NAVY, (x, y - 5), (x, y + 5), 2)
        x, y = center((14, 14))
        unlocked = self.player.shards >= 5
        pygame.draw.rect(self.screen, AMBER if unlocked else (103, 91, 80), (x - 14, y - 14, 28, 28), 3)
        pygame.draw.circle(self.screen, AMBER if unlocked else MUTED, (x, y), 7)
        x, y = center(self.player.pos)
        pygame.draw.circle(self.screen, CYAN, (x, y), 16, 2)
        pygame.draw.circle(self.screen, AMBER, (x, y), 10)
        pygame.draw.arc(self.screen, CYAN, (x - 11, y - 13, 22, 20), 0, math.pi, 3)
        for ghost in self.hushlings:
            x, y = center(ghost.pos)
            color = CYAN if ghost.state == "STUNNED" else (AMBER if ghost.state == "SEARCH" else VIOLET)
            pygame.draw.circle(self.screen, color, (x, y), 12)
            pygame.draw.circle(self.screen, WHITE, (x - 4, y - 2), 3)
            pygame.draw.circle(self.screen, WHITE, (x + 4, y - 2), 3)
            pygame.draw.arc(self.screen, color, (x - 11, y - 2, 22, 20), math.pi, 2 * math.pi, 3)
        x, y = center(self.boss.pos)
        pygame.draw.rect(self.screen, BLACK, (x - 14, y - 16, 28, 32), border_radius=3)
        pygame.draw.rect(self.screen, CORAL, (x - 14, y - 16, 28, 32), 2)
        pygame.draw.circle(self.screen, CORAL, (x, y - 2), 9, 2)
        pygame.draw.line(self.screen, CORAL, (x - 6, y + 12), (x + 8, y - 9), 3)
        if self.clock_time < self.emp_until:
            pygame.draw.circle(self.screen, CYAN, center(self.player.pos), 2 * TILE, 2)

    def draw_path(self, path, color, dotted=False):
        if len(path) < 2:
            return
        points = [center(p) for p in path]
        for i in range(len(points) - 1):
            if dotted:
                ax, ay = points[i]
                bx, by = points[i + 1]
                for k in range(1, 6):
                    t = k / 6.0
                    pygame.draw.circle(self.screen, color, (round(ax + (bx - ax) * t),
                                                            round(ay + (by - ay) * t)), 3)
            else:
                pygame.draw.line(self.screen, color, points[i], points[i + 1], 3)

    def draw_debug_world(self):
        for ghost in self.hushlings:
            self.draw_path(ghost.path, VIOLET)
            x, y = center(ghost.pos)
            draw_text(self.screen, self.tiny, ghost.state, (x - 24, y - 31), WHITE)
            if ghost.last_seen is not None:
                pygame.draw.circle(self.screen, AMBER, center(ghost.last_seen), 4, 1)
            pygame.draw.circle(self.screen, (101, 81, 131), (x, y), 5 * TILE, 1)
        self.draw_path(self.boss.path, CORAL, dotted=True)
        for i, candidate in enumerate(self.boss.candidates):
            x, y = center(candidate["cell"])
            pygame.draw.circle(self.screen, AMBER, (x, y), 14, 3 if i == 0 else 1)
            draw_text(self.screen, self.tiny, str(i + 1), (x - 4, y - 7), WHITE)
        tx, ty = center(self.boss.target)
        pygame.draw.circle(self.screen, CORAL, (tx, ty), 17, 2)

    def panel_line(self, text, y, color=WHITE, x=PANEL_X):
        draw_text(self.screen, self.small, text, (x, y), color)

    def draw_panel(self):
        x = PANEL_X
        pygame.draw.rect(self.screen, (22, 29, 49), (x - 22, 92, 514, 650), border_radius=12)
        draw_text(self.screen, self.mid, "WNVR-13  /  FIELD LOG", (x, 106), CYAN)
        pygame.draw.line(self.screen, WALL, (x, 146), (1210, 146), 1)
        self.panel_line("HP", 166)
        pygame.draw.rect(self.screen, (70, 67, 81), (x + 45, 165, 275, 17), border_radius=5)
        pygame.draw.rect(self.screen, MINT if self.player.hp > 35 else CORAL,
                         (x + 45, 165, int(275 * self.player.hp / 100), 17), border_radius=5)
        self.panel_line(str(self.player.hp) + "/100", 166, WHITE, x + 332)
        self.panel_line("SHARDS        {}/5    (+{} extra)".format(min(self.player.shards, 5), max(0, self.player.shards - 5)), 201, CYAN)
        self.panel_line("EMP CHARGES   {}/3    [E]".format(self.player.charges), 228, MINT)
        self.panel_line("TIME          {:02d}:{:02d}".format(int(self.clock_time) // 60, int(self.clock_time) % 60), 255)
        self.panel_line("SCORE         {}".format(self.player.score), 282, AMBER)
        self.panel_line("TRANSMITTER   " + ("UNLOCKED" if self.player.shards >= 5 else "LOCKED"), 309,
                        AMBER if self.player.shards >= 5 else CORAL)
        pygame.draw.line(self.screen, WALL, (x, 345), (1210, 345), 1)
        direction, probability, distribution, model = self.predictor.predict()
        draw_text(self.screen, self.font, "LISTENER FREQUENCY", (x, 363), CORAL)
        self.panel_line("Predicted: {}   {:.0%}".format(direction, probability), 393)
        self.panel_line("Model: " + model, 416, MUTED)
        self.panel_line("Confidence / radio hiss", 442, MUTED)
        pygame.draw.rect(self.screen, (70, 67, 81), (x, 465, 390, 13), border_radius=3)
        pygame.draw.rect(self.screen, CORAL, (x, 465, int(390 * probability), 13), border_radius=3)
        if self.debug:
            self.draw_debug_panel(distribution)
        else:
            self.panel_line("[F1] Show live AI telemetry", 507, CYAN)
            self.panel_line("Move: WASD / arrow keys", 544)
            self.panel_line("EMP: E  |  Pause: P", 574)
            self.panel_line("Menu: Esc or Q", 604)
            self.panel_line("CYAN shard   MINT recharge", 649, MUTED)
            self.panel_line("CORAL puddle  AMBER snare", 677, MUTED)
        if self.notice and self.clock_time < self.notice_end:
            pygame.draw.rect(self.screen, (32, 46, 66), (OX, 753, 1165, 34), border_radius=5)
            draw_text(self.screen, self.small, self.notice, (OX + 12, 762), WHITE)

    def draw_debug_panel(self, distribution):
        x = PANEL_X
        probs = "  ".join("{}:{:.0f}%".format(k[0], distribution[k] * 100) for k in DIRS)
        self.panel_line(probs, 492, CYAN)
        self.panel_line("Moves: {} | transitions: {}".format(len(self.predictor.history), self.predictor.transitions), 515)
        recent, lifetime = self.predictor.accuracy()
        self.panel_line("Accuracy: last30 {:.0f}% / all {:.0f}%".format(recent, lifetime), 538)
        self.panel_line("At: {} | last: {}".format(self.player.pos,
                        self.predictor.history[-1] if self.predictor.history else "NONE"), 561)
        self.panel_line("Boss {} -> {}  A*:{}".format(self.boss.state, self.boss.target, self.boss.nodes), 585, CORAL)
        for i, ghost in enumerate(self.hushlings):
            self.panel_line("H{} {} -> {} n:{}".format(ghost.name, ghost.state, ghost.target, ghost.nodes),
                            608 + 23 * i, VIOLET)
        self.panel_line("Candidates: P  Dboss  T  Utility", 655, AMBER)
        for i, candidate in enumerate(self.boss.candidates[:3]):
            self.panel_line("{} {} {:.0%}  {}  {}  {:.1f}{}".format(i + 1, candidate["cell"],
                            candidate["prob"], candidate["distance"], candidate["steps"],
                            candidate["utility"], "*" if candidate["feasible"] else ""),
                            676 + 19 * i, MUTED)
        self.panel_line("Seed: {}  Replan: {:.2f}s".format(self.seed, max(0, self.boss.plan_timer)), 738)
        # Compact transition matrix & settings in left border when in debug.
        draw_text(self.screen, self.tiny, "P1 U/R/D/L (Laplace counts)", (OX, 22), MUTED)
        for i, d in enumerate(DIRS):
            row = self.predictor.first[d]
            msg = "{}: {}".format(d[0], "/".join(str(row[k]) for k in DIRS))
            draw_text(self.screen, self.tiny, msg, (OX + 220 + i * 109, 22), WHITE)
        context = tuple(self.predictor.history[-2:])
        if len(context) == 2:
            draw_text(self.screen, self.tiny, "P2 context {}: {} samples".format(context,
                      self.predictor.second_observations[context]), (OX, 43), CYAN)
        draw_text(self.screen, self.tiny, "Spawn %  " + "  ".join("{}:{}".format(k[0], v)
                      for k, v in self.probs.items()), (OX + 300, 43), MUTED)

    def centered(self, font, msg, y, color=WHITE):
        surf = font.render(msg, True, color)
        self.screen.blit(surf, ((WIDTH - surf.get_width()) // 2, y))

    def draw_menu(self):
        self.centered(self.large, "DEAD AIR", 142, CYAN)
        self.centered(self.mid, "THE THIRTEENTH FREQUENCY", 216, CORAL)
        self.centered(self.font, "WNVR-13  |  12:00 AM  |  TRANSMISSION INTERRUPTED", 279, MUTED)
        for y, msg, color in [(372, "[ENTER]  PLAY", MINT), (419, "[M]  PROBABILITY MIXER", CYAN),
                               (466, "[H]  HOW TO PLAY", WHITE), (513, "[Q]  QUIT", MUTED)]:
            self.centered(self.mid, msg, y, color)
        self.centered(self.small, "Your footsteps are data. The station is listening.", 662, MUTED)
        self.centered(self.small, "A Pygame AI survival maze | Desktop + Web", 687, MUTED)

    def draw_mixer(self):
        self.centered(self.large, "PROBABILITY MIXER", 93, CYAN)
        self.centered(self.font, "Set world generation probabilities before entering the station", 170, MUTED)
        self.mixer_rects = []
        for i, (key, chance) in enumerate(self.probs.items()):
            y = 244 + i * 97
            selected = i == self.selected
            draw_text(self.screen, self.font, PROB_LABELS[key], (240, y), CYAN if selected else WHITE)
            draw_text(self.screen, self.font, "{}%".format(chance), (955, y), AMBER)
            lo, hi = (2, 10) if key == "shard" else (0, 15)
            rect = pygame.Rect(550, y + 5, 360, 23)
            self.mixer_rects.append(rect)
            pygame.draw.rect(self.screen, (55, 62, 84), rect, border_radius=8)
            amount = int((chance - lo) / (hi - lo) * rect.width)
            if amount:
                pygame.draw.rect(self.screen, CYAN if selected else VIOLET,
                                 (rect.x, rect.y, amount, rect.height), border_radius=8)
            pygame.draw.circle(self.screen, WHITE if selected else MUTED, (rect.x + amount, rect.centery), 11)
            estimate = round(215 * chance / 100, 1)
            draw_text(self.screen, self.small, "~{} per world before guarantees/caps".format(estimate), (553, y + 34), MUTED)
        self.centered(self.font, "UP/DOWN: choose   LEFT/RIGHT: adjust   Mouse: slider", 665)
        self.centered(self.font, "[ENTER] Generate maze    [ESC] Main menu", 707, MINT)

    def draw_help(self):
        self.centered(self.large, "HOW TO SURVIVE WNVR-13", 90, CYAN)
        lines = [
            "You are Kit Vale, an audio engineer trapped in a haunted radio station.",
            "Recover at least FIVE cyan Signal Shards, then reach the amber transmitter",
            "in the bottom-right corner. Get there alive to broadcast an SOS.",
            "",
            "WASD / arrows: move    E: EMP pulse    P: pause    F1: AI debug",
            "",
            "MINT BATTERY: heal 20 HP, or store an EMP charge when at full HP.",
            "CORAL PUDDLE: -18 HP   AMBER SNARE: -8 HP and a brief slowdown.",
            "VIOLET HUSHLINGS: patrol, chase, search; EMP stuns them for 2 sec.",
            "RED LISTENER: predicts your future turns and tries to intercept you.",
            "",
            "Debug mode displays A* routes, FSM states, probability predictions,",
            "interception targets, candidate utility and prediction accuracy.",
            "",
            "Tip: vary your turns to make your movement harder to predict.",
        ]
        for i, line in enumerate(lines):
            draw_text(self.screen, self.font, line, (105, 204 + 33 * i),
                      CYAN if i in (4, 11) else WHITE)
        self.centered(self.font, "[ENTER] or [ESC] return to menu", 735, MINT)

    def draw_end(self):
        winning = self.scene == "WIN"
        self.centered(self.large, "YOU ARE ON THE AIR" if winning else "SIGNAL LOST", 171,
                      MINT if winning else CORAL)
        self.centered(self.mid, "WNVR-13 " + ("TRANSMISSION RESTORED" if winning else "HAS GONE SILENT"),
                      254, WHITE)
        self.centered(self.font, "Time  {:02d}:{:02d}   |   Shards  {}   |   HP  {}".format(
                      int(self.clock_time) // 60, int(self.clock_time) % 60,
                      self.player.shards, self.player.hp), 359)
        self.centered(self.mid, "FINAL SCORE: {}".format(self.player.score), 417, AMBER)
        if not winning:
            self.centered(self.font, "Final Listener prediction: " + self.final_prediction, 479, CORAL)
        self.centered(self.font, "[R] New maze     [M] Main menu     [Q] Quit", 616, CYAN)

    def draw(self):
        self.screen.fill(NAVY)
        if self.scene == "MENU":
            self.draw_menu()
        elif self.scene == "MIXER":
            self.draw_mixer()
        elif self.scene == "HELP":
            self.draw_help()
        elif self.scene == "PLAY":
            draw_text(self.screen, self.mid, "DEAD AIR  /  WNVR-13", (OX, 67), CYAN)
            self.draw_maze()
            if self.debug:
                self.draw_debug_world()
            self.draw_objects()
            self.draw_panel()
            if self.paused:
                veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                veil.fill((5, 9, 20, 175))
                self.screen.blit(veil, (0, 0))
                self.centered(self.large, "PAUSED", 327, AMBER)
                self.centered(self.font, "Press P to resume", 393, WHITE)
        else:
            self.draw_end()
        # Decorative CRT scanlines, deliberately subtle and independent of sound.
        for y in range(0, HEIGHT, 7):
            pygame.draw.line(self.screen, (20, 25, 42), (0, y), (WIDTH, y), 1)
        pygame.display.flip()


async def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("DEAD AIR: The Thirteenth Frequency")
    game = Game(screen)
    clock = pygame.time.Clock()
    while game.running:
        dt = clock.tick(FPS) / 1000.0
        for event in pygame.event.get():
            game.handle_event(event)
        if game.running:
            game.update(dt, pygame.key.get_pressed())
            game.draw()
        await asyncio.sleep(0)  # Required for the browser's cooperative event loop.
    pygame.quit()


if __name__ == "__main__":
    asyncio.run(main())
