"""Buổi tối — Mở Quán. KHUNG: đi lại, chặn biên, đồng hồ, kho nạp từ file/scenario.

Nhóm viết tiếp (PRD-0 mục F, Quán):
  TODO(nhóm, lát 3): khách đến theo lịch, chọn món nấu được, giữ chỗ nguyên liệu, kiên nhẫn,
                     bỏ đi (customer_left), no_dish, vòng đời khách.
  TODO(nhóm, lát 4): interact tại bếp/bàn (cook_started, dish_ready, dish_picked, served),
                     ăn xong trả tiền (paid), boa, uy tín, hết ca (quan_end).
"""
import math
from ..ids import sort_by_id, id_key
from .ramp import ramp_velocity
from ..errors import BadInput

TICK = 60.0


class QuanSim:
    mode = "quan"
    phase = "quan"

    def __init__(self, tuning, scenario, streams, ids, inventory=None):
        t = tuning["quan"]
        self.t = t
        self.menu = tuning["menu"]
        self.rng = streams
        self.ids = ids
        p = scenario.get("player", {})
        self.pos = [float(c) for c in p.get("pos", t["start_pos"])]
        self.vel = [float(c) for c in p.get("vel", [0.0, 0.0])]
        self._tgt = None
        self._ramp_left = 0
        # kho: --inventory HOẶC scenario.stock (cả hai -> cli đã báo mã 2)
        self.stock = dict(inventory if inventory is not None else scenario.get("stock", {}))
        self.hand = dict(scenario["hand"]) if scenario.get("hand") is not None else None 
        self.time_left_ticks = scenario.get("time_left_ticks", int(round(t["duration_s"] * 60)))
        self.phase_tick = 0 
        self.reputation = float(scenario.get("reputation", t["reputation_initial"]))
        self.stoves = [dict(s, state=s.get("state", "idle"),
                            dish=dict(s["dish"]) if s.get("dish") is not None else None,
                            cook_ticks_left=s.get("cook_ticks_left", 0), ready_ticks=s.get("ready_ticks", 0))
                       for s in self._merge(t["stoves"], scenario.get("stoves", []))]
        self.tables = self._merge(t["tables"], scenario.get("tables", []))
        self.patience_max = int(round(t["patience_s"] * TICK))
        self.eat_max = int(round(t["eat_s"] * TICK))
        self.customers = self._init_customers(scenario.get("customers", []))
        for e in self.customers:
            ids.reserve(e["id"])
        self.money = 0
        self.earned = 0
        self.shift_earned = 0
        self.done = False
        self.reason = None

    @staticmethod
    def _merge(defaults, updates):
        by_id = {d["id"]: dict(d) for d in defaults}
        for u in updates:
            if u["id"] not in by_id:
                from ..errors import BadInput
                raise BadInput(f"id bếp/bàn không tồn tại: {u['id']}")
            by_id[u["id"]].update(u)
        return sort_by_id(list(by_id.values()))

    def _init_customers(self, raw_customers):
        custs = []
        for c in raw_customers:
            state = c.get("state", "waiting")
            order_status = c.get("order_status", "reserved")
            item = dict(c)
            item["state"] = state
            item["order_tick"] = c.get("order_tick", 0)
            item["patience_ticks_left"] = c.get("patience_ticks_left", self.patience_max if state == "waiting" else 0)
            item["eat_ticks_left"] = c.get("eat_ticks_left", self.eat_max if state == "eating" else 0)
            item["order_status"] = order_status
            item["reserved"] = dict(c["reserved"]) if "reserved" in c and c["reserved"] is not None else None
            item["base_price"] = c.get("base_price")
            item["tip"] = c.get("tip")
            custs.append(item)

        need_res = [c for c in custs if c["order_status"] == "reserved" and c["reserved"] is None]
        need_res.sort(key=lambda c: (c["order_tick"], id_key(c["table_id"])))
        for c in need_res:
            recipe = self.menu[c["dish_id"]]["recipe"]
            avail = self._available_stock(custs)
            if all(avail.get(k, 0) >= v for k, v in recipe.items()):
                c["reserved"] = dict(recipe)
            else:
                raise BadInput(f"Khách {c['id']} thiếu nguyên liệu giữ chỗ")

        for c in custs:
            if c["reserved"] is None:
                c["reserved"] = {}
        return sort_by_id(custs)

    def _available_stock(self, cust_list=None):
        if cust_list is None:
            cust_list = self.customers
        avail = dict(self.stock)
        for c in cust_list:
            for k, v in c.get("reserved", {}).items():
                avail[k] = avail.get(k, 0) - v
        return avail

    def snapshot(self) -> dict:
        occupied = {c["table_id"]: c["id"] for c in self.customers}
        return {
            "player": {"pos": self.pos},
            "stock": {k: self.stock[k] for k in sorted(self.stock) if self.stock[k] > 0},
            "hand": self.hand,
            "stoves": [{k: s.get(k) for k in ("id", "pos", "state", "dish", "cook_ticks_left", "ready_ticks")}
                       for s in self.stoves],
            "tables": [{"id": tb["id"], "pos": tb["pos"], "customer_id": occupied.get(tb["id"])} for tb in self.tables],
            "customers": sort_by_id(self.customers),
        }

    def step(self, inp):
        events = []
        self.phase_tick += 1
        self.time_left_ticks = max(0, self.time_left_ticks - 1)

        for s in sort_by_id(self.stoves):
            if s["state"] == "ready":
                s["ready_ticks"] += 1
            elif s["state"] == "cooking":
                s["cook_ticks_left"] = max(0, s["cook_ticks_left"] - 1)

        for c in sort_by_id(self.customers):
            if c["state"] == "eating":
                c["eat_ticks_left"] = max(0, c["eat_ticks_left"] - 1)
            elif c["state"] == "waiting":
                c["patience_ticks_left"] = max(0, c["patience_ticks_left"] - 1)

        for s in sort_by_id(self.stoves):
            if s["state"] == "cooking" and s["cook_ticks_left"] == 0:
                s["state"] = "ready"
                s["ready_ticks"] = 0
                dish = s["dish"]
                events.append(("dish_ready", {
                    "stove_id": s["id"],
                    "order_id": dish["order_id"],
                    "dish_id": dish["dish_id"],
                }))

        self._move(inp)
        if inp.pressed("interact"):
            r = float(self.t["interact_radius"])
            candidates = []
            for s in self.stoves:
                d = math.dist(self.pos, s["pos"])
                if d <= r:
                    candidates.append((d, 0, id_key(s["id"]), "stove", s))
            for tb in self.tables:
                d = math.dist(self.pos, tb["pos"])
                if d <= r:
                    candidates.append((d, 1, id_key(tb["id"]), "table", tb))

            if candidates:
                candidates.sort(key=lambda item: (item[0], item[1], item[2]))
                _, _, _, kind, obj = candidates[0]
                if kind == "stove":
                    self._interact_stove(obj, events)
                else:
                    self._interact_table(obj, events)

        closing = (self.time_left_ticks <= 0)
        cust_by_table = {c["table_id"]: c for c in self.customers}
        to_remove = set()

        for tb in sort_by_id(self.tables):
            c = cust_by_table.get(tb["id"])
            if not c:
                continue

            if c["state"] == "eating":
                if c["eat_ticks_left"] == 0 or closing:
                    base_price = int(c["base_price"])
                    tip = int(c["tip"])
                    amount = base_price + tip
                    self.money += amount
                    self.earned += amount
                    self.shift_earned += amount
                    if tip > 0:
                        self.reputation = min(
                            float(self.t["reputation_max"]),
                            round(self.reputation + float(self.t["tip_reputation"]), 6)
                        )
                    events.append(("paid", {
                        "order_id": c["id"],
                        "table_id": c["table_id"],
                        "base_price": base_price,
                        "tip": tip,
                        "amount": amount,
                        "reason": "finished_eating" if c["eat_ticks_left"] == 0 else "closing"
                    }))
                    to_remove.add(c["id"])

            elif c["state"] == "waiting":
                if closing:
                    self._cleanup_order_items(c["id"])
                    events.append(("customer_left", {
                        "order_id": c["id"],
                        "table_id": c["table_id"],
                        "reason": "closing",
                        "reputation": self.reputation
                    }))
                    to_remove.add(c["id"])
                elif c["patience_ticks_left"] == 0:
                    self._cleanup_order_items(c["id"])
                    self.reputation = max(
                        float(self.t["reputation_min"]),
                        min(float(self.t["reputation_max"]),
                            round(self.reputation + float(self.t["left_reputation_delta"]), 6))
                    )
                    events.append(("customer_left", {
                        "order_id": c["id"],
                        "table_id": c["table_id"],
                        "reason": "patience",
                        "reputation": self.reputation
                    }))
                    to_remove.add(c["id"])

        if to_remove:
            self.customers = [c for c in self.customers if c["id"] not in to_remove]

        if closing:
            self.done = True
            self.reason = "time"
            events.append(("quan_end", {"reason": "time", "money": self.money, "earned": self.earned,
                                        "shift_earned": self.shift_earned, "reputation": self.reputation}))
            return events

        first_tick = int(self.t["first_customer_tick"])
        interval_ticks = int(round(self.t["customer_interval_s"] * TICK))
        if self.phase_tick >= first_tick and (self.phase_tick - first_tick) % interval_ticks == 0:
            occupied_tables = {c["table_id"] for c in self.customers}
            free_tables = [tb for tb in sort_by_id(self.tables) if tb["id"] not in occupied_tables]
            if free_tables:
                target_table = free_tables[0]
                avail = self._available_stock()
                cookable = [
                    dish_id for dish_id in sorted(self.menu.keys())
                    if all(avail.get(k, 0) >= v for k, v in self.menu[dish_id]["recipe"].items())
                ]
                if cookable:
                    chosen_dish = self.rng.get("customer_dish").choice(cookable)
                    recipe = dict(self.menu[chosen_dish]["recipe"])
                    order_id = self.ids.new("C")
                    new_cust = {
                        "id": order_id,
                        "table_id": target_table["id"],
                        "dish_id": chosen_dish,
                        "order_tick": self.phase_tick,
                        "state": "waiting",
                        "patience_ticks_left": self.patience_max,
                        "eat_ticks_left": 0,
                        "order_status": "reserved",
                        "reserved": recipe,
                        "base_price": None,
                        "tip": None,
                    }
                    self.customers.append(new_cust)
                    self.customers = sort_by_id(self.customers)
                    events.append(("customer_arrived", {
                        "order_id": order_id,
                        "table_id": target_table["id"],
                        "dish_id": chosen_dish
                    }))
                else:
                    events.append(("no_dish", {}))
        return events

    def _interact_stove(self, stove, events):
        if stove["state"] == "idle":
            reserved_orders = [
                c for c in self.customers
                if c["state"] == "waiting" and c["order_status"] == "reserved"
            ]
            if not reserved_orders:
                return
            reserved_orders.sort(key=lambda c: (c["order_tick"], id_key(c["table_id"])))
            target_cust = reserved_orders[0]
            dish_id = target_cust["dish_id"]
            menu_item = self.menu[dish_id]
            recipe = menu_item["recipe"]

            items_list = []
            for k in sorted(recipe.keys()):
                cnt = int(recipe[k])
                self.stock[k] = max(0, self.stock.get(k, 0) - cnt)
                items_list.extend([k] * cnt)

            target_cust["reserved"] = {}
            target_cust["order_status"] = "assigned"
            base_price = int(menu_item["price"])
            stove["state"] = "cooking"
            stove["dish"] = {
                "order_id": target_cust["id"],
                "dish_id": dish_id,
                "base_price": base_price
            }
            stove["cook_ticks_left"] = int(round(menu_item["cook_s"] * TICK))
            stove["ready_ticks"] = 0

            events.append(("cook_started", {
                "stove_id": stove["id"],
                "order_id": target_cust["id"],
                "dish_id": dish_id,
                "items": items_list,
                "base_price": base_price
            }))

        elif stove["state"] == "ready":
            if self.hand is not None:
                return
            dish = stove["dish"]
            self.hand = dict(dish)
            stove["state"] = "idle"
            stove["dish"] = None
            stove["cook_ticks_left"] = 0
            stove["ready_ticks"] = 0
            events.append(("dish_picked", {
                "stove_id": stove["id"],
                "order_id": dish["order_id"],
                "dish_id": dish["dish_id"]
            }))

        def _interact_table(self, table, events):
            if self.hand is None:
               return
        cust = next((c for c in self.customers if c["table_id"] == table["id"]), None)
        if not cust or cust["state"] != "waiting":
            return
        if self.hand["order_id"] != cust["id"]:
            return

        dish = self.hand
        self.hand = None
        base_price = int(dish["base_price"])
        ratio = cust["patience_ticks_left"] / float(self.patience_max) if self.patience_max > 0 else 0.0
        if ratio >= float(self.t["tip_min_patience_ratio"]):
            tip = int(math.floor(base_price * float(self.t["tip_rate"])))
        else:
            tip = 0

        cust["state"] = "eating"
        cust["order_status"] = "served"
        cust["eat_ticks_left"] = self.eat_max
        cust["base_price"] = base_price
        cust["tip"] = tip

        events.append(("served", {
            "order_id": cust["id"],
            "table_id": table["id"],
            "dish_id": dish["dish_id"],
            "patience_ticks_left": cust["patience_ticks_left"],
            "base_price": base_price,
            "tip": tip
        }))

    def _cleanup_order_items(self, order_id):
        if self.hand is not None and self.hand.get("order_id") == order_id:
            self.hand = None
        for s in self.stoves:
            if s.get("dish") is not None and s["dish"].get("order_id") == order_id:
                s["state"] = "idle"
                s["dish"] = None
                s["cook_ticks_left"] = 0
                s["ready_ticks"] = 0

    def _move(self, inp):
        speed = self.t["walk_speed"]
        mx, mz = inp.move
        self.vel = ramp_velocity(self, (mx * speed, mz * speed), int(self.t.get("ramp_max_ticks", 6)))
        b = self.t["bounds"]
        for i, axis in enumerate(("x", "z")):
            self.pos[i] += self.vel[i] / TICK
            lo, hi = b[axis]
            if self.pos[i] <= lo:
                self.pos[i], self.vel[i] = lo, max(0.0, self.vel[i])
            elif self.pos[i] >= hi:
                self.pos[i], self.vel[i] = hi, min(0.0, self.vel[i])