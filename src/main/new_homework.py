# ============================================================
# 完整修复版代码（Q1 - Q7 + Bonus）
# 遵循 PEP 8 / autopep8 --max-line-length=79 / isort 规范
# ============================================================

import json
import re
from collections import deque
from enum import Enum


# ============================================================
# Q1 机器人自检
# ============================================================

def hp_ratio(hp, max_hp):
    """血量百分比，返回 0-100 的 int。"""
    if max_hp <= 0:
        return 0
    pct = int(hp / max_hp * 100)
    return max(0, min(100, pct))


def status_report(name, robot_type, hp, max_hp, battery):
    """生成单行自检报告。"""
    hp_pct = hp_ratio(hp, max_hp)
    battery = int(max(0, min(100, battery)))

    if battery >= 60:
        bat_status = "OK"
    elif battery >= 20:
        bat_status = "WARNING"
    else:
        bat_status = "LOW"

    return (
        f"{name:<10}|{robot_type:^10}|"
        f"HP{hp_pct:>3}%|BAT{battery:>3}%|{bat_status}"
    )


# ============================================================
# Q2 战斗日志分析
# ============================================================

def analyze_damage_log(lines):
    """解析混合格式的伤害日志。"""
    total = 0
    by_armor = {"front": 0, "left": 0, "right": 0}
    seen_ids = set()
    event_count = 0

    for line in lines:
        if not isinstance(line, str):
            continue
        s = line.strip()
        if not s or s.startswith("#"):
            continue

        # JSON 行
        if s.startswith("{"):
            try:
                data = json.loads(s)
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            if "armor" not in data or "damage" not in data:
                continue
            armor = data["armor"]
            damage = data["damage"]
            if armor not in ("front", "left", "right"):
                continue
            if (
                not isinstance(damage, int)
                or isinstance(damage, bool)
                or damage <= 0
            ):
                continue

            id_val = data.get("id", None)
            if id_val is not None:
                try:
                    if id_val in seen_ids:
                        continue
                    seen_ids.add(id_val)
                except TypeError:
                    pass

            total += damage
            by_armor[armor] += damage
            event_count += 1
            continue

        # 传感器行
        segments = s.split(",")
        valid = True
        parsed = []
        for seg in segments:
            seg = seg.strip()
            m = re.fullmatch(r"([FLR]):(\d+)", seg)
            if not m:
                valid = False
                break
            letter, num = m.group(1), int(m.group(2))
            if num <= 0:
                valid = False
                break
            armor = {"F": "front", "L": "left", "R": "right"}[letter]
            parsed.append((armor, num))
        if not valid:
            continue

        for armor, dmg in parsed:
            total += dmg
            by_armor[armor] += dmg
            event_count += 1

    most_hit = None
    if event_count > 0:
        max_dmg = max(by_armor.values())
        if max_dmg > 0:
            for part in ("front", "left", "right"):
                if by_armor[part] == max_dmg:
                    most_hit = part
                    break

    avg = round(total / event_count, 2) if event_count > 0 else 0.0

    return {
        "total": total,
        "by_armor": by_armor,
        "most_hit": most_hit,
        "avg": avg,
    }


# ============================================================
# Q3 SentryGrid
# ============================================================

class Facing(Enum):
    UP = (0, -1)
    RIGHT = (1, 0)
    DOWN = (0, 1)
    LEFT = (-1, 0)


class SentryGrid:
    def __init__(
        self,
        width,
        height,
        obstacles,
        enemy_pos,
        start_pos=(0, 0),
        facing=Facing.UP,
        fuel=100,
    ):
        self.width = width
        self.height = height
        self.obstacles = set(obstacles)
        self.enemy_pos = enemy_pos
        self._current_pos = None

        self.current_pos = start_pos
        self.facing = facing
        self.fuel = fuel
        self.collision_count = 0

    @property
    def current_pos(self):
        return self._current_pos

    @current_pos.setter
    def current_pos(self, value):
        if not isinstance(value, (tuple, list)) or len(value) != 2:
            raise TypeError(
                "current_pos must be a tuple or list of length 2"
            )
        try:
            x = int(value[0])
            y = int(value[1])
        except (ValueError, TypeError):
            raise TypeError("current_pos elements must be integers")
        self._current_pos = (x, y)

    def _in_bounds(self, pos):
        x, y = pos
        return 0 <= x < self.width and 0 <= y < self.height

    def move_forward(self):
        if self.fuel <= 0:
            return self.current_pos

        self.fuel -= 1

        dx, dy = self.facing.value
        next_x = self.current_pos[0] + dx
        next_y = self.current_pos[1] + dy
        next_pos = (next_x, next_y)

        if next_pos in self.obstacles or not self._in_bounds(next_pos):
            self.collision_count += 1
            return self.current_pos

        self._current_pos = next_pos
        return self.current_pos

    def turn_left(self):
        order = [Facing.UP, Facing.LEFT, Facing.DOWN, Facing.RIGHT]
        idx = order.index(self.facing)
        self.facing = order[(idx + 1) % 4]
        return self.facing

    def turn_right(self):
        order = [Facing.UP, Facing.RIGHT, Facing.DOWN, Facing.LEFT]
        idx = order.index(self.facing)
        self.facing = order[(idx + 1) % 4]
        return self.facing


# ============================================================
# Q4 贪心导航
# ============================================================

def next_step_toward(pos, target, obstacles, current_facing=Facing.UP):
    """返回下一步应朝向的 Facing。"""
    x, y = pos
    tx, ty = target
    d0 = abs(tx - x) + abs(ty - y)

    candidates = []
    for f in (Facing.UP, Facing.RIGHT, Facing.DOWN, Facing.LEFT):
        dx, dy = f.value
        nx, ny = x + dx, y + dy
        next_pos = (nx, ny)
        if next_pos in obstacles:
            continue
        d1 = abs(tx - nx) + abs(ty - ny)
        if d1 < d0:
            candidates.append((f, next_pos))

    if not candidates:
        return current_facing
    if len(candidates) == 1:
        return candidates[0][0]

    x_diff = abs(tx - x)
    y_diff = abs(ty - y)
    prefer_horizontal = x_diff >= y_diff

    for f, _ in candidates:
        is_horizontal = f in (Facing.LEFT, Facing.RIGHT)
        if is_horizontal == prefer_horizontal:
            return f
    return candidates[0][0]


# ============================================================
# Q5 哨兵决策机
# ============================================================

class SentryState(Enum):
    PATROL = "PATROL"
    SUSPECT = "SUSPECT"
    ENGAGE = "ENGAGE"
    RETREAT = "RETREAT"
    RETURN = "RETURN"


def decide(sensor, state, hp, heat):
    """哨兵决策机，返回 (action, new_state)。"""
    required = {"enemy_frames", "enemy_dist", "robot_type", "max_hp"}
    if not isinstance(sensor, dict) or not required.issubset(sensor.keys()):
        raise ValueError("sensor missing required fields")
    if not isinstance(state, SentryState):
        raise ValueError("invalid state")

    frames_raw = sensor["enemy_frames"]
    if (
        not isinstance(frames_raw, (list, tuple))
        or len(frames_raw) < 1
        or len(frames_raw) > 6
    ):
        raise ValueError("enemy_frames invalid length")
    frames = [bool(v) for v in frames_raw]

    enemy_dist_raw = sensor["enemy_dist"]
    if (
        isinstance(enemy_dist_raw, int)
        and not isinstance(enemy_dist_raw, bool)
        and enemy_dist_raw >= 0
    ):
        enemy_dist = enemy_dist_raw
    else:
        enemy_dist = 999

    robot_type_raw = sensor["robot_type"]
    if robot_type_raw == "HERO":
        robot_type = "HERO"
    else:
        robot_type = "INFANTRY"

    max_hp_raw = sensor["max_hp"]
    if (
        isinstance(max_hp_raw, int)
        and not isinstance(max_hp_raw, bool)
        and max_hp_raw > 0
    ):
        max_hp = max_hp_raw
    else:
        max_hp = 1

    hp_val = hp if isinstance(hp, int) and not isinstance(hp, bool) else 0
    hp_val = max(0, min(hp_val, max_hp))
    hp_pct = int(hp_val / max_hp * 100)
    hp_pct = max(0, min(100, hp_pct))

    visible = frames[-1] if frames else False

    # R1
    if hp_pct <= 30:
        return ("RETREAT", SentryState.RETREAT)

    # R2
    if state == SentryState.RETREAT:
        if hp_pct > 30:
            return ("RETURN", SentryState.RETURN)
        else:
            return ("RETREAT", SentryState.RETREAT)

    # R3
    if state == SentryState.RETURN:
        return ("MOVE_BASE", SentryState.PATROL)

    # R4
    if state == SentryState.ENGAGE and visible:
        if enemy_dist <= 3:
            return ("SHOOT", SentryState.ENGAGE)
        else:
            if robot_type == "HERO":
                return ("MOVE_RIGHT", SentryState.ENGAGE)
            else:
                return ("MOVE_LEFT", SentryState.ENGAGE)

    # R5
    if state == SentryState.ENGAGE and not visible:
        if len(frames) >= 2 and not frames[-1] and not frames[-2]:
            return ("SCAN", SentryState.SUSPECT)
        else:
            return ("HOLD_FIRE", SentryState.ENGAGE)

    # R6
    if state in (SentryState.PATROL, SentryState.SUSPECT) and visible:
        if len(frames) >= 2 and frames[-1] and frames[-2]:
            if enemy_dist <= 3:
                return ("SHOOT", SentryState.ENGAGE)
            else:
                if robot_type == "HERO":
                    return ("MOVE_RIGHT", SentryState.ENGAGE)
                else:
                    return ("MOVE_LEFT", SentryState.ENGAGE)
        else:
            return ("SCAN", SentryState.SUSPECT)

    # R7
    if state in (SentryState.PATROL, SentryState.SUSPECT) and not visible:
        if state == SentryState.PATROL:
            return ("PATROL_MOVE", SentryState.PATROL)
        else:
            return ("SCAN", SentryState.SUSPECT)

    return ("PATROL_MOVE", SentryState.PATROL)


# ============================================================
# Q6 巡逻任务
# ============================================================

def _bfs_next_step(start, target, obstacles, width, height):
    """从 start 到 target 的 BFS，返回 start 的下一步方向。"""
    if start == target:
        return None

    q = deque([start])
    parent = {start: None}

    while q:
        cur = q.popleft()
        if cur == target:
            break
        x, y = cur
        for f in (Facing.UP, Facing.RIGHT, Facing.DOWN, Facing.LEFT):
            dx, dy = f.value
            next_pos = (x + dx, y + dy)
            if next_pos in obstacles or not (
                0 <= next_pos[0] < width and 0 <= next_pos[1] < height
            ):
                continue
            if next_pos not in parent:
                parent[next_pos] = cur
                q.append(next_pos)

    if target not in parent:
        return None

    cur = target
    while parent[cur] != start:
        cur = parent[cur]

    dx = cur[0] - start[0]
    dy = cur[1] - start[1]
    for f in (Facing.UP, Facing.RIGHT, Facing.DOWN, Facing.LEFT):
        if f.value == (dx, dy):
            return f
    return None


def run_patrol(grid, max_steps=500):
    """巡逻任务主循环。"""
    visited = {grid.current_pos}
    steps = 0
    collisions = 0
    consecutive_collisions = 0

    while steps < max_steps and grid.fuel > 0:
        if grid.current_pos == grid.enemy_pos:
            break

        if consecutive_collisions >= 3:
            direction = _bfs_next_step(
                grid.current_pos,
                grid.enemy_pos,
                grid.obstacles,
                grid.width,
                grid.height,
            )
            if direction is None:
                direction = next_step_toward(
                    grid.current_pos,
                    grid.enemy_pos,
                    grid.obstacles,
                    grid.facing,
                )
        else:
            direction = next_step_toward(
                grid.current_pos,
                grid.enemy_pos,
                grid.obstacles,
                grid.facing,
            )

        while grid.facing != direction:
            grid.turn_right()

        old_pos = grid.current_pos
        grid.move_forward()
        steps += 1

        if grid.current_pos == old_pos:
            collisions += 1
            consecutive_collisions += 1
        else:
            consecutive_collisions = 0
            visited.add(grid.current_pos)

    success = grid.current_pos == grid.enemy_pos

    return {
        "steps": steps,
        "collisions": collisions,
        "visited_count": len(visited),
        "found_enemy": success,
        "success": success,
    }


def report_to_json(stats):
    """确定性 JSON 序列化。"""
    return json.dumps(stats, sort_keys=True, separators=(",", ":"))


# ============================================================
# Q7 Debug：昨天还能跑
# ============================================================

def segment_length_cm(p1, p2):
    """两个检查点 (x, y) 之间的路线长度，单位：厘米。
    检查点坐标单位为格，1 格 = 1 米 = 100 厘米，
    路线按曼哈顿距离计算。"""
    return (abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])) * 100


def total_route_meters(points):
    """整条巡逻路线的长度，单位：米。
    points 为检查点序列 [(x, y), ...]，至少两个点。"""
    distance_cm = 0
    for i in range(len(points) - 1):
        distance_cm += segment_length_cm(points[i], points[i + 1])
    return distance_cm / 100


def parse_event(line):
    """解析一行事件日志，形如 "MOVE,3" / "SCAN,0" / "IDLE,1"。
    合法返回 {"type": str, "count": int}；
    脏行返回 None（不得抛异常）。"""
    parts = line.strip().split(",")
    if len(parts) != 2 or parts[0] not in ("MOVE", "SCAN", "IDLE"):
        return None
    try:
        count = int(parts[1])
    except ValueError:
        return None
    return {"type": parts[0], "count": count}


def first_positive(samples):
    """返回样本序列中第一个正数；若没有正数，返回 None。"""
    for s in samples:
        if s > 0:
            return s
    return None


def calibrate(samples):
    """以第一个正样本为基线计算累计漂移：sum(s - baseline)。
    样本为空或没有正样本时，漂移为 0。"""
    baseline = first_positive(samples)
    if baseline is None:
        return 0

    drift = 0
    for s in samples:
        drift += s - baseline
    return drift


def summarize_events(events, max_id):
    """统计 id 不超过 max_id 的事件。"""
    used = 0
    steps = 0
    for e in events:
        if e["id"] <= max_id:
            used += 1
            steps += e["move"] + calibrate(e["samples"])
    return {"events": used, "steps": steps}


def log(message, history=None):
    """向历史追加一条日志并返回整个历史列表。
    不显式传入 history 时，每次调用都从空历史开始。"""
    if history is None:
        history = []
    history.append(message)
    return history


def run_legacy_sim(rounds, stamina_start=100):
    """旧版巡逻模拟。"""
    stamina = stamina_start
    round_ = 0
    trace = []

    while round_ < rounds:
        stamina -= 8
        if round_ >= 3:
            stamina -= 5

        trace.append((round_, stamina))

        if stamina <= 20:
            break

        round_ += 1

    return {
        "rounds": len(trace),
        "stamina": stamina,
        "trace": trace,
    }


# ============================================================
# Bonus：BFS 最短路
# ============================================================

def bfs_path_length(start, target, obstacles):
    """返回全局最短路的步数。
    start == target 返回 0；目标不可达返回 -1。
    注意：obstacles 由调用方负责包含地图边界。"""
    if start == target:
        return 0

    q = deque([start])
    dist = {start: 0}

    while q:
        cur = q.popleft()
        if cur == target:
            return dist[cur]

        x, y = cur
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            nxt = (x + dx, y + dy)
            if nxt in obstacles or nxt in dist:
                continue
            dist[nxt] = dist[cur] + 1
            q.append(nxt)

    return -1
# check


