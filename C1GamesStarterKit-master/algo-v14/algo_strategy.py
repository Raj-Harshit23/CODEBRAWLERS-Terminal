import gamelib
import random
import math
import warnings
from sys import maxsize
import json


"""
Most of the algo code you write will be in this file unless you create new
modules yourself. Start by modifying the 'on_turn' function.

Advanced strategy tips: 

  - You can analyze action frames by modifying on_action_frame function

  - The GameState.map object can be manually manipulated to create hypothetical 
  board states. Though, we recommended making a copy of the map to preserve 
  the actual current map state.
"""

class AlgoStrategy(gamelib.AlgoCore):
    def __init__(self):
        super().__init__()
        seed = random.randrange(maxsize)
        random.seed(seed)
        gamelib.debug_write('Random seed: {}'.format(seed))
        self.attack_count = 0
        self.breached_last_round = False

    def on_game_start(self, config):
        gamelib.debug_write('Configuring your custom algo strategy...')
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
        self.scored_on_locations = []

    def on_turn(self, turn_state):
        game_state = gamelib.GameState(self.config, turn_state)
        gamelib.debug_write('Performing turn {} of your custom algo strategy'.format(game_state.turn_number))
        game_state.suppress_warnings(True)  # Comment or remove this line to enable warnings.
        self.newalgo(game_state)
        game_state.submit_turn()

    def on_action_frame(self, turn_string):
        state = json.loads(turn_string)
        events = state["events"]
        breaches = events["breach"]
        self.breached_last_round = False
        for breach in breaches:
            location = breach[0]
            unit_owner_self = True if breach[4] == 1 else False
            if not unit_owner_self:
                gamelib.debug_write("Got scored on at: {}".format(location))
                self.scored_on_locations.append(location)
                self.breached_last_round = True
                gamelib.debug_write("All locations: {}".format(self.scored_on_locations))

    def euclidean_distance(self, point1, point2):
        return math.sqrt((point1[0] - point2[0]) ** 2 + (point1[1] - point2[1]) ** 2)

    def prioritize_turret_positions(self, breach_location, positions):
        return sorted(positions, key=lambda pos: self.euclidean_distance(pos, breach_location))

    def prioritize_turret_positions_by_distance(self, game_state, positions):
        def closest_turret_distance(pos):
            min_distance = float('inf')
            for x in range(game_state.ARENA_SIZE):
                for y in range(game_state.ARENA_SIZE):
                    units = game_state.game_map[x, y]
                    if units:  # Check if units is not None
                        for unit in units:
                            if unit.unit_type == TURRET and unit.player_index == 0:
                                distance = self.euclidean_distance(pos, [x, y])
                                if distance < min_distance:
                                    min_distance = distance
            return min_distance

        return sorted(positions, key=closest_turret_distance, reverse=True)

    # def get_optimal_attack(self, game_state):
    #     attack_positions = [[3, 10], [4, 9], [5, 8], [6, 7], [7, 6], [8, 5], [9, 4], [10, 3], [11, 2], [12, 1], [13, 0], [14, 0], [15, 1], [16, 2], [17, 3], [18, 4], [19, 5], [20, 6], [21, 7], [22, 8], [23, 9], [24, 10]]
    #     optimal_position = None
    #     minimal_damage = float('inf')

    #     for position in attack_positions:
    #         path = game_state.find_path_to_edge(position)
    #         if not path:
    #             total_damage = 999999
    #             if total_damage < minimal_damage:
    #                 minimal_damage = total_damage
    #                 optimal_position = position
    #             continue

    #         total_damage = 0
    #         for path_location in path:
    #             attackers = game_state.get_attackers(path_location, 1)
    #             for attacker in attackers:
    #                 total_damage += attacker.damage_i

    #         if total_damage < minimal_damage:
    #             minimal_damage = total_damage
    #             optimal_position = position

    #     return optimal_position, game_state.find_path_to_edge(optimal_position)

    def get_optimal_attack(self, game_state):
        attack_positions = [[3, 10], [4, 9], [5, 8], [6, 7], [7, 6], [8, 5], [9, 4], [10, 3], [11, 2], [12, 1], [13, 0], [14, 0], [15, 1], [16, 2], [17, 3], [18, 4], [19, 5], [20, 6], [21, 7], [22, 8], [23, 9], [24, 10]]
        attack_positions = attack_positions[::3]
        optimal_position = None
        minimal_damage = float('inf')

        for position in attack_positions:
            path = game_state.find_path_to_edge(position)
            if not path:
                total_damage = 999999
                # gamelib.debug_write(f"Position {position}: No path found, damage set to {total_damage}")
                if total_damage < minimal_damage:
                    minimal_damage = total_damage
                    optimal_position = position
                continue

            total_damage = 0
            

            for path_location in path:
                attackers = game_state.get_attackers(path_location, 0)
                
                for attacker in attackers:
                    total_damage += attacker.damage_i

            gamelib.debug_write(f"Position {position}: Total damage: {total_damage}")

            if total_damage <= minimal_damage:
                minimal_damage = total_damage
                optimal_position = position
        gamelib.debug_write(f"Optimal attack position: {optimal_position}, minimal damage: {minimal_damage}")
        return optimal_position, game_state.find_path_to_edge(optimal_position)

    def newalgo(self, game_state):
        support_locations = [[13, 4], [14, 4], [13, 3]]
        extended_left_corner = [[5, 8], [5, 9], [5, 10], [5, 11], [5, 12], [4, 13], [4, 11], [4, 10], [4, 9], [3, 13], [3, 12], [3, 10], [2, 12], [2, 11], [0, 13], [1, 13]]
        gamelib.debug_write("spawning stationary units on defense lines and upgrading based on priorities")

        corner3 = [[0, 13], [1, 13], [3, 12], [3, 11]]
        corner4 = [[27, 13], [26, 13], [24, 12], [24, 11]]

        turret_protect_locations = [[12, 5], [15, 5]]
        v_turret = [[4, 9], [8, 5], [22, 11], [10, 5], [12, 7], [14, 9]]
        middle_turrets = [[7, 7], [8, 8], [17, 8], [19, 8]]

        new_defense_left = [[5, 11], [5, 9], [7, 9], [7, 7], [9, 7], [9, 5], [11, 5], [11, 3], [12, 3], [7, 11], [9, 9], [11, 7], [13, 5]]
        new_defense_right = [[21, 11], [21, 9], [19, 9], [19, 7], [17, 7], [17, 5], [15, 5], [15, 7], [17, 9], [19, 11]]
        new_corners = [[25, 11], [25, 12], [25, 13], [2, 13], [2, 12], [2, 11]]

        locations_to_upgrade = turret_protect_locations + corner3 + new_corners + new_defense_left + new_defense_right + corner4
        locations_to_spawn = corner4 + middle_turrets + v_turret
        overall_defense = corner4 + new_defense_right + new_defense_left + new_corners

        if game_state.turn_number >= 2:
            if self.breached_last_round:
                breach_location = self.scored_on_locations[-1]
                corner3 = self.prioritize_turret_positions(breach_location, corner3)
                corner4 = self.prioritize_turret_positions(breach_location, corner4)
                extended_left_corner = self.prioritize_turret_positions(breach_location, extended_left_corner)
                turret_protect_locations = self.prioritize_turret_positions(breach_location, turret_protect_locations)
                v_turret = self.prioritize_turret_positions(breach_location, v_turret)
                middle_turrets = self.prioritize_turret_positions(breach_location, middle_turrets)
                locations_to_upgrade = self.prioritize_turret_positions(breach_location, locations_to_upgrade)
                locations_to_spawn = self.prioritize_turret_positions(breach_location, locations_to_spawn)
                overall_defense = self.prioritize_turret_positions(breach_location, overall_defense)
            else:
                corner3 = self.prioritize_turret_positions_by_distance(game_state, corner3)
                corner4 = self.prioritize_turret_positions_by_distance(game_state, corner4)
                extended_left_corner = self.prioritize_turret_positions_by_distance(game_state, extended_left_corner)
                turret_protect_locations = self.prioritize_turret_positions_by_distance(game_state, turret_protect_locations)
                v_turret = self.prioritize_turret_positions_by_distance(game_state, v_turret)
                middle_turrets = self.prioritize_turret_positions_by_distance(game_state, middle_turrets)
                locations_to_upgrade = self.prioritize_turret_positions_by_distance(game_state, locations_to_upgrade)
                locations_to_spawn = self.prioritize_turret_positions_by_distance(game_state, locations_to_spawn)
                overall_defense = self.prioritize_turret_positions_by_distance(game_state, overall_defense)

        game_state.attempt_spawn(TURRET, corner3)
        game_state.attempt_spawn(SUPPORT, support_locations)
        game_state.attempt_spawn(TURRET, turret_protect_locations)
        game_state.attempt_upgrade(support_locations)
        game_state.attempt_spawn(TURRET, overall_defense)
        game_state.attempt_upgrade(locations_to_upgrade)
        game_state.attempt_spawn(TURRET, extended_left_corner)
        game_state.attempt_upgrade(extended_left_corner)

        attack_position, _ = self.get_optimal_attack(game_state)

        if game_state.get_resource(MP) >= 5:
            self.attack_count += 1
            gamelib.debug_write('Enough resources, now spawn the army')
            game_state.attempt_spawn(SCOUT, attack_position, 10)
            game_state.attempt_spawn(DEMOLISHER, attack_position, 1)
            game_state.attempt_spawn(SCOUT, attack_position, 10)

        game_state.attempt_upgrade([3, 12])
        game_state.attempt_upgrade([24, 12])

if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()