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
class LRUTurretCache:
    def __init__(self, capacity):
        self.capacity = capacity
        self.cache = {}
        self.order = []

    def make_turret_lru(self, x, y):
        key = (x, y)
        if key in self.cache:
            self.order.remove(key)
        elif len(self.cache) >= self.capacity:
            oldest = self.order.pop(0)
            del self.cache[oldest]

        self.cache[key] = True
        self.order.append(key)

    def remove_existing_turret(self, x, y):
        key = (x, y)
        if key in self.cache:
            self.order.remove(key)
            del self.cache[key]

    def check_turret(self, x, y):
        return (x, y) in self.cache

    def make_most_recently_used(self, x, y):
        key = (x, y)
        if key in self.cache:
            self.order.remove(key)
            self.order.append(key)


class AlgoStrategy(gamelib.AlgoCore):
    def __init__(self):
        super().__init__()
        seed = random.randrange(maxsize)
        random.seed(seed)
        # gamelib.debug_write('Random seed: {}'.format(seed))
        self.attack_count = 0
        self.lru_cache = LRUTurretCache(100)
        self.prev_turret_health = {}

    def on_game_start(self, config):
        # gamelib.debug_write('Configuring your custom algo strategy...')
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
        # gamelib.debug_write('Performing turn {} of your custom algo strategy'.format(game_state.turn_number))
        game_state.suppress_warnings(True)  # Comment or remove this line to enable warnings.
        self.newalgo(game_state)
        game_state.submit_turn()

    def on_action_frame(self, turn_string):
        state = json.loads(turn_string)
        events = state["events"]
        breaches = events["breach"]
        for breach in breaches:
            location = breach[0]
            unit_owner_self = True if breach[4] == 1 else False
            if not unit_owner_self:
                # gamelib.debug_write("Got scored on at: {}".format(location))
                self.scored_on_locations.append(location)
                # gamelib.debug_write("All locations: {}".format(self.scored_on_locations))

    def euclidean_distance(self, point1, point2):
        return math.sqrt((point1[0] - point2[0]) ** 2 + (point1[1] - point2[1]) ** 2)

    def prioritize_turret_positions(self, breach_location, positions):
        return sorted(positions, key=lambda pos: self.euclidean_distance(pos, breach_location))

    def get_optimal_attack(self, game_state):
        attack_positions = [[3, 10], [4, 9], [5, 8], [6, 7], [7, 6], [8, 5], [9, 4], [10, 3], [11, 2], [12, 1], [13, 0], [14, 0], [15, 1], [16, 2], [17, 3], [18, 4], [19, 5], [20, 6], [21, 7], [22, 8], [23, 9], [24, 10]]
        optimal_position = None
        minimal_damage = float('inf')

        for position in attack_positions:
            path = game_state.find_path_to_edge(position)
            if not path:
                total_damage = 999999
                if total_damage < minimal_damage:
                    minimal_damage = total_damage
                    optimal_position = position
                continue

            total_damage = 0
            for path_location in path:
                attackers = game_state.get_attackers(path_location, 1)
                for attacker in attackers:
                    total_damage += attacker.damage_i

            if path and path[-1] not in game_state.game_map.get_edge_locations(game_state.get_target_edge(position)):
                continue
            if total_damage < minimal_damage:
                minimal_damage = total_damage
                optimal_position = position

        return optimal_position, game_state.find_path_to_edge(optimal_position)
    
    def prioritize_upgrade_list(self, game_state, upgrade_list):
        ratio = 0.3

        curr_support_points = game_state.get_resource(SP)
        first_support = game_state.get_resource(SP)
        # use 30% of support points for upgrades
        curr_upgrade_points = curr_support_points * ratio
        upgraded = 0
        for loc in upgrade_list:
            if (first_support - curr_support_points) > ratio*first_support:
                break
            if game_state.attempt_upgrade(loc):
                upgraded += 1
                curr_upgrade_points -= (curr_support_points - game_state.get_resource(SP))
                curr_support_points = game_state.get_resource(SP)

        curr_support_points = game_state.get_resource(SP)

        if (first_support - curr_support_points) > ratio*first_support:
            # error condition
            gamelib.debug_write("Error: Upgraded more than 30% of support points")
            # print the current and first support points
            gamelib.debug_write("Current support points: {}".format(curr_support_points))
            gamelib.debug_write("First support points: {}".format(first_support))
            # print the number of upgraded locations
            gamelib.debug_write("Upgraded {} locations".format(upgraded))
        else:
            gamelib.debug_write("Upgraded {} locations".format(upgraded))

    def custom_spawn_turret(self, game_state, turret_list):
        for turret in turret_list:
            if self.lru_cache.check_turret(turret[0],turret[1]):
                continue
            else:
                game_state.attempt_spawn(TURRET, [turret])
                self.lru_cache.make_most_recently_used(turret[0],turret[1])
                self.prev_turret_health[(turret[0],turret[1])] = 70

    def newalgo(self, game_state):
        # self.prev_health.append(game_state.get_resource(SP))
        # support_locations = [[13, 4], [14, 4], [13, 3],[14,3]]
        # extended_left_corner = [[5, 8], [5, 9], [5, 10], [5, 11], [5, 12], [4, 13], [4, 11], [4, 10], [4, 9], [3, 13], [3, 12], [3, 10], [2, 12], [2, 11], [0, 13], [1, 13]]
        # # gamelib.debug_write("spawning stationary units on defense lines and upgrading based on priorities")

        # corner3 = [[0, 13], [1, 13], [3, 12], [3, 11]]
        # corner4 = [[27, 13], [26, 13], [24, 12], [24, 11]]

        # turret_protect_locations = [[12, 5], [15, 5]]
        # v_turret = [[4, 9], [8, 5], [22, 11], [10, 5], [12, 7], [14, 9]]
        # middle_turrets = [[7, 7], [8, 8], [17, 8], [19, 8]]

        # locations_to_upgrade = turret_protect_locations + corner3 + middle_turrets + v_turret + corner4 + [[3, 12], [24, 12], [7, 7], [8, 8]]
        # locations_to_spawn = corner4 + middle_turrets + v_turret

        # if game_state.turn_number >= 2 and self.scored_on_locations:
        #     breach_location = self.scored_on_locations[-1]
        #     corner3 = self.prioritize_turret_positions(breach_location, corner3)
        #     corner4 = self.prioritize_turret_positions(breach_location, corner4)
        #     extended_left_corner = self.prioritize_turret_positions(breach_location, extended_left_corner)
        #     turret_protect_locations = self.prioritize_turret_positions(breach_location, turret_protect_locations)
        #     v_turret = self.prioritize_turret_positions(breach_location, v_turret)
        #     middle_turrets = self.prioritize_turret_positions(breach_location, middle_turrets)
        #     locations_to_upgrade = self.prioritize_turret_positions(breach_location, locations_to_upgrade)
        #     locations_to_spawn = self.prioritize_turret_positions(breach_location, locations_to_spawn)

        # # print the health damage
        # gamelib.debug_write("Health damage: {}".format(self.health_damage(game_state)))   
        
        #     game_state.attempt_spawn(TURRET, corner3)
        #     # game_state.attempt_upgrade(extended_left_corner)
        #     game_state.attempt_spawn(SUPPORT, support_locations)
        #     game_state.attempt_spawn(TURRET, turret_protect_locations)
        #     game_state.attempt_upgrade(support_locations)
        #     game_state.attempt_spawn(TURRET, locations_to_spawn)
        # else:
        # if game_state.turn_number >= 5:
        #     self.prioritize_upgrade_list(game_state, locations_to_upgrade) 

        # # in this current move, whatever turrets we currently spawn, check if they are in cache.
        # # if present, we won't spawn them, 
        # # if present, we spawn them and add them to cache.
        # # also those turrets which deal some damage, we make them most recently used in cache.
        # # then if we want to upgrade then after some turns, we will remove the least recently used turrets from the cache.
        
        # # in the lru, 
        


        # game_state.attempt_spawn(TURRET, corner3)
        # game_state.attempt_spawn(SUPPORT, support_locations)
        # game_state.attempt_spawn(TURRET, turret_protect_locations)
        # game_state.attempt_upgrade(support_locations)
        # game_state.attempt_spawn(TURRET, locations_to_spawn)
        # game_state.attempt_spawn(TURRET, extended_left_corner)
        # game_state.attempt_upgrade(locations_to_spawn)
        # game_state.attempt_upgrade(extended_left_corner)

        # attack_position, _ = self.get_optimal_attack(game_state)
        # threshold = 5
        # if self.health_damage(game_state) < 2:
        #     threshold += 2
        # if game_state.get_resource(MP) >= threshold:
        #     self.attack_count += 1
        #     # gamelib.debug_write('Enough resources, now spawn the army')
        #     game_state.attempt_spawn(SCOUT, attack_position, 1000)
        #     # game_state.attempt_spawn(DEMOLISHER, attack_position, 1)
        #     # game_state.attempt_spawn(SCOUT, attack_position, 10)

        # # game_state.attempt_upgrade([3, 12])
        # # game_state.attempt_upgrade([24, 12])
        # # game_state.attempt_upgrade([[7, 7], [8, 8]])
        # game_state.attempt_upgrade(v_turret)


        # after adding all the turrets, we will check what all turrets dealt damage and make them most recently used
        # in the cache.

        # remove the died turrets from the cache 
        for turret in self.lru_cache.cache.keys():
            if game_state.contains_stationary_unit([turret[0], turret[1]]) == False:
                self.lru_cache.remove_existing_turret(turret[0], turret[1])
                if turret in self.prev_turret_health:
                    del self.prev_turret_health[turret]

        # now we will check which turrets dealt damage and make them most recently used in the cache.
        for turret in self.lru_cache.cache.keys():
            x,y = turret

            current_health_of_turret = 0
            for unit in game_state.game_map[x,y]:
                if unit.stationary:
                    current_health_of_turret = unit.health
                    break

            prev_health_of_turret = self.prev_turret_health.get(turret, 0)
            damage_dealt = prev_health_of_turret - current_health_of_turret

            if damage_dealt > 0:
                self.lru_cache.make_most_recently_used(x,y)

            self.prev_turret_health[turret] = current_health_of_turret


        if game_state.turn_number == 0:
            self.custom_spawn_turret(game_state, [[3, 12], [24, 12], [7, 7], [8, 8]])
        elif game_state.turn_number == 1:
            self.custom_spawn_turret(game_state, [4,3], [23,3], [6,4], [21,4])
        elif game_state.turn_number == 2:
            self.custom_spawn_turret(game_state, [5,5], [20,5], [7,6], [19,6])

        # print the current turret locations in the cache and the order in which they are stored in each turn
        gamelib.debug_write("Turret cache: {}".format(self.lru_cache.cache))
        gamelib.debug_write("Turret order: {}".format(self.lru_cache.order))


            

        

            


if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()