import gamelib
import random
import math
import warnings
from sys import maxsize
import json

class AlgoStrategy(gamelib.AlgoCore):
    def __init__(self):
        super().__init__()
        seed = random.randrange(maxsize)
        random.seed(seed)
        gamelib.debug_write(f"Random seed: {seed}")

        # Basic tracking for enemy spawns, enemy defenses in our half, and where we got breached
        self.enemy_spawn_history = []  # elements are [left_spawns, right_spawns, turn_number]
        self.enemy_defense_positions = []
        self.scored_on_locations = []
        self.attack_count = 0

    def on_game_start(self, config):
        gamelib.debug_write("Refined adaptive algo strategy (no built-in simulation).")
        self.config = config

        global WALL, SUPPORT, TURRET, SCOUT, DEMOLISHER, INTERCEPTOR, MP, SP
        WALL = config["unitInformation"][0]["shorthand"]
        SUPPORT = config["unitInformation"][1]["shorthand"]
        TURRET = config["unitInformation"][2]["shorthand"]
        SCOUT = config["unitInformation"][3]["shorthand"]
        DEMOLISHER = config["unitInformation"][4]["shorthand"]
        INTERCEPTOR = config["unitInformation"][5]["shorthand"]
        MP = 1
        SP = 0

    def on_turn(self, turn_string):
        game_state = gamelib.GameState(self.config, turn_string)
        game_state.suppress_warnings(True)

        # Dynamically remove and add defenses based on recent data
        self.dynamic_defense_adjustments(game_state)
        # Build or repair main defenses
        self.build_defenses(game_state)
        # Decide if we should go on offense
        if self.should_attack(game_state):
            self.execute_offense(game_state)
            self.attack_count += 1

        game_state.submit_turn()

    def dynamic_defense_adjustments(self, game_state):
        """
        Look at the last ~3 turns of enemy spawn data plus
        the current distribution of enemy defenses in our half.
        Remove or relocate structures as needed to free up SP
        or reinforce heavily attacked sides.
        """
        turn = game_state.turn_number
        if turn < 3:
            return  # Not enough data to adjust yet

        recent_records = [r for r in self.enemy_spawn_history if r[2] >= turn - 3]
        left_spawns = sum(r[0] for r in recent_records)
        right_spawns = sum(r[1] for r in recent_records)

        # Measure enemy defenses in our half:
        enemy_left_defenses = sum(1 for d in self.enemy_defense_positions if d[0] < 14)
        enemy_right_defenses = sum(1 for d in self.enemy_defense_positions if d[0] >= 14)

        # If the enemy floods us from one side and doesn’t build many defenses there, we might shift to heavy offense
        # But keep minimal turrets for that side’s defense
        if left_spawns > right_spawns and enemy_left_defenses < enemy_right_defenses:
            # Remove some left walls to open resources
            removal_candidates = [[6, 11], [7, 11], [8, 11]]
            game_state.attempt_remove(removal_candidates)
            # Possibly place more turrets on the right to hold off small spawns, or if we see right spawns growing
            if right_spawns > 1:
                game_state.attempt_spawn(TURRET, [[20, 10], [21, 10]])

        elif right_spawns > left_spawns and enemy_right_defenses < enemy_left_defenses:
            # Remove some right walls
            removal_candidates = [[20, 11], [21, 11], [19, 11]]
            game_state.attempt_remove(removal_candidates)
            # Add a couple turrets on the left if strong left spawns come in
            if left_spawns > 1:
                game_state.attempt_spawn(TURRET, [[6, 10], [7, 10]])

        # If neither side is heavily targeted or the enemy is well balanced, do nothing special
        # or remove a few unneeded walls to accumulate SP for future turns
        if left_spawns < 2 and right_spawns < 2 and turn > 6:
            game_state.attempt_remove([[10, 11], [17, 11]])  # free up some SP for future

    def build_defenses(self, game_state):
        """
        Builds a layered defense with a small opening in the middle. 
        Upgrades selectively over time, places some supports behind.
        """
        turn = game_state.turn_number
        sp_available = game_state.get_resource(SP)

        # Basic front wall with a single gap at x=13
        front_wall_positions = [[x, 11] for x in range(4, 24) if x != 13]
        game_state.attempt_spawn(WALL, front_wall_positions)

        # Upgrade front walls if we have enough SP
        if turn > 2 and sp_available > 8:
            game_state.attempt_upgrade(front_wall_positions)

        # Turrets behind walls
        turret_positions = [[6, 10], [10, 10], [17, 10], [21, 10]]
        for pos in turret_positions:
            game_state.attempt_spawn(TURRET, pos)

        # Upgrade a few turrets if we have leftover SP
        if turn > 4 and sp_available > 10:
            game_state.attempt_upgrade(random.sample(turret_positions, 2))

        # Supports further behind to benefit from bigger range
        support_positions = [[12, 8], [13, 8], [14, 8], [15, 8]]
        if turn > 1:
            for pos in support_positions:
                game_state.attempt_spawn(SUPPORT, pos)
            if sp_available > 10:
                game_state.attempt_upgrade(support_positions)

        # Possibly a second wall row at y=10 if we have enough SP after turn ~7
        if turn > 7 and sp_available > 15:
            second_row = [[x, 10] for x in range(5, 23) if x not in (13, 14)]
            game_state.attempt_spawn(WALL, second_row)
            if game_state.get_resource(SP) > 20:
                game_state.attempt_upgrade(second_row)

    def should_attack(self, game_state):
        """
        Decide whether to launch an attack wave. For now:
        - Skip first 3 turns to build a stable defense
        - If we have ≥10 MP or every 4th turn, consider attacking
        """
        turn = game_state.turn_number
        mp = game_state.get_resource(MP)
        if turn < 3:
            return False
        return mp >= 10 or (turn % 4 == 0)

    def execute_offense(self, game_state):
        """
        Builds an attacking wave of Demolishers (40%) and Scouts (60%).
        Chooses spawn side opposite where we were breached most often.
        """
        mp = game_state.get_resource(MP)
        left_breaches = sum(1 for loc in self.scored_on_locations if loc[0] < 14)
        right_breaches = sum(1 for loc in self.scored_on_locations if loc[0] >= 14)

        # If the enemy breaks us more on the left, we spawn right (and vice versa)
        if left_breaches > right_breaches:
            spawn_loc = [14, 0]
        else:
            spawn_loc = [13, 0]

        # Example ratio
        demolisher_cost = 4
        demolisher_count = int((mp * 0.4) // demolisher_cost)
        if demolisher_count > 0:
            game_state.attempt_spawn(DEMOLISHER, spawn_loc, demolisher_count)
        # Use remainder for scouts
        leftover_mp = int(game_state.get_resource(MP))
        if leftover_mp > 0:
            game_state.attempt_spawn(SCOUT, spawn_loc, leftover_mp)

    def on_action_frame(self, turn_string):
        """
        Record spawns and defenses for future turns. Also note where we got breached.
        """
        state = json.loads(turn_string)
        events = state["events"]

        # Breaches
        for breach in events.get("breach", []):
            location = breach[0]
            unit_owner_self = (breach[4] == 1)
            if not unit_owner_self:
                self.scored_on_locations.append(location)

        # Spawns
        enemy_left_spawns = 0
        enemy_right_spawns = 0
        for spawn in events.get("spawn", []):
            location = spawn[0]
            unit_owner = spawn[3]
            if unit_owner != 0:  # Enemy
                if location[0] < 14:
                    enemy_left_spawns += 1
                else:
                    enemy_right_spawns += 1

        turn_number = state["turnInfo"][1]
        existing = [rec for rec in self.enemy_spawn_history if rec[2] == turn_number]
        if existing:
            existing[0][0] += enemy_left_spawns
            existing[0][1] += enemy_right_spawns
        else:
            self.enemy_spawn_history.append([enemy_left_spawns, enemy_right_spawns, turn_number])

        # Track enemy structures in our half
        self.enemy_defense_positions = []
        for structure_type, units in enumerate(state["p2Units"]):
            for unit in units:
                x, y = unit[0], unit[1]
                if y <= 13:
                    self.enemy_defense_positions.append([x, y, structure_type])

if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()