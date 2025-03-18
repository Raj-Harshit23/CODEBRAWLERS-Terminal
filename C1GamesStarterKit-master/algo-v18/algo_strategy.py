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
        self.last_destroyed_enemy_structs = []

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

            # gamelib.debug_write(f"Position {position}: Total damage: {total_damage}")

            if total_damage <= minimal_damage:
                minimal_damage = total_damage
                optimal_position = position
        # gamelib.debug_write(f"Optimal attack position: {optimal_position}, minimal damage: {minimal_damage}")
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

    def get_optimal_attack_2(self, game_state):
        if game_state.turn_number<0:
            attack_positions = [[3, 10], [4, 9], [5, 8], [6, 7], [7, 6], [8, 5], [9, 4], [10, 3], [11, 2], [12, 1], [13, 0], [14, 0], [15, 1], [16, 2], [17, 3], [18, 4], [19, 5], [20, 6], [21, 7], [22, 8], [23, 9], [24, 10]]
            ## only check each 3rd
            attack_positions = attack_positions[::4]
            optimal_position = [10,3]
            minimal_health = float('inf')

            ## create a copy of game state
            game_state_copy = gamelib.GameState(self.config, game_state.serialized_string)
            
            # Map of unit type indices to their string representation
            unit_type_map = {0: "WALL", 1: "SUPPORT", 2: "TURRET"}
            
            for (unit_type, x, y) in self.last_destroyed_enemy_structs:
                # Map 0->WALL,1->SUPPORT,2->TURRET  (based on the kit's indexing)
                if unit_type == 0:
                    game_state_copy.game_map.add_unit(WALL, [x, y], 1)
                elif unit_type == 1:
                    game_state_copy.game_map.add_unit(SUPPORT, [x, y], 1)
                elif unit_type == 2:
                    game_state_copy.game_map.add_unit(TURRET, [x, y], 1)

            # Rest of your function...
            for position in attack_positions:
                path = game_state_copy.find_path_to_edge(position)
                if not path:
                    continue 

                # ## only select the path which ends at enemy's edges
                if path[-1][0]+path[-1][1] != 41 and path[-1][1]-path[-1][0] != 14:
                    continue
                
                total_health = 0
                for path_location in path:
                    attackers = game_state_copy.get_attackers(path_location, 0)
                    
                    for attacker in attackers:
                        total_health += attacker.health

                # gamelib.debug_write(f"Position {position}: Total damage: {total_health}")

                if total_health <= minimal_health:
                    minimal_health = total_health
                    optimal_position = position

            if game_state.turn_number == 0:
                optimal_position = [20,6]
                    
            # gamelib.debug_write(f"Optimal attack position: {optimal_position}, minimal damage: {minimal_health}")
            return optimal_position, game_state_copy.find_path_to_edge(optimal_position)
        else:
            attack_positions = [[3, 10], [4, 9], [5, 8], [6, 7], [7, 6], [8, 5], [9, 4], [10, 3], [11, 2], [12, 1], [13, 0], [14, 0], [15, 1], [16, 2], [17, 3], [18, 4], [19, 5], [20, 6], [21, 7], [22, 8], [23, 9], [24, 10]]
            ## only check each 3rd
            attack_positions = attack_positions[::4]
            optimal_position = [10,3]
            optimal_path=None
            minimal_health = float('inf')

            ## create a copy of game state
            game_state_copy = gamelib.GameState(self.config, game_state.serialized_string)

            # Map of unit type indices to their string representation
            unit_type_map = {0: "WALL", 1: "SUPPORT", 2: "TURRET"}

            for (unit_type, x, y) in self.last_destroyed_enemy_structs:
                # Map 0->WALL,1->SUPPORT,2->TURRET  (based on the kit's indexing)
                if unit_type == 0:
                    game_state_copy.game_map.add_unit(WALL, [x, y], 1)
                elif unit_type == 1:
                    game_state_copy.game_map.add_unit(SUPPORT, [x, y], 1)
                elif unit_type == 2:
                    game_state_copy.game_map.add_unit(TURRET, [x, y], 1)

            ## iterate over enemy,s map, if a stationary structure is found and it is support
            ## keep an empty set or dict initially(whichever is faster)
            ## then add all the positions in euclidean distnace<=3.5 of the support to the set
            # Create a set to store positions near enemy support structures
            support_range_positions = set()

            # Only scan enemy territory (right half of the arena)
            for x in range(28):
                for y in range(14,28):
                    units = game_state_copy.game_map[x, y]
                    if units:
                        for unit in units:
                            # Check if it's an enemy support structure
                            if unit.unit_type == SUPPORT and unit.player_index == 1:
                                # Only iterate within a 6×6 square centered at the support (covers 3.5 radius)
                                for pos_x in range(max(0, x-4), min(game_state_copy.ARENA_SIZE, x+5)):
                                    for pos_y in range(max(0, y-4), min(game_state_copy.ARENA_SIZE, y+5)):
                                        # Check if this position is within 3.5 units of the support
                                        if self.euclidean_distance([x, y], [pos_x, pos_y]) <= 3.5:
                                            support_range_positions.add((pos_x, pos_y))

            # gamelib.debug_write(f"Found {len(support_range_positions)} positions within range of enemy supports")


            # List to store tuples of (position, health, path)
            path_options = []

            # Rest of your function...
            for position in attack_positions:
                path = game_state_copy.find_path_to_edge(position)
                if not path:
                    continue 

                # ## only select the path which ends at enemy's edges
                if path[-1][0]+path[-1][1] != 41 and path[-1][1]-path[-1][0] != 14:
                    continue
                
                total_health = 0
                total_supports = 0
                for path_location in path:
                    if tuple(path_location) in support_range_positions:
                        total_supports += 1
                    attackers = game_state_copy.get_attackers(path_location, 0)
                    
                    for attacker in attackers:
                        total_health += attacker.health

                # gamelib.debug_write(f"Position {position}: Total damage: {total_health}")
                
                # Store this path option
                path_options.append((position, total_health, total_supports))

            # Sort paths by total turret health (ascending)
            if path_options:
                path_options.sort(key=lambda x: x[1])

                # Take the top 5 paths (or fewer if less than 5 are available)
                top_paths = path_options[:3]

                # Find the path in top paths wiht max support structures
                top_paths.sort(key=lambda x: x[2], reverse=True)
                optimal_position, _, _ = top_paths[0]
            else:
                optimal_position = [20,6]

            if game_state.turn_number == 0:
                optimal_position = [20,6]
        
            # gamelib.debug_write(f"Optimal attack position: {optimal_position}, minimal damage: {minimal_health}")
            return optimal_position, optimal_path

    def get_self_breach_positions(self, game_state):

        # attack_positions = [[3, 10], [4, 9], [5, 8], [6, 7], [7, 6], [8, 5], [9, 4], [10, 3], [11, 2], [12, 1], [13, 0], [14, 0], [15, 1], [16, 2], [17, 3], [18, 4], [19, 5], [20, 6], [21, 7], [22, 8], [23, 9], [24, 10]]
        # make these attack positions enemy attack positions
        attack_positions = [[27,14],[26,15],[25,16],[24,17],[23,18],[22,19],[21,20],[20,21],[19,22],[18,23],[17,24],[16,25],[15,26],[14,27],[13,27],[12,26],[11,25],[10,24],[9,23],[8,22],[7,21],[6,20],[5,19],[4,18],[3,17],[2,16],[1,15],[0,14]]
        ## only check each 3rd  
        attack_positions = attack_positions[::4]
        optimal_position = [21,20]
        minimal_health = float('inf')

        ## create a copy of game state
        game_state_copy = gamelib.GameState(self.config, game_state.serialized_string)
        
        # Map of unit type indices to their string representation
        # unit_type_map = {0: "WALL", 1: "SUPPORT", 2: "TURRET"}
        
        # for (unit_type, x, y) in self.last_destroyed_enemy_structs:
        #     # Map 0->WALL,1->SUPPORT,2->TURRET  (based on the kit's indexing)
        #     if unit_type == 0:
        #         game_state_copy.game_map.add_unit(WALL, [x, y], 1)
        #     elif unit_type == 1:
        #         game_state_copy.game_map.add_unit(SUPPORT, [x, y], 1)
        #     elif unit_type == 2:
        #         game_state_copy.game_map.add_unit(TURRET, [x, y], 1)

        # Rest of your function...
        for position in attack_positions:
            path = game_state_copy.find_path_to_edge(position)
            if not path:
                continue 

            # ## only select the path which ends at enemy's edges
            # if path[-1][0]+path[-1][1] != 13 and path[-1][0]-path[-1][1] != 14:
            #     continue
            
            total_health = 0
            for path_location in path:
                attackers = game_state_copy.get_attackers(path_location, 1)
                
                for attacker in attackers:
                    total_health += attacker.damage_i

            # gamelib.debug_write(f"Position {position}: Total damage: {total_health}")

            if total_health <= minimal_health:
                minimal_health = total_health
                optimal_position = position

                
        # gamelib.debug_write(f"Optimal attack position: {optimal_position}, minimal damage: {minimal_health}")
        return game_state_copy.find_path_to_edge(optimal_position)[-1]

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

        support_locations = [[13, 6], [14, 6], [13, 5],[14,5]]
        turret_protect_locations = [[12, 7], [15, 7], [12,4],[15,4]]

        left_corner = [[0, 13], [1, 13], [3, 12], [3, 11]]
        left_ext_corner = [[3,11],[3,12],[3,13]]
        left_diag1 = [[4,9],[6,11],[8,13]]
        left_diag2 = [[6,8],[8,10],[10,12]]
        left_diag3 = [[8,7],[10,9],[12,11]]
        left_diag4 = [[9,5],[11,7],[13,9]]

        right_corner = [[27, 13], [26, 13], [24, 12], [24, 11]]
        right_ext_corner = [[24,11],[24,12],[24,13]]
        right_diag1 = [[23,9],[21,11],[19,13]]
        right_diag2 = [[21,8],[19,10],[17,12]]
        right_diag3 = [[19,7],[17,9],[15,11]]
        right_diag4 = [[18,5],[16,7],[14,9]]

        middle2 = [[13,8],[14,8]]
        bottom4 = [[11,3], [16,3],[13,2],[14,2]]

        turrets_to_spawn = left_corner + left_ext_corner + left_diag1 + left_diag2 + left_diag3 + left_diag4 + right_corner + right_ext_corner + right_diag1 + right_diag2 + right_diag3 + right_diag4 + middle2 + bottom4
        to_be_upgraded_max_prio = [[2,12],[25,12],[13,9],[8,10],[19,10],[12,6],[15,6],[12,4],[15,4]]
        if game_state.turn_number >= 2 and self.scored_on_locations:
            # self_breach_location = self_breach[0]
            
            if game_state.turn_number % 3 == -1:
                self_breach_location = self.get_self_breach_positions(game_state)
                gamelib.debug_write("Self breach location: {}".format(self_breach_location))
                turrets_to_spawn = self.ultra_prioritize_turret_positions(self_breach_location, turrets_to_spawn)
            else:
                enemy_breach_location = self.scored_on_locations[-1]
                turrets_to_spawn = self.ultra_prioritize_turret_positions(enemy_breach_location, turrets_to_spawn)

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
            game_state.attempt_spawn(SUPPORT, support_locations)
            self.custom_spawn_turret(game_state, turret_protect_locations, 0)
            game_state.attempt_upgrade(support_locations)
            game_state.attempt_upgrade(turret_protect_locations)
        else:
            number_of_supports = 0
            for loc in support_locations:
                if game_state.contains_stationary_unit(loc):
                    number_of_supports += 1
            if number_of_supports < 4:
                game_state.attempt_spawn(SUPPORT, support_locations)

            number_of_upgraded_supports = 0
            for loc in support_locations:
                for unit in game_state.game_map[loc[0],loc[1]]:
                    if unit.stationary and unit.upgraded:
                        number_of_upgraded_supports += 1
                        break
            if number_of_upgraded_supports < 3:
                for loc in support_locations:
                    if game_state.attempt_upgrade(loc):
                        break
                # game_state.attempt_upgrade(support_locations)

            self.custom_spawn_turret(game_state, turrets_to_spawn, 0)

        # removing 3 turrets with least priority

        if len(self.lru_cache.order) <0:
            # remove the 2 least recently used turrets
            self.prev_delete = False
            # do not remove upgraded elements
            # do not remove support turrets
            removed = 0
            n = len(self.lru_cache.order)
            for i in range(n):
                # find the top element but dont pop from the lru
                x,y = self.lru_cache.order[i]
                # x, y = self.lru_cache.order.pop(0)
                if [x, y] in left_corner:
                    continue
                if [x, y] in right_corner:
                    continue
                if [x,y] in left_ext_corner:
                    continue
                if [x,y] in right_ext_corner:
                    continue
                if [x,y] in middle2:
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
                self.prev_delete = True

                game_state.attempt_remove([x, y])
                # self.lru_cache.remove_existing_turret(x, y)
                if turret in self.prev_turret_health:
                    del self.prev_turret_health[(x, y)]

                if removed >= 3:
                    break
        else:
            self.prev_delete = False



        # attack now::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
        # attack now::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
        # attack now::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

        attack_pos, _ = self.get_optimal_attack_2(game_state)

        threshold = 5

        if game_state.get_resource(MP) >= threshold:
            game_state.attempt_spawn(SCOUT, attack_pos, 1000)
        
        #attack ends::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
        #attack ends::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
        #attack ends::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

        # print the current turret locations in the cache and the order in which they are stored in each turn
        # gamelib.debug_write("Turret cache: {}".format(self.lru_cache.cache))
        # gamelib.debug_write("Turret order: {}".format(self.lru_cache.order))

if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()