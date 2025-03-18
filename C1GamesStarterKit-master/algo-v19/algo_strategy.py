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
        # gamelib.debug_write('Random seed: {}'.format(seed))
        self.attack_count = 0
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
        self.alt_attack = 0
        self.prev_enemy_health = None
        self.enemy_health_change = [5]

    def on_turn(self, turn_state):
        game_state = gamelib.GameState(self.config, turn_state)

        current_enemy_health = game_state.enemy_health
        if self.prev_enemy_health is not None:
            self.enemy_health_change.append(self.prev_enemy_health - current_enemy_health)

        self.prev_enemy_health = current_enemy_health
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
        # if equal equal eucledian distance, we want the middle y positions first
        return sorted(positions, key=lambda pos: (self.euclidean_distance_line(pos, line), abs(pos[1] - 9)))

    def get_optimal_attack(self, game_state):
        attack_positions = [[3,10],[4,9],[5,8],[6,7],[7,6],[8,5],[9,4],[10,3],[11,2],[12,1],[13,0],[14,0],[15,1],[16,2],[17,3],[18,4],[19,5],[20,6],[21,7],[22,8],[23,9],[24,10]]
        attack_positions = attack_positions[::4]
        optimal_position = None
        minimal_damage = float('inf')

        if game_state.turn_number==0:
            posns=[[20,6],[13,0],[6,7],[17,3]]
            random.shuffle(posns)
            optimal_position=posns[0]
            if optimal_position[0]>13:
                self.alt_attack=1
            else:
                self.alt_attack=0
            return optimal_position, None
            
        paths=[]
        for position in attack_positions:
            path = game_state.find_path_to_edge(position)
            if not path:
                continue

            if path[-1][0]+path[-1][1] != 41 and path[-1][1]-path[-1][0] != 14:
                    continue

            total_damage = sum(attacker.damage_i for path_location in path for attacker in game_state.get_attackers(path_location, 0))

            # gamelib.debug_write(f"Position {position}: Total damage: {total_damage}")

            paths.append([position,total_damage])

        top3=sorted(paths,key=lambda x: x[1])[:3]
        if top3:
            if self.alt_attack==0:
                ## find the ith path among top3 with least damage, with top3[i][0][0]>13
                found=0
                for i in range(len(top3)):
                    if top3[i][0][0]>13:
                        optimal_position=top3[i][0]
                        found=1
                        break
                if found:
                    self.alt_attack=1
                    return optimal_position, None
                else:
                    return top3[0][0], None
                
            else:
                ## find the ith path among top3 with least damage, with top3[i][0][0]>13
                found=0
                for i in range(len(top3)):
                    if top3[i][0][0]<=13:
                        optimal_position=top3[i][0]
                        found=1
                        break
                if found:
                    self.alt_attack=0
                    return optimal_position, None
                else:
                    return top3[0][0], None
                
        ## if path not found, select position randomly from [20,6],[13,0],[6,7] and [17,3]
        ## and set self.alt_attack accordingly
        posns=[[20,6],[13,0],[6,7],[17,3]]
        random.shuffle(posns)
        optimal_position=posns[0]
        if optimal_position[0]>13:
            self.alt_attack=1
        else:
            self.alt_attack=0

        # print the top 3 positions
        gamelib.debug_write(f"Top 3 positions: {top3}")
        # print the self.altattack
        gamelib.debug_write(f"Alt attack: {self.alt_attack}")
        return optimal_position, None

    def get_optimal_attack_2(self, game_state):
        if game_state.turn_number==0 or game_state.turn_number>1:
            attack_positions = [[3,10],[4,9],[5,8],[6,7],[7,6],[8,5],[9,4],[10,3],[11,2],[12,1],[13,0],[14,0],[15,1],[16,2],[17,3],[18,4],[19,5],[20,6],[21,7],[22,8],[23,9],[24,10]]
            attack_positions = attack_positions[::4]
            optimal_position = None
            minimal_damage = float('inf')

            if game_state.turn_number==0:
                posns=[[20,6],[13,0],[6,7],[14,0]]
                random.shuffle(posns)
                optimal_position=posns[0]
                if optimal_position[0]>13:
                    self.alt_attack=1
                else:
                    self.alt_attack=0
                return optimal_position, None
                
            paths=[]
            for position in attack_positions:
                path = game_state.find_path_to_edge(position)
                if not path:
                    continue

                if path[-1][0]+path[-1][1] != 41 and path[-1][1]-path[-1][0] != 14:
                        continue

                total_damage = sum(attacker.damage_i for path_location in path for attacker in game_state.get_attackers(path_location, 0))

                # gamelib.debug_write(f"Position {position}: Total damage: {total_damage}")

                paths.append([position,total_damage])

            top3=sorted(paths,key=lambda x: x[1])[:3]
            if top3:
                if self.alt_attack==0:
                    ## find the ith path among top3 with least damage, with top3[i][0][0]>13
                    found=0
                    for i in range(len(top3)):
                        if top3[i][0][0]>13:
                            optimal_position=top3[i][0]
                            found=1
                            break
                    if found:
                        self.alt_attack=1
                        return optimal_position, None
                    else:
                        return top3[0][0], None
                    
                else:
                    ## find the ith path among top3 with least damage, with top3[i][0][0]>13
                    found=0
                    for i in range(len(top3)):
                        if top3[i][0][0]<=13:
                            optimal_position=top3[i][0]
                            found=1
                            break
                    if found:
                        self.alt_attack=0
                        return optimal_position, None
                    else:
                        return top3[0][0], None
                    
            ## if path not found, select position randomly from [20,6],[13,0],[6,7] and [17,3]
            ## and set self.alt_attack accordingly
            posns=[[20,6],[13,0],[6,7],[14,0]]
            random.shuffle(posns)
            optimal_position=posns[0]
            if optimal_position[0]>13:
                self.alt_attack=1
            else:
                self.alt_attack=0

            # print the top 3 positions
            gamelib.debug_write(f"Top 3 positions: {top3}")
            # print the self.altattack
            gamelib.debug_write(f"Alt attack: {self.alt_attack}")
            return optimal_position, None
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
                        total_health += attacker.damage_i

                # gamelib.debug_write(f"Position {position}: Total damage: {total_health}")
                
                # Store this path option
                path_options.append((position, total_health, total_supports))

            # Sort paths by total turret health (ascending)
            curr_support = 0
            if path_options:
                path_options.sort(key=lambda x: x[1])

                # Take the top 5 paths (or fewer if less than 5 are available)
                top_paths = path_options[:3]

                # Find the path in top paths wiht max support structures
                top_paths.sort(key=lambda x: x[2], reverse=True)

                found=0
                for i in range(len(top_paths)):
                    if top_paths[i][2] > curr_support:
                        optimal_position, _, curr_support = top_paths[i]
                        found=1

                if not found:
                    optimal_position, _, _ = top_paths[0]
            else:
                posns=[[20,6],[13,0],[6,7],[14,0]]
                random.shuffle(posns)
                optimal_position=posns[0]
            
            # set self.alt_attack accordingly
            if optimal_position[0]>13:
                self.alt_attack=1
            else:
                self.alt_attack=0
        
            # gamelib.debug_write(f"Optimal attack position: {optimal_position}, minimal damage: {minimal_health}")
            return optimal_position, None

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

        support_locations = [[13,5],[14,5],[13,6],[14,6]]
        turret_protect_locations = [[12,4],[15,4],[12,7],[15,7]]

        wall_left = [0,13]
        wall_right = [27,13]

        row_1 = [[1,13],[2,13],[3,13],[4,13],[7,13],[10,13],[13,13],[16,13],[19,13],[22,13],[24,13],[25,13],[26,13]]
        row_2 = [[3,11],[6,11],[9,11],[12,11],[15,11],[18,11],[21,11],[24,11]]
        row_1point5 = [[4,12],[8,12],[12,12],[16,12],[20,12],[24,12]]
        turrets_to_spawn = row_1 + row_2 + row_1point5

        if self.prev_delete:

            number_of_supports = 0

            for loc in support_locations:
                if game_state.contains_stationary_unit(loc):
                    number_of_supports += 1

            if number_of_supports < 3:
                for loc in support_locations:
                    if game_state.attempt_spawn(SUPPORT, loc):
                        break
            
            self_breach_location = self.get_self_breach_positions(game_state)
            turrets_to_spawn = self.ultra_prioritize_turret_positions(self_breach_location, turrets_to_spawn)
            spawn = 0
            
            for loc in turrets_to_spawn:
                if game_state.attempt_spawn(TURRET, loc):
                    spawn += 1
                    if spawn >= 2:
                        break
            
            self.prev_delete = False
        
        if game_state.turn_number >= 2 and self.scored_on_locations:
            enemy_line_positions = [[0, 14], [1, 14], [2, 14]]
            our_turret_positions = [[0, 13], [1, 13], [2, 13]]

            continuous_enemy_line = all(
                game_state.contains_stationary_unit(pos) for pos in enemy_line_positions
            )

            if continuous_enemy_line:
                if game_state.contains_stationary_unit([3, 14]):
                    for turret_pos in our_turret_positions:
                        game_state.attempt_remove(turret_pos)
                else:
                    game_state.attempt_remove([0, 13])
                    game_state.attempt_remove([1, 13])
                
                self.prev_delete = True
            
            enemy_line_positions = [[27, 14], [26, 14], [25, 14]]
            our_turret_positions = [[27, 13], [26, 13], [25, 13]]

            continuous_enemy_line = all(
                game_state.contains_stationary_unit(pos) for pos in enemy_line_positions
            )

            if continuous_enemy_line:
                if game_state.contains_stationary_unit([24, 14]):
                    for turret_pos in our_turret_positions:
                        game_state.attempt_remove(turret_pos)
                else:
                    game_state.attempt_remove([27, 13])
                    game_state.attempt_remove([26, 13])
            
                self.prev_delete = True

            if game_state.turn_number % 4 == 3:
                self_breach_location = self.get_self_breach_positions(game_state)
                # gamelib.debug_write("Self breach location: {}".format(self_breach_location))
                turrets_to_spawn = self.ultra_prioritize_turret_positions(self_breach_location, turrets_to_spawn)
            else:
                enemy_breach_location = self.scored_on_locations[-1]
                turrets_to_spawn = self.ultra_prioritize_turret_positions(enemy_breach_location, turrets_to_spawn)

        if game_state.turn_number < 2:
            game_state.attempt_spawn(SUPPORT, support_locations)
            game_state.attempt_spawn(TURRET, turret_protect_locations)
            game_state.attempt_upgrade(support_locations)
            game_state.attempt_upgrade(turret_protect_locations)
        else:
            
            if turrets_to_spawn[0] == [1,13] or turrets_to_spawn[1] == [1,13]:
                game_state.attempt_spawn(WALL, wall_left)
            if turrets_to_spawn[0] == [25,13] or turrets_to_spawn[1] == [25,13]:
                game_state.attempt_spawn(WALL, wall_right)

            game_state.attempt_spawn(TURRET, turrets_to_spawn)
            num_of_turrets = 0
            for loc in turrets_to_spawn:
                if game_state.contains_stationary_unit(loc):
                    num_of_turrets += 1
                
            if num_of_turrets > 20:
                for loc in support_locations:
                    if game_state.attempt_spawn(SUPPORT, loc):
                        break

        # attack now::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
        # attack now::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
        # attack now::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

        attack_pos, _ = self.get_optimal_attack_2(game_state)

        threshold = 5

        if self.enemy_health_change[-1] < 2 and game_state.my_health > 5:
            threshold += 2

        if game_state.get_resource(MP) >= threshold:
            game_state.attempt_spawn(SCOUT, attack_pos, 1000)
        
        #attack ends::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
        #attack ends::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
        #attack ends::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::


if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()