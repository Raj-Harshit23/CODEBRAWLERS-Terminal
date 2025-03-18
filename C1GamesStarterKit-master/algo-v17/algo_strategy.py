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
            # if not in order then remove from cache only
            if key not in self.order:
                del self.cache[key]
            else:
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
        self.prev_delete = False

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
    
    def euclidean_distance_line(self, point1, line):
        # line is a list of points
        dist = 10000
        for point in line:
            dist = min(dist, self.euclidean_distance(point1, point))
        return dist
    
    def give_points_along_diagonal(self, locx, locy):
        points = []
        
        if locx < 14:
            i = 0
            while locy + i <= 13:
                points.append([locx + i, locy + i])
                i += 1
        else:
            i = 0
            while locy + i <= 13:
                points.append([locx - i, locy + i])
                i += 1
        
        # print original points and the points along the diagonal
        # print(f"Original points: {locx, locy}")
        # print(f"Points along the diagonal: {points}")

        return points
    
    def prioritize_turret_positions(self, breach_location, positions):
        return sorted(positions, key=lambda pos: self.euclidean_distance(pos, breach_location))
    
    def ultra_prioritize_turret_positions(self, breach_locations, positions):
        line = self.give_points_along_diagonal(breach_locations[0], breach_locations[1])
        return sorted(positions, key=lambda pos: self.euclidean_distance_line(pos, line))

    def get_optimal_attack(self, game_state):
        attack_positions = [[3, 10], [4, 9], [5, 8], [6, 7], [7, 6], [8, 5], [9, 4], [10, 3], [11, 2], [12, 1], [13, 0], [14, 0], [15, 1], [16, 2], [17, 3], [18, 4], [19, 5], [20, 6], [21, 7], [22, 8], [23, 9], [24, 10]]
        # take alternate positions in attack positions
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

    def custom_spawn_turret(self, game_state, turret_list, to_upgrade):
        for turret in turret_list:
            if self.lru_cache.check_turret(turret[0],turret[1]):
                # add debug statement
                # gamelib.debug_write("Turret already present at location: {}".format(turret))
                continue
            else:
                # gamelib.debug_write("Spawning turret at location: {}".format(turret))
                if game_state.attempt_spawn(TURRET, turret):
                    if to_upgrade and self.prev_delete:
                        game_state.attempt_upgrade(turret)
                        to_upgrade = False
            
                    self.lru_cache.make_turret_lru(turret[0],turret[1])
                    self.lru_cache.make_most_recently_used(turret[0],turret[1])
                    self.prev_turret_health[(turret[0],turret[1])] = 70

    def newalgo(self, game_state):

        # remove the died turrets from the cache 

        # before starting this turn, remove the dead turrets
        to_be_removed = []
        for turret in self.lru_cache.cache.keys():
            if game_state.contains_stationary_unit([turret[0], turret[1]]) == False:
                to_be_removed.append(turret)

        for turret in to_be_removed:
            self.lru_cache.remove_existing_turret(turret[0], turret[1])
            if turret in self.prev_turret_health:
                del self.prev_turret_health[turret]

        # now we will check which turrets dealt damage and make them most recently used in the cache.
        # to make mru
        to_make_mru = []    
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
                to_make_mru.append(turret)

            self.prev_turret_health[turret] = current_health_of_turret

        for turret in to_make_mru:
            self.lru_cache.make_most_recently_used(turret[0], turret[1])

        # if game_state.turn_number == 0:
        #     self.custom_spawn_turret(game_state, [[11,8],[12,8],[13,8],[14,8]])
        # elif game_state.turn_number == 1:
        #     self.custom_spawn_turret(game_state, [[18,10],[19,10],[20,10],[21,10]])
        # elif game_state.turn_number == 2:
        #     self.custom_spawn_turret(game_state, [[1,12],[2,12],[3,12],[4,12]])


        support_locations = [[13, 6], [14, 6], [13, 5],[14,5]]
        extended_left_corner = [[5, 8], [5, 9], [5, 10], [5, 11], [5, 12], [4, 13], [4, 11], [4, 10], [4, 9], [3, 13], [3, 12], [3, 10], [2, 12], [2, 11], [0, 13], [1, 13]]
        # gamelib.debug_write("spawning stationary units on defense lines and upgrading based on priorities")

        corner3 = [[0, 13], [1, 13], [3, 12], [3, 11]]
        corner4 = [[27, 13], [26, 13], [24, 12], [24, 11]]

        turret_protect_locations = [[12, 6], [15, 6], [12,4],[15,4]]
        v_turret = [[4, 9], [8, 5], [22, 11], [10, 5], [12, 7], [14, 9]]
        middle_turrets = [[7, 7], [8, 8], [17, 8], [19, 8]]

        locations_to_upgrade = turret_protect_locations + corner3 + middle_turrets + v_turret + corner4 + [[3, 12], [24, 12], [7, 7], [8, 8]]
        locations_to_spawn = corner4 + middle_turrets + v_turret

        new_corner3 = corner3
        new_corner4 = corner4
        vleft_mid = [[6,9],[8,9],[8,7]]
        vright_mid = [[19,9],[21,9],[21,7]]

        vleft_bottom = [[9,5],[11,5],[11,3]]
        vright_bottom = [[16,5],[18,5],[18,3]]

        vleft_midmid = [[10,9],[10,7],[13,9]]
        vright_midmid = [[17,9],[17,7],[15,9]]

        new_turret_protect = turret_protect_locations

        bottom_2 = [[13,2],[14,2]]

        vleft_top = [[5,10],[5,12],[7,12]]
        vright_top = [[22,10],[20,12],[22,12]]

        mid_2 = [[13,8],[14,8]]

        top_2 = [[13,11],[14,11]]

        to_be_upgraded_max_prio = [[7,12],[8,9],[12,9],[15,9],[19,9],[12,6],[15,6],[10,7],[17,7],[5,12],[22,12],[1,13],[26,13]]    

        to_be_spawned_new = new_corner3 + new_corner4 + vleft_mid + vright_mid + vleft_bottom + vright_bottom + vleft_midmid + vright_midmid + new_turret_protect + bottom_2 + vleft_top + vright_top + mid_2 + top_2

        if game_state.turn_number >= 2 and self.scored_on_locations:
            breach_location = self.scored_on_locations[-1]
            new_corner3 = self.ultra_prioritize_turret_positions(breach_location, new_corner3)
            new_corner4 = self.ultra_prioritize_turret_positions(breach_location, new_corner4)
            vleft_mid = self.ultra_prioritize_turret_positions(breach_location, vleft_mid)
            vright_mid = self.ultra_prioritize_turret_positions(breach_location, vright_mid)

            vleft_bottom = self.ultra_prioritize_turret_positions(breach_location, vleft_bottom)
            vright_bottom = self.ultra_prioritize_turret_positions(breach_location, vright_bottom)    

            vleft_midmid = self.ultra_prioritize_turret_positions(breach_location, vleft_midmid)
            vright_midmid = self.ultra_prioritize_turret_positions(breach_location, vright_midmid)

            new_turret_protect = self.ultra_prioritize_turret_positions(breach_location, new_turret_protect)

            bottom_2 = self.ultra_prioritize_turret_positions(breach_location, bottom_2)

            vleft_top = self.ultra_prioritize_turret_positions(breach_location, vleft_top)
            vright_top = self.ultra_prioritize_turret_positions(breach_location, vright_top)

            mid_2 = self.ultra_prioritize_turret_positions(breach_location, mid_2)

            top_2 = self.ultra_prioritize_turret_positions(breach_location, top_2)

            to_be_upgraded_max_prio = self.ultra_prioritize_turret_positions(breach_location, to_be_upgraded_max_prio)
            to_be_spawned_new = self.ultra_prioritize_turret_positions(breach_location, to_be_spawned_new)

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

        if self.prev_delete:
            # upgrade the max priority 1 turret
            upgraded = 0
            for loc in to_be_upgraded_max_prio:
                if game_state.attempt_upgrade(loc):
                    upgraded += 1
                if upgraded >= 1:
                    break
            # game_state.attempt_upgrade(to_be_upgraded_max_prio[0])

        if game_state.turn_number < 2:
            # self.custom_spawn_turret(game_state, new_corner3, 0)
            game_state.attempt_spawn(SUPPORT, support_locations)
            self.custom_spawn_turret(game_state, new_turret_protect, 0)
            game_state.attempt_upgrade(support_locations)
            game_state.attempt_upgrade(new_turret_protect)
        else:
            self.custom_spawn_turret(game_state, to_be_spawned_new, 0)
        
        # if not self.prev_delete:
        #     self.custom_spawn_turret(game_state, corner3, 0)

        # game_state.attempt_spawn(SUPPORT, support_locations)
        # if len(self.lru_cache.order) < 10:
        #     self.custom_spawn_turret(game_state, turret_protect_locations, 0)
        # game_state.attempt_upgrade(support_locations)

        # self.custom_spawn_turret(game_state, locations_to_spawn, 1)
        # self.custom_spawn_turret(game_state, extended_left_corner,1)
        # game_state.attempt_upgrade(locations_to_spawn)
        # game_state.attempt_upgrade(extended_left_corner)


        # removing 3 turrets with least priority
        if len(self.lru_cache.order) > 20:
            # remove the 3 least recently used turrets
            self.prev_delete = True
            # do not remove upgraded elements
            # do not remove support turrets
            removed = 0
            n = len(self.lru_cache.order)
            for i in range(n):
                # find the top element but dont pop from the lru
                x,y = self.lru_cache.order[i]
                # x, y = self.lru_cache.order.pop(0)
                if [x, y] in new_corner3:
                    continue
                if [x, y] in new_corner4:
                    continue
                if [x, y] in turret_protect_locations:
                    # add it to most recently used
                    # self.lru_cache.make_most_recently_used(x, y)
                    continue
                # if it is upgraded, then do not remove it
                # to_make_mru2 = []
                skip = False
                for unit in game_state.game_map[x, y]:
                    # skip = False
                    if unit.stationary and unit.upgraded:
                        # self.lru_cache.make_most_recently_used(x, y)
                        skip = True
                        break
                    if skip:
                        break
                if skip:
                    continue

                removed += 1

                game_state.attempt_remove([x, y])
                # self.lru_cache.remove_existing_turret(x, y)
                if turret in self.prev_turret_health:
                    del self.prev_turret_health[(x, y)]

                if removed >= 2:
                    break
        else:
            self.prev_delete = False



        # attack now::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
        # attack now::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
        # attack now::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

        attack_pos, _ = self.get_optimal_attack(game_state)

        threshold = 5

        if game_state.get_resource(MP) >= threshold:
            game_state.attempt_spawn(SCOUT, attack_pos, 1000)
        
        #attack ends::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
        #attack ends::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
        #attack ends::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

        # print the current turret locations in the cache and the order in which they are stored in each turn
        # gamelib.debug_write("Turret cache: {}".format(self.lru_cache.cache))
        gamelib.debug_write("Turret order: {}".format(self.lru_cache.order))

            


if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()