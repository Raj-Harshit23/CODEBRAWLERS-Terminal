import gamelib
import random
import math
import warnings
from sys import maxsize
import json
import heapq

"""
Advanced C1 Terminal Algorithm
This algorithm implements dynamic defense building, strategic offense,
and intelligent resource management to create a highly competitive bot.
"""

class AlgoStrategy(gamelib.AlgoCore):
    def __init__(self):
        super().__init__()
        seed = random.randrange(maxsize)
        random.seed(seed)
        gamelib.debug_write('Random seed: {}'.format(seed))
        
        # Strategy state tracking
        self.scored_on_locations = []
        self.enemy_scored_locations = []
        self.attack_log = {}
        self.defense_log = {}
        self.last_attack_phase = 0
        self.enemy_formation = "unknown"
        self.enemy_attack_style = "unknown"
        
        # Defense formations
        self.defense_v_patterns = {
            "early_game": [
                [11, 7], [12, 7], [13, 7], [14, 7], [15, 7], [16, 7],
                [10, 8], [11, 8], [12, 8], [13, 8], [14, 8], [15, 8], [16, 8], [17, 8],
                [9, 9], [10, 9], [11, 9], [12, 9], [13, 9], [14, 9], [15, 9], [16, 9], [17, 9], [18, 9],
                [8, 10], [9, 10], [10, 10], [11, 10], [12, 10], [13, 10], [14, 10], [15, 10], [16, 10], [17, 10], [18, 10], [19, 10]
            ],
            "mid_game": [
                [0, 13], [1, 12], [2, 11], [3, 10], [4, 9], [5, 8], [6, 7],
                [27, 13], [26, 12], [25, 11], [24, 10], [23, 9], [22, 8], [21, 7]
            ],
            "funnel": [
                [7, 11], [8, 10], [9, 9], [10, 8], [11, 7],
                [20, 11], [19, 10], [18, 9], [17, 8], [16, 7],
                [12, 6], [13, 5], [14, 5], [15, 6]
            ]
        }
        
        # Turret positions
        self.turret_positions = [
            [3, 12], [6, 11], [9, 8], [13, 6], [14, 6], [18, 8], [21, 11], [24, 12],
            [10, 7], [17, 7], [12, 8], [15, 8], [11, 10], [16, 10]
        ]
        
        # Support positions (behind turrets)
        self.support_positions = [
            [3, 11], [6, 10], [9, 7], [13, 5], [14, 5], [18, 7], [21, 10], [24, 11],
            [10, 6], [17, 6], [12, 7], [15, 7]
        ]
        
        # Critical points (high-value locations that need reinforcement)
        self.critical_points = [
            [13, 5], [14, 5], [10, 7], [17, 7], [3, 12], [24, 12]
        ]
        
        # Attack spawn points
        self.spawn_points = [
            [13, 0], [14, 0], [12, 1], [15, 1]
        ]
        
        # Initialize costs (will be set in on_game_start)
        self.wall_cost = 1
        self.support_cost = 4
        self.turret_cost = 3
        self.scout_cost = 1
        self.demolisher_cost = 3
        self.interceptor_cost = 3

    def on_game_start(self, config):
        """ 
        Read in config and perform initial setup
        """
        gamelib.debug_write('Configuring algo strategy...')
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
        
        # Set resource costs directly from config instead of creating GameUnit instances
        self.wall_cost = config["unitInformation"][0]["cost1"]
        self.support_cost = config["unitInformation"][1]["cost1"] 
        self.turret_cost = config["unitInformation"][2]["cost1"]
        self.scout_cost = config["unitInformation"][3]["cost2"]
        self.demolisher_cost = config["unitInformation"][4]["cost2"]
        self.interceptor_cost = config["unitInformation"][5]["cost2"]

    def on_turn(self, turn_state):
        """
        Main turn logic
        """
        game_state = gamelib.GameState(self.config, turn_state)
        gamelib.debug_write('Turn: {}'.format(game_state.turn_number))
        game_state.suppress_warnings(True)
        
        # Execute our strategy
        self.execute_strategy(game_state)
        
        game_state.submit_turn()

    def execute_strategy(self, game_state):
        """
        Coordinated strategy execution based on game phase
        """
        # Analyze game state
        game_phase = self.determine_game_phase(game_state)
        enemy_info = self.analyze_enemy(game_state)
        
        # Update strategy based on analyses
        self.update_strategy(game_state, game_phase, enemy_info)
        
        # Build defenses
        self.build_defense(game_state, game_phase, enemy_info)
        
        # Launch attacks
        if self.should_attack(game_state, game_phase):
            self.execute_attack(game_state, game_phase, enemy_info)

    def determine_game_phase(self, game_state):
        """
        Determine the current phase of the game
        """
        turn = game_state.turn_number
        if turn < 5:
            return "opening"
        elif turn < 15:
            return "early_game"
        elif turn < 30:
            return "mid_game"
        else:
            return "late_game"

    def analyze_enemy(self, game_state):
        """
        Analyze enemy defenses and attack patterns
        """
        enemy_info = {
            "defense_strength": 0,
            "turret_count": 0,
            "wall_count": 0,
            "support_count": 0,
            "front_line_strength": 0,
            "weak_points": [],
        }
        
        # Count enemy defensive structures
        for location in game_state.game_map:
            if game_state.contains_stationary_unit(location):
                for unit in game_state.game_map[location]:
                    if unit.player_index == 1:  # Enemy unit
                        enemy_info["defense_strength"] += 1
                        if unit.unit_type == TURRET:
                            enemy_info["turret_count"] += 1
                        elif unit.unit_type == WALL:
                            enemy_info["wall_count"] += 1
                        elif unit.unit_type == SUPPORT:
                            enemy_info["support_count"] += 1
                        
                        # Check if unit is in the front line (y-coordinate > 15)
                        if location[1] > 15:
                            enemy_info["front_line_strength"] += 1

        # Find weak points
        enemy_info["weak_points"] = self.find_weak_points(game_state)
        
        return enemy_info

    def find_weak_points(self, game_state):
        """
        Find weak points in enemy defenses
        """
        weak_points = []
        
        # Check paths from each edge location
        enemy_edges = game_state.game_map.get_edge_locations(1)
        
        for edge in enemy_edges:
            # Use simple path finding instead of gamelib's find_path_to_edge
            # which might be unreliable or causing issues
            x, y = edge
            # Only consider edges in the middle section of the map
            if 8 <= x <= 19:
                defense_strength = self.calculate_path_defense(game_state, [13, 0], edge)
                if defense_strength < 5:  # Threshold can be adjusted
                    weak_points.append(edge)
        
        return weak_points
        
    def calculate_path_defense(self, game_state, start, end):
        """
        Calculate the defensive strength along a path
        """
        # Simple estimation: check halfway points between start and end
        defense_strength = 0
        x1, y1 = start
        x2, y2 = end
        
        # Check 5 points along the path
        for i in range(1, 6):
            x = x1 + (x2 - x1) * i // 5
            y = y1 + (y2 - y1) * i // 5
            
            # Count defensive structures in a 3x3 area
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    check_loc = [x + dx, y + dy]
                    if game_state.game_map.in_arena_bounds(check_loc):
                        if game_state.contains_stationary_unit(check_loc):
                            for unit in game_state.game_map[check_loc]:
                                if unit.player_index == 1:  # Enemy unit
                                    if unit.unit_type == TURRET:
                                        defense_strength += 3
                                    elif unit.unit_type == WALL:
                                        defense_strength += 1
        
        return defense_strength

    def update_strategy(self, game_state, game_phase, enemy_info):
        """
        Update strategy based on game state and enemy information
        """
        # If we've been scored on multiple times in the same location, prioritize defense there
        if len(self.scored_on_locations) > 0:
            scored_locations_count = {}
            for location in self.scored_on_locations:
                loc_tuple = tuple(location)
                if loc_tuple in scored_locations_count:
                    scored_locations_count[loc_tuple] += 1
                else:
                    scored_locations_count[loc_tuple] = 1
            
            # Find most frequently breached locations
            self.priority_defense_locations = [list(loc) for loc, count in 
                                             scored_locations_count.items() 
                                             if count > 1]
        else:
            self.priority_defense_locations = []
        
        # Adjust strategy based on enemy's defensive strength
        if enemy_info["defense_strength"] > 30:
            self.enemy_formation = "defensive"
        elif enemy_info["front_line_strength"] > 10:
            self.enemy_formation = "offensive"
        else:
            self.enemy_formation = "balanced"
            
        gamelib.debug_write(f"Enemy formation: {self.enemy_formation}, Defense: {enemy_info['defense_strength']}")

    def build_defense(self, game_state, game_phase, enemy_info):
        """
        Build and upgrade defenses based on game phase and enemy behavior
        """
        # Build basic V-shape defense formation based on game phase
        if game_phase in ["opening", "early_game"]:
            self.build_formation(game_state, self.defense_v_patterns["early_game"], WALL)
        else:
            # Build complete defense
            self.build_formation(game_state, self.defense_v_patterns["early_game"], WALL)
            self.build_formation(game_state, self.defense_v_patterns["mid_game"], WALL)
            self.build_formation(game_state, self.defense_v_patterns["funnel"], WALL)
        
        # Place turrets in strategic positions
        for location in self.turret_positions:
            game_state.attempt_spawn(TURRET, location)
        
        # Reinforce priority defense locations (breach points)
        for location in self.priority_defense_locations:
            # Build turret slightly behind breach location to not block spawn
            reinforcement_loc = [location[0], location[1]+1]
            if self.is_valid_location(reinforcement_loc, game_state):
                game_state.attempt_spawn(TURRET, reinforcement_loc)
                game_state.attempt_upgrade(reinforcement_loc)
            
            # Add walls around vulnerable areas
            game_state.attempt_spawn(WALL, location)
            game_state.attempt_upgrade(location)
            
            # Add walls around the turret for protection
            for dx, dy in [(1, 0), (-1, 0), (0, 1)]:
                wall_loc = [reinforcement_loc[0] + dx, reinforcement_loc[1] + dy]
                if self.is_valid_location(wall_loc, game_state):
                    game_state.attempt_spawn(WALL, wall_loc)
        
        # Place support units
        if game_phase in ["mid_game", "late_game"]:
            for location in self.support_positions:
                game_state.attempt_spawn(SUPPORT, location)
        
        # Upgrade critical structures
        self.upgrade_structures(game_state, game_phase)

    def is_valid_location(self, location, game_state):
        """
        Check if a location is valid for building
        """
        x, y = location
        return (0 <= x < 28) and (y >= 0) and game_state.game_map.in_arena_bounds(location)

    def build_formation(self, game_state, locations, unit_type):
        """
        Build a formation of structures at specified locations
        """
        for location in locations:
            game_state.attempt_spawn(unit_type, location)

    def upgrade_structures(self, game_state, game_phase):
        """
        Upgrade important structures based on game phase and resources
        """
        # Always upgrade critical points first
        for location in self.critical_points:
            game_state.attempt_upgrade(location)
        
        # Upgrade turrets
        for location in self.turret_positions:
            if game_state.contains_stationary_unit(location):
                for unit in game_state.game_map[location]:
                    if unit.unit_type == TURRET and unit.player_index == 0 and unit.upgraded is False:
                        game_state.attempt_upgrade(location)
        
        # In later phases, upgrade walls in the front line
        if game_phase in ["mid_game", "late_game"]:
            front_line_walls = [loc for loc in self.defense_v_patterns["early_game"] 
                              if game_state.contains_stationary_unit(loc)]
            
            for location in front_line_walls:
                game_state.attempt_upgrade(location)
        
        # Upgrade support units last
        if game_phase == "late_game":
            for location in self.support_positions:
                game_state.attempt_upgrade(location)

    def should_attack(self, game_state, game_phase):
        """
        Determine if we should attack this turn
        """
        # Always attack in opening phase on every other turn
        if game_phase == "opening":
            return game_state.turn_number > 0 and game_state.turn_number % 2 == 0
        
        # After opening, attack based on resources and turn timing
        mp = game_state.get_resource(MP)
        
        if game_phase == "early_game":
            return mp >= 10
        elif game_phase == "mid_game":
            return mp >= 15 or game_state.turn_number % 2 == 0
        else:  # late_game
            return mp >= 20 or game_state.turn_number % 3 == 0

    def execute_attack(self, game_state, game_phase, enemy_info):
        """
        Execute attack strategy based on game phase and enemy info
        """
        # Select best spawn point based on damage calculation
        best_spawn = self.find_best_spawn_point(game_state)
        secondary_spawn = self.find_secondary_spawn(game_state, best_spawn)
        
        gamelib.debug_write(f"Attack from {best_spawn} and {secondary_spawn}")
        
        # Determine attack composition based on game phase and enemy defense
        if game_phase == "opening" or game_phase == "early_game":
            # Early game: Use scouts for quick points
            self.send_scouts(game_state, best_spawn, 5)
            
        elif game_phase == "mid_game":
            if enemy_info["front_line_strength"] > 8:
                # If enemy has strong front line, use demolishers to break through
                self.send_demolisher_scout_combo(game_state, best_spawn, secondary_spawn)
            else:
                # Otherwise, use interceptors to counter enemy mobile units and scouts for scoring
                self.send_interceptors(game_state, best_spawn, 3)
                self.send_scouts(game_state, secondary_spawn, 10)
                
        else:  # late_game
            # Determine if we should focus on breaking defenses or scoring points
            if enemy_info["defense_strength"] > 40:
                # Heavy defense-breaking attack
                self.send_demolisher_scout_combo(game_state, best_spawn, secondary_spawn)
            else:
                # Balanced attack
                self.send_demolisher_scout_combo(game_state, best_spawn, None)
                self.send_scouts(game_state, secondary_spawn, 15)
                
        # Record this attack
        self.last_attack_phase = game_phase
        
    def find_best_spawn_point(self, game_state):
        """
        Find the best spawn point with the least dangerous path
        """
        spawn_options = [[13, 0], [14, 0], [12, 1], [15, 1]]
        return self.least_damage_spawn_location(game_state, spawn_options)

    def find_secondary_spawn(self, game_state, primary_spawn):
        """
        Find a secondary spawn point that's different from the primary one
        """
        spawn_options = [[13, 0], [14, 0], [12, 1], [15, 1]]
        
        # Remove primary spawn from options
        filtered_options = [spawn for spawn in spawn_options if spawn != primary_spawn]
        
        # Find the best among the remaining options
        return self.least_damage_spawn_location(game_state, filtered_options)

    def least_damage_spawn_location(self, game_state, location_options):
        """
        Find spawn location that will take the least damage path
        """
        damages = []
        
        for location in location_options:
            # Estimate damage along path to enemy edge
            damage = self.estimate_path_damage(game_state, location)
            damages.append(damage)
        
        # Return the location with minimum damage, or first one if all are the same
        min_damage = min(damages)
        min_damage_indices = [i for i, d in enumerate(damages) if d == min_damage]
        
        return location_options[min_damage_indices[0]]
        
    def estimate_path_damage(self, game_state, start_location):
        """
        Estimate the damage units will take along a path from start_location
        """
        # Use simple path estimation instead of gamelib's path finding
        # Check 5 points along a straight line to the enemy edge
        damage = 0
        x1, y1 = start_location
        x2, y2 = 14, 27  # Mid-point of enemy edge
        
        # Check 10 points along the path
        for i in range(1, 11):
            x = x1 + (x2 - x1) * i // 10
            y = y1 + (y2 - y1) * i // 10
            check_loc = [x, y]
            
            # Count enemy turrets in range
            for dx in range(-3, 4):  # Turret range
                for dy in range(-3, 4):
                    if abs(dx) + abs(dy) <= 3:  # Manhattan distance for turret range
                        turret_loc = [x + dx, y + dy]
                        if game_state.game_map.in_arena_bounds(turret_loc):
                            if game_state.contains_stationary_unit(turret_loc):
                                for unit in game_state.game_map[turret_loc]:
                                    if unit.player_index == 1 and unit.unit_type == TURRET:
                                        damage += 5 if unit.upgraded else 3
        
        return damage

    def send_scouts(self, game_state, location, amount):
        """
        Send scouts from a location
        """
        game_state.attempt_spawn(SCOUT, location, amount)

    def send_demolishers(self, game_state, location, amount):
        """
        Send demolishers from a location
        """
        game_state.attempt_spawn(DEMOLISHER, location, amount)

    def send_interceptors(self, game_state, location, amount):
        """
        Send interceptors from a location
        """
        game_state.attempt_spawn(INTERCEPTOR, location, amount)

    def send_demolisher_scout_combo(self, game_state, primary_spawn, secondary_spawn):
        """
        Send a combo attack of demolishers to break defenses, followed by scouts to score
        """
        # Send demolishers first to break defenses
        self.send_demolishers(game_state, primary_spawn, 4)
        
        # If we specified a secondary spawn, send scouts from there
        if secondary_spawn:
            # Send scouts to follow behind demolishers
            self.send_scouts(game_state, secondary_spawn, 15)
        else:
            # Send from same location if no secondary specified
            self.send_scouts(game_state, primary_spawn, 12)

    def on_action_frame(self, turn_string):
        """
        Track outcomes from action frames
        """
        state = json.loads(turn_string)
        events = state["events"]
        breaches = events["breach"]
        
        for breach in breaches:
            location = breach[0]
            unit_owner_self = True if breach[4] == 1 else False
            
            if not unit_owner_self:  # Enemy scored on us
                if location not in self.scored_on_locations:
                    gamelib.debug_write(f"Enemy breach at {location}")
                    self.scored_on_locations.append(location)
            else:  # We scored on enemy
                if location not in self.enemy_scored_locations:
                    gamelib.debug_write(f"We breached enemy at {location}")
                    self.enemy_scored_locations.append(location)


if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()