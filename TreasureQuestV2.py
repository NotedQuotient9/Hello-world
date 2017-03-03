import libtcodpy as libtcod
import math
import textwrap
import shelve


#size of the window
SCREEN_WIDTH = 80 #80
SCREEN_HEIGHT = 45 #50


MAP_WIDTH = 80
MAP_HEIGHT = 38 #43

#dungeon generator parameters
ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30

#graphical tile information
wall_tile = 256
floor_tile = 257
player_tile = 258
orc_tile = 259
troll_tile = 260
scroll_tile = 261
healingpotion_tile = 262
sword_tile = 263
shield_tile = 264
stairsdown_tile = 265
dagger_tile = 266

#spell information
HEAL_AMOUNT = 40 
MORE_HEAL_AMOUNT = 100 #the heal value for the advanced potion
MAX_HEAL_AMOUNT = 250
LIGHTNING_DAMAGE = 40
LIGHTNING_RANGE = 5
CONFUSE_NUM_TURNS = 10
CONFUSE_RANGE = 8
FIREBALL_RADIUS = 3
FIREBALL_DAMAGE = 25

#player information
LEVEL_UP_BASE = 200
LEVEL_UP_FACTOR = 150 #number is tweaked for more challenging level up

#GUI information
BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT
MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MSG_HEIGHT = PANEL_HEIGHT - 1
INVENTORY_WIDTH = 50
LEVEL_SCREEN_WIDTH = 40
CHARACTER_SCREEN_WIDTH = 30

FOV_AlGO = 0 #fog of war algorithm default values
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

LIMIT_FPS = 20 #20 frames per second

#color_dark_wall = libtcod.Color(0,0, 100)
#color_light_wall = libtcod.Color(130, 110, 50)
color_dark_ground = libtcod.Color(50, 50, 150)
color_light_ground = libtcod.Color(200, 180, 50)


class Tile:
	#a tile of the map and its properties
	def __init__(self, blocked, block_sight = None):
		self.blocked = blocked
		
		self.explored = False
		
		#by default, if a tile is blocked, it also blocks sight
		if block_sight is None: block_sight = blocked
		self.block_sight = block_sight
	


class Rect:
	#a rectangle on the map, used to show a room
	def __init__(self, x, y, w, h):
		self.x1 = x
		self.y1 = y
		self.x2 = x + w
		self.y2 = y + h
		
	def center(self):
		center_x = (self.x1 + self.x2) / 2
		center_y = (self.y1 + self.y2) / 2
		return (center_x, center_y)
		
	def intersect(self, other):
		#returns true if rectangle intersects with another
		return (self.x1 <= other.x2 and self.x2 >= other.x1 and
			    self.y1 <= other.y2 and self.y2 >= other.y1)
	
			
class Object:
	#just a generic object
	#it's always representedby a character on screen
	def __init__(self, x, y, char, name, color, blocks=False, always_visible=False, fighter=None, ai=None, item=None, equipment=None):
		
		self.x = x
		self.y = y
		self.char = char
		self.name = name
		self.color = color
		self.blocks = blocks
		self.always_visible = always_visible
		self.fighter = fighter
		if self.fighter: #links the fighter component to the fighter class
			self.fighter.owner = self
		self.ai = ai
		if self.ai: #links the ai component to its respective class
			self.ai.owner = self
		self.item = item
		if self.item: #let the item component know who owns it
			self.item.owner = self
		self.equipment = equipment
		if self.equipment:
			self.equipment.owner = self
		
			#new item componant is required
			self.item = Item()
			self.item.owner = self
			
	def move(self, dx, dy):
		#move by the given amount, if the destination is not blocked
		if not is_blocked(self.x + dx, self.y +dy):
			self.x += dx
			self.y += dy
			
	def move_towards(self, target_x, target_y):
		#vector from this object to the target, and distance
		dx = target_x - self.x
		dy = target_y - self.y
		distance = math.sqrt(dx ** 2 + dy ** 2)
		
		#maths things
		dx = int(round(dx / distance))
		dy = int(round(dy / distance))
		self.move(dx, dy)
		
	def distance_to(self, other):
		#returns the distance to another object
		dx = other.x - self.x
		dy = other.y - self.y
		return math.sqrt(dx ** 2 + dy ** 2)

	def distance(self, x, y):
		#returns the distance to some coordinates
		return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)
		
	def draw(self):
		#add fov settings
		if (libtcod.map_is_in_fov(fov_map, self.x, self.y) or
			(self.always_visible and map[self.x][self.y].explored)):
			#set the colour and then draw the character that represents this object at its position
			libtcod.console_set_default_foreground(con, self.color)
			libtcod.console_put_char(con, self.x, self.y, self.char, libtcod.BKGND_NONE)
		
	def clear(self):
		#erase the character that represents this object
		libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)

	def send_to_back(self):
		#affects the layering of monster sprites
		global objects
		objects.remove(self)
		objects.insert(0, self)
		
class Fighter:
	#combat-related properties and methods (monster, player, npc)
	def __init__(self, hp, defence, power, xp, death_function=None):
		self.base_max_hp = hp
		self.hp = hp
		self.base_defence = defence
		self.base_power = power
		self.xp = xp
		self.death_function = death_function
		
	@property
	def power(self):
		bonus = sum(equipment.power_bonus for equipment in get_all_equipped(self.owner))
		return self.base_power + bonus
		
	@property
	def defence(self): #returns actual defence by summing up bonuses
		bonus = sum(equipment.defence_bonus for equipment in get_all_equipped(self.owner))
		return self.base_defence + bonus
		
	@property
	def max_hp(self): #returns actual hp including item bonuses
		bonus = sum(equipment.max_hp_bonus for equipment in get_all_equipped(self.owner))
		return self.base_max_hp + bonus
		
	def take_damage(self, damage):
		#applies damage if possible
		if damage > 0:
			self.hp -= damage
			
			#checks for death functions
			if self.hp <= 0:
				function = self.death_function
				if function is not None:
					function(self.owner)
				if self.owner != player:
					player.fighter.xp += self.xp
	
	def attack(self, target):
		#a simple attack formula
		damage = self.power - target.fighter.defence
		
		if damage > 0:
			#makes the target take damage
			message(self.owner.name.capitalize() + 'attacks ' + target.name + ' for ' + str(damage) + ' hit points. ')
			target.fighter.take_damage(damage)
		else:
			message(self.owner.name.capitalize() + ' attacks ' + target.name + ' but it has no effect!')
		
	def heal(self, amount):
		#heals by a given amount, without going over the max
		self.hp += amount
		if self.hp > self.max_hp:
			self.hp = self.max_hp
		
class BasicMonster:
	#the ai for the basic monster
	def take_turn(self):
		#the monster's turn
		monster = self.owner
		if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
		
			#moves towards player
			if monster.distance_to(player) >= 2:
				monster.move_towards(player.x, player.y)
				
			#attacks if close
			elif player.fighter.hp > 0:
				monster.fighter.attack(player)
	
class ConfusedMonster:
	#ai for confused monster
	def __init__(self, old_ai, num_turns=CONFUSE_NUM_TURNS):
		self.old_ai = old_ai
		self.num_turns = num_turns
	
	def take_turn(self):
		if self.num_turns > 0: #if they are still confused
			#makes the monster move randomly
			self.owner.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))
			self.num_turns -= 1
	
		else: #restores the non confused ai
			self.owner.ai = self.old_ai
			message('The ' + self.owner.name + ' is no longer confused!', libtcod.red)
	
class Item:
	#items that can be picked up and used
	def __init__(self, use_function=None):
		self.use_function = use_function
	
	def pick_up(self):
		#adds to inventory and takes from map
		if len(inventory) >= 26:
			message('Your inventory is full, cannot pick up ' + self.owner.name + '.', libtcod.red)
		else:
			inventory.append(self.owner)
			objects.remove(self.owner)
			message('You picked up a ' + self.owner.name + '!', libtcod.green)
		
			equipment = self.owner.equipment
			if equipment and get_equipped_in_slot(equipment.slot) is None:
				equipment.equip()
	
	def drop(self):
		#adds item to the map and removes it from the inventory
		objects.append(self.owner)
		inventory.remove(self.owner)
		self.owner.x = player.x
		self.owner.y = player.y
		message('You dropped a ' + self.owner.name + '.', libtcod.yellow)
		
		if self.owner.equipment:
			self.owner.equipment.dequip()
	
	
	def use(self):
		#just call the use_function if it is defined
		if self.use_function is None:
			message('The ' + self.owner.name + 'cannot be used.')
		if self.owner.equipment:
			self.owner.equipment.toggle_equip()
			return
		else:
			if self.use_function() != 'cancelled':
				inventory.remove(self.owner) #destroy after use, unless it was cancelled for some reason
		
class Equipment:
	#equippable items (e.g. sword, shield, armour)
	def __init__(self, slot, power_bonus=0, defence_bonus=0, max_hp_bonus=0):
		self.power_bonus = power_bonus
		self.defence_bonus = defence_bonus
		self.max_hp_bonus = max_hp_bonus
		
		self.slot = slot
		self.is_equipped = False
		
	def toggle_equip(self): #toggles the equp/dequip status of item
		if self.is_equipped:
			self.dequip()
			
	def equip(self):
		old_equipment = get_equipped_in_slot(self.slot)
		if old_equipment is not None:
			old_equipment.dequip()
		
		#equips item and gives info
		self.is_equipped = True
		message('Equipped ' + self.owner.name + ' on ' + self.slot + '.', libtcod.light_green)
		
		
	def dequip(self):
		#self explanatory
		if not self.is_equipped: return
		self.is_equipped = False
		message('Dequipped ' + self.owner.name + ' from ' + self.slot + '.', libtcod.light_yellow)
		
def get_equipped_in_slot(slot): #puts grabbed items in a slot
	for obj in inventory:
		if obj.equipment and obj.equipment.slot == slot and obj.equipment.is_equipped:
			return obj.equipment
	return None
		
def get_all_equipped(obj):
	if obj == player:
		equipped_list = []
		for item in inventory:
			if item.equipment and item.equipment.is_equipped:
				equipped_list.append(item.equipment)
		return equipped_list
	else:
		return [] #other objects (e.g. monsters) have no equipment
		
def is_blocked(x, y):
	#first test the map tile
	if map[x][y].blocked:
		return True
		
	#now check for blocking objects
	for object in objects:
		if object.blocks and object.x == x and object.y == y:
			return True
					
	return False
		
	
def create_room(room):
	global map
	#go through the tiles in the rectangle and make them passable
	for x in range(room.x1 + 1, room.x2):
		for y in range(room.y1 + 1, room.y2): 
			map[x][y].blocked = False
			map[x][y].block_sight = False
			

def create_h_tunnel(x1, x2, y):
	global map
	for x in range(min(x1, x2), max(x1, x2) + 1):
		map[x][y].blocked = False
		map[x][y].block_sight = False
		
def create_v_tunnel(y1, y2, x):
	global map
	for y in range(min(y1, y2), max(y1, y2) + 1):
		map[x][y].blocked = False
		map[x][y].block_sight = False
			
def make_map():
	global map, objects, stairs
	
	#the list of objects with just the player
	objects = [player]
	
	#fill map with "blocked" tiles
	map = [[ Tile(True) # weird bug fix, just roll with it for now
		for y in range(MAP_HEIGHT)]
			for x in range(MAP_WIDTH) ]
	#map is instead filled with blocked tiles, which the room function unblocks
	
	rooms = []
	num_rooms = 0
	
	for r in range(MAX_ROOMS):
		#randomise width and height
		w = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		h = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		#randomise room positioning within map boundaries
		x = libtcod.random_get_int(0, 0, MAP_WIDTH - w - 1)
		y = libtcod.random_get_int(0, 0, MAP_HEIGHT - h - 1)
	
		#uses the rect class to make rooms
		new_room = Rect(x, y, w, h)
	
		#runs through rooms for intersect check
		failed = False
		for other_room in rooms:
			if new_room.intersect(other_room):
				failed = True
				break
			
		if not failed:
			#this means that the room does not intersect and is safe
			
			#the create room function
			create_room(new_room)
			
			#center coordinates of new room
			(new_x, new_y) = new_room.center()
			
			if num_rooms == 0:
				#this is the first room, where the player will start
				player.x = new_x
				player.y = new_y
				
				#npc.x = (new_x + 2) #fresh code here bois, making npc start to the right of player
				#npc.y = new_y
			else:
				#all rooms after the first room
				#adds tunnel connectors
				
				#the coordinates of the previous room
				(prev_x, prev_y) = rooms[num_rooms-1].center()
				
				#draws a random number (either zero or one)
				if libtcod.random_get_int(0, 0, 1) == 1:
					#first move horizontally, then vertically
					create_h_tunnel(prev_x, new_x, prev_y)
					create_v_tunnel(prev_y, new_y, new_x)
				else:
					#first move vertically then horizontally
					create_v_tunnel(prev_y, new_y, prev_x)
					create_h_tunnel(prev_x, new_x, new_y)
				
			place_objects(new_room)
				
			#finally, append the new room to the list
			rooms.append(new_room)
			num_rooms += 1
			
	#creates stairs at the center of the last room
	stairs = Object(new_x, new_y, stairsdown_tile, 'stairs', libtcod.white, always_visible=True)
	objects.append(stairs)
	stairs.send_to_back() #so its drawn below the monsters
	
	
def random_choice_index(chances): #random number generator for item placement
	dice = libtcod.random_get_int(0, 1, sum(chances))
	
	#goes through all chances
	running_sum = 0
	choice = 0
	for w in chances:
		running_sum += w
		
		if dice <= running_sum:
			return choice
		choice += 1
	
	
def random_choice(chances_dict):
	#chooses options from the dictionary of chances
	chances = chances_dict.values()
	strings = chances_dict.keys()
	
	return strings[random_choice_index(chances)]
	
def from_dungeon_level(table):
	#returns a value that depends on dungeon level
	for (value, level) in reversed(table):
		if dungeon_level >= level:
			return value
	return 0
	
def on_dungeon_level(table):	
	#similar to from_dungeon_level but is for an exact floor only
	for (value, level) in reversed(table):
		if dungeon_level == level:
			return value
	return 0
	
def place_objects(room):
	#chooses a random number of monsters
	
	max_monsters = from_dungeon_level([[2, 1], [3, 4], [5, 6], [4,10], [3, 20],[5, 30]])
	
	#chance of each monster
	monster_chances = {}
	monster_chances['orc'] = 80 #orcs will always spawn
	monster_chances['troll'] = from_dungeon_level([[15, 3], [30, 5], [60, 7], [30, 10], [5, 15]])
	monster_chances['blood troll'] = from_dungeon_level([[15, 10], [30, 15], [60,20], [30, 25], [5, 35]])
	monster_chances['bone troll'] = from_dungeon_level([[20, 30], [50, 35], [60, 40], [30, 45]])
	monster_chances['orc chieftain'] = from_dungeon_level([[35, 40], [50, 45]])
	
	max_items = from_dungeon_level([[1, 1], [2, 4]])
	
	#chance of each item
	item_chances = {}
	item_chances['heal'] = 35  #healing potion always shows up, even if all other items have 0 chance
	item_chances['more-heal'] = from_dungeon_level([[35, 13]])
	item_chances['max-heal'] = from_dungeon_level([[35, 30]])
	item_chances['lightning'] = from_dungeon_level([[25, 4]])
	item_chances['fireball'] =  from_dungeon_level([[25, 6]])
	item_chances['confuse'] =   from_dungeon_level([[10, 2]])
	item_chances['iron sword'] = 	from_dungeon_level([[5, 6]])
	item_chances['leather shield'] = 	from_dungeon_level([[15, 10]]) #need to mess with the spawn rates and floors
	item_chances['steel sword'] =  from_dungeon_level([[15, 20]])
	item_chances['steel shield'] = from_dungeon_level([[15, 25]])
	item_chances['HERO SWORD'] = from_dungeon_level([[5, 30]])
	item_chances['HERO CROWN'] = 	from_dungeon_level([[15, 35]])
	item_chances['HERO SHIELD'] = from_dungeon_level([[5, 40]])
	item_chances['treasure'] = on_dungeon_level([[100, 50]]) 
	num_monsters = libtcod.random_get_int(0, 0, max_monsters)
	
	for i in range(num_monsters):
		#chooses random monster placement
		x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
		y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
			
		if not is_blocked(x, y):
			choice = random_choice(monster_chances)
			if choice == 'orc': #this creates an 80% chance of getting an orc
				#creates an orc
				fighter_component = Fighter(hp=20, defence=0, power=4, xp=35, death_function=monster_death)
				ai_component = BasicMonster()
				
				monster = Object(x, y, orc_tile, 'orc', libtcod.desaturated_green,
					blocks=True, fighter=fighter_component, ai=ai_component)
					
			elif choice == 'troll':
				#creates a troll
				fighter_component = Fighter(hp=30, defence=2, power=8, xp=100, death_function=monster_death)
				ai_component = BasicMonster()
				
				
				monster = Object(x, y, troll_tile, 'troll', libtcod.darker_green,
					blocks=True, fighter=fighter_component, ai=ai_component)
			
			elif choice == 'blood troll':
				#creates a boss troll
				fighter_component = Fighter(hp=50, defence=4, power=10, xp=500, death_function=monster_death)
				ai_component = BasicMonster()
				
				monster = Object(x, y, troll_tile, 'blood troll', libtcod.dark_red,
					blocks=True, fighter=fighter_component, ai=ai_component)
					
			elif choice == 'bone troll':
				#creates an even stronger troll, only appears at super high levels
				fighter_component = Fighter(hp=65, defence=6, power=15, xp=750, death_function=monster_death)
				ai_component = BasicMonster()
				
				monster = Object(x, y, troll_tile, 'bone troll', libtcod.white,
					blocks=True, fighter=fighter_component, ai=ai_component)
			
			elif choice == 'orc chieftain':
				#creates the strongest enemy, only at super high levels
				fighter_component = Fighter(hp=85, defence=10, power=20, xp=1000, death_function=monster_death)
				ai_component = BasicMonster()
				
				monster = Object(x, y, orc_tile, 'orc chieftain', libtcod.violet,
					blocks=True, fighter=fighter_component, ai=ai_component)
			
			objects.append(monster)
			
	num_items = libtcod.random_get_int(0, 0, max_items)
	
	for i in range(num_items):
		#chooses random spots for items
		x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
		y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
		
		#only places if spot is unblocked
		if not is_blocked(x, y):
			
			choice = random_choice(item_chances)
			if choice == 'heal':
				#70% chance for healing potion
				#creates healing potion
				item_component = Item(use_function=cast_heal)
			
				item = Object(x, y, healingpotion_tile, 'healing potion', libtcod.violet, item=item_component)
				
			#add new potion type, also add in the spawn menu
			elif choice == 'more-heal':
				#creates better healing potion
				item_component = Item(use_function=cast_more_heal)
				
				item = Object(x, y, healingpotion_tile, 'advanced potion', libtcod.light_green, item=item_component)
			
			elif choice == 'max-heal':
				#creates the final tier of healing potion
				item_component = Item(use_function=cast_max_heal)
				
				item = Object(x, y, healingpotion_tile, 'ultimate potion', libtcod.yellow, item=item_component)
			
			elif choice == 'lightning':
				#15% chance for lightining bolt scroll
				item_component = Item(use_function=cast_lightning)
				
				item = Object(x, y, scroll_tile, 'scroll of lightning bolt', libtcod.light_yellow, item=item_component)
			
			elif choice == 'fireball':
				#10% chance for fireball scroll
				item_component = Item(use_function=cast_fireball)
				
				item = Object(x, y, scroll_tile, 'scroll of fireball', libtcod.light_yellow, item=item_component)
			
			elif choice == 'confuse':
				#15% chance for confusion scroll
				item_component = Item(use_function=cast_confuse)
				
				item = Object(x, y, scroll_tile, 'scroll of confusion', libtcod.light_yellow, item=item_component)
			
			elif choice == 'iron sword':
				#creates an equipabble sword
				equipment_component = Equipment(slot='right hand', power_bonus=3)
				item = Object(x, y, sword_tile, 'iron sword', libtcod.darker_orange, equipment=equipment_component)
			
			elif choice == 'leather shield':
				#creates an equipabble shield
				equipment_component = Equipment(slot='left hand', defence_bonus=1)
				item = Object(x, y, shield_tile, 'leather shield', libtcod.darker_orange, equipment=equipment_component)
			
			elif choice == 'steel sword':
				#creates a stronger sword
				equipment_component = Equipment(slot='right hand', power_bonus=5)
				item = Object(x, y, sword_tile, 'steel sword', libtcod.grey, equipment=equipment_component)
				
			elif choice == 'steel shield':
				#creates a stronger shield
				equipment_component = Equipment(slot='left hand', defence_bonus=3)
				item = Object(x, y, shield_tile, 'steel shield', libtcod.grey, equipment=equipment_component)
				
			elif choice == 'HERO SWORD':
				#creates the ultimate tool for a hero
				equipment_component = Equipment(slot='right hand', power_bonus=8)
				item = Object(x, y, sword_tile, 'HERO SWORD', libtcod.sky, equipment=equipment_component)
				
			elif choice == 'HERO CROWN':
				#creates a sick crown which grants more hp
				equipment_component = Equipment(slot='head', max_hp_bonus=25)
				item = Object(x, y, 'O', 'HERO CROWN', libtcod.yellow, equipment=equipment_component)
				
			elif choice == 'HERO SHIELD':
				#creates the ultimate shield
				equipment_component = Equipment(slot='left hand', defence_bonus=5)
				item = Object(x, y, shield_tile, 'HERO SHIELD', libtcod.sky, equipment=equipment_component)
			
			elif choice == 'treasure':
				#the promised treasure on level 50, it doesn't do anything
				equipment_component = Equipment(slot='money pouch', defence_bonus=5)
				item = Object(x, y, '*', 'treasure', libtcod.yellow, equipment=equipment_component)
			
			objects.append(item)
			item.send_to_back() #items appear below other objects
			

def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
	#renders a bar which can be used for anything
	bar_width = int(float(value) / maximum * total_width)
	
	#renders the background
	libtcod.console_set_default_background(panel, back_color)
	libtcod.console_rect(panel, x, y, total_width, 1, False, libtcod.BKGND_SCREEN)
	
	#now renders the bar itself
	libtcod.console_set_default_background(panel, bar_color)
	if bar_width > 0:
		libtcod.console_rect(panel, x, y, bar_width, 1, False, libtcod.BKGND_SCREEN)
		
	#adding text to the bars
	libtcod.console_set_default_foreground(panel, libtcod.white)
	libtcod.console_print_ex(panel, x + total_width / 2, y, libtcod.BKGND_NONE, libtcod.CENTER,
		name + ': ' + str(value) + '/' + str(maximum))
			
def get_names_under_mouse():
	global mouse
	
	#returns a string with the names of all objects under the mouse
	(x, y) = (mouse.cx, mouse.cy)
	
	names = [obj.name for obj in objects
		if obj.x == x and obj.y == y and libtcod.map_is_in_fov(fov_map, obj.x, obj.y)]
	
	names = ', '.join(names) #joins the names, separated by commas
	return names.capitalize()
			
def render_all():
	global fov_map, color_dark_wall, color_light_wall
	global color_dark_ground, color_light_ground
	global fov_recompute
	
	if fov_recompute:
		#recompute's fov if necessary
		fov_recompute = False
		libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_AlGO)
	
		#go through all tiles and set their background color
		for y in range(MAP_HEIGHT):
			for x in range(MAP_WIDTH):
				visible = libtcod.map_is_in_fov(fov_map, x, y)
				wall = map[x][y].block_sight
				if not visible:
					if map[x][y].explored: #adds fog of war
						#this is for when the tiles are out of the fov
						if wall:
							libtcod.console_put_char_ex(con, x, y, wall_tile, libtcod.grey, libtcod.black )
						else:
							libtcod.console_put_char_ex(con, x, y, floor_tile, libtcod.grey, libtcod.black)
				else:
					#if tiles are in fov
					if wall:
						libtcod.console_put_char_ex(con, x, y, wall_tile, libtcod.white, libtcod.black)
					else:
						libtcod.console_put_char_ex(con, x, y, floor_tile, libtcod.white, libtcod.black)
					map[x][y].explored = True
				
	#draw all objects in the list
	for object in objects:
		if object != player:
			object.draw()
	player.draw()
	
	#blit the contents of con to the root console and present it
	libtcod.console_blit(con, 0,0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, 0)
	
	#prepare to render GUI panel
	libtcod.console_set_default_background(panel, libtcod.black)
	libtcod.console_clear(panel)
	
	#prints the games messages one at a time
	y = 1
	for (line, color) in game_msgs:
		libtcod.console_set_default_foreground(panel, color)
		libtcod.console_print_ex(panel, MSG_X, y, libtcod.BKGND_NONE, libtcod.LEFT, line)
		y += 1
	
	#shows player's stats
	render_bar(1, 1, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp,
		libtcod.light_red, libtcod.darker_red)
	libtcod.console_print_ex(panel, 1, 3, libtcod.BKGND_NONE, libtcod.LEFT, 'Dungeon level ' + str(dungeon_level))
		
	#stuff for mouse-looking	
	libtcod.console_set_default_foreground(panel, libtcod.light_gray)
	libtcod.console_print_ex(panel, 1, 0, libtcod.BKGND_NONE, libtcod.LEFT, get_names_under_mouse())
		
	#blits the contents of the panel
	libtcod.console_blit(panel, 0, 0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)
	
def message(new_msg, color = libtcod.white):
	#splits the message if necessary using textwrap
	new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)
	
	for line in new_msg_lines:
		#if the buffer is full, remove the first line to make room for the new one
		if len(game_msgs) == MSG_HEIGHT:
			del game_msgs[0]
			
		#adds the new line with text and colour
		game_msgs.append((line, color))
	
	
def player_move_or_attack(dx, dy):
	global fov_recompute
		
	#the coordinates the player is going to
	x = player.x + dx
	y = player.y + dy
		
	#looking for an object to attack
	target = None
	for object in objects:
		if object.fighter and object.x == x and object.y == y:
			target = object
			break
		
	#attacks if object found
	if target is not None:
		player.fighter.attack(target)
			
	else:
		player.move(dx, dy)
		fov_recompute = True
	
def menu(header, options, width):
	if len(options) > 26: raise ValueError('Cannot have a menu with more than 26 options.')
	
	#calculate total height for the header
	header_height = libtcod.console_get_height_rect(con, 0, 0, width, SCREEN_HEIGHT, header)
	if header == '':
		header_height = 0
	height = len(options) + header_height
	
	#creates an offscreen console that represents the menu's window
	window = libtcod.console_new(width, height)
	
	#print the header, with autowrap(of course)
	libtcod.console_set_default_foreground(window, libtcod.white)
	libtcod.console_print_rect_ex(window, 0, 0, width, height, libtcod.BKGND_NONE, libtcod.LEFT, header)
	
	#print all the options
	y = header_height
	letter_index = ord('a')
	for option_text in options:
		text = '(' + chr(letter_index) + ') ' + option_text
		libtcod.console_print_ex(window, 0, y, libtcod.BKGND_NONE, libtcod.LEFT, text)
		y += 1
		letter_index += 1
		
	#blit the contents of "window" to the root console
	x = SCREEN_WIDTH/2 - width/2
	y = SCREEN_HEIGHT/2 - height/2
	libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7)#these last two numbers are screen transparency
	
	#present this new screen to the player and wait for keypress
	libtcod.console_flush()
	key = libtcod.console_wait_for_keypress(True)
	
	if key.vk == libtcod.KEY_ENTER and key.lalt: #fullscreen if enter and left alt are pressed together
		libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
	
	#convert the ASCII code to an index, returns if it corresponds to an option_text
	index = key.c - ord('a')
	if index >= 0 and index < len(options): return index
	return None
	
def inventory_menu(header):
	#show a menu with each item of the inventory as an option_text
	if len(inventory) == 0:
		options = ['Inventory is empty.']
	else:
		options = []
		for item in inventory:
			text = item.name
			#shows additional info for equipment
			if item.equipment and item.equipment.is_equipped:
				text = text + ' (on ' + item.equipment.slot + ')'
			options.append(text)
		
	index = menu(header, options, INVENTORY_WIDTH)
	
	#returns chosen item
	if index is None or len(inventory) == 0: return None
	return inventory[index].item
	
def msgbox(text, width=50):
	menu(text, [], width) #uses menu() as a sort of message box
	
def handle_keys():
	global key
	
	
	if key.vk == libtcod.KEY_ENTER and key.lalt: #left alt
		#this is ALT + ENTER to toggle fullscreen
		libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
		
	elif key.vk == libtcod.KEY_ESCAPE:
		return 'exit' #to exit game
		
	if game_state == 'playing':
		#movement keys
		if key.vk == libtcod.KEY_UP or key.vk == libtcod.KEY_KP8:
			player_move_or_attack(0, -1)
			
		elif key.vk == libtcod.KEY_DOWN or key.vk == libtcod.KEY_KP2:
			player_move_or_attack(0, 1)
			
		elif key.vk == libtcod.KEY_LEFT or key.vk == libtcod.KEY_KP4:
			player_move_or_attack(-1, 0)
			
		elif key.vk == libtcod.KEY_RIGHT or key.vk == libtcod.KEY_KP6:
			player_move_or_attack(1, 0)
		elif key.vk == libtcod.KEY_HOME or key.vk == libtcod.KEY_KP7:
			player_move_or_attack(-1, -1)
		elif key.vk == libtcod.KEY_PAGEUP or key.vk == libtcod.KEY_KP9:
			player_move_or_attack(1, -1)
		elif key.vk == libtcod.KEY_END or key.vk == libtcod.KEY_KP1:
			player_move_or_attack(-1, 1)
		elif key.vk == libtcod.KEY_PAGEDOWN or key.vk == libtcod.KEY_KP3:
			player_move_or_attack(1, 1)
		elif key.vk == libtcod.KEY_KP5:
			pass #do nothing for a turn		
		else:
			#test for other keys
			key_char = chr(key.c)
			
			if key_char == 'g':
				#pick up an item
				for object in objects: #look for an item in the player's tile
					if object.x == player.x and object.y == player.y and object.item:
						object.item.pick_up()
						break
						
			if key_char == 'i':
				#shows the inventory, and uses any selected items
				chosen_item =  inventory_menu('Press the key next to an item to use it, or any other to cancel.\n')
				if chosen_item is not None:
					chosen_item.use()
			
			if key_char == 'd':
				#shows the inventory, but drops the selected item
				chosen_item = inventory_menu('Press the key next to an item to drop it, or any other to cancel.\n')
				if chosen_item is not None:
					chosen_item.drop()
			
			if key_char == 'c':
				#shows character information (ie level and stats)
				level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
				msgbox('Character Information\n\nLEVEL: ' + str(player.level) + '\nExperience: ' + str(player.fighter.xp) +
					'\nExperience to level up: ' + str(level_up_xp) + '\n\nMaximum HP: ' + str(player.fighter.max_hp) +
					'\nAttack: ' + str(player.fighter.power) + '\nDefence: ' + str(player.fighter.defence), CHARACTER_SCREEN_WIDTH)
			
			if key_char == '<':
				#go down stairs if player is on them
				if stairs.x == player.x and stairs.y == player.y:
					next_level()
			
			
			return 'didnt-take-turn'
	
def check_level_up():
	#checks if enough xp has been accumlated to level up
	level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
	if player.fighter.xp >= level_up_xp:
		#if there is enough xp to level up
		player.level += 1
		player.fighter.xp -= level_up_xp
		message('You become stronger and more skilled! You reached level ' + str(player.level) + '!', libtcod.yellow)
		
		choice = None
		while choice == None: #keeps asking until a choice is made
			choice = menu('Level up!, Choose a stat to increase:\n',
				['Constitution (+20 HP, from ' + str(player.fighter.max_hp) + ')',
				'Strengh (+1 attack, from ' + str(player.fighter.power) + ')',
				'Agility (+1 defence, from ' + str(player.fighter.defence) + ')'], LEVEL_SCREEN_WIDTH)
				
		if choice == 0:
			player.fighter.max_hp += 20
			player.fighter.hp += 20
		elif choice == 1:
			player.fighter.power += 1
		elif choice == 2:
			player.fighter.defence += 1
	
def target_tile(max_range=None):
		#allows targeting by left clicking the mouse
		global key, mouse
		while True:
			#render teh screen
			libtcod.console_flush()
			libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE, key, mouse)
			render_all()
			(x, y) = (mouse.cx, mouse.cy)
			
			if mouse.rbutton_pressed or key.vk == libtcod.KEY_ESCAPE:
				return (None, None) #if player right clicks or presses escape then action is cancelled
				
			#accepts shot if in fov
			if (mouse.lbutton_pressed and libtcod.map_is_in_fov(fov_map, x, y) and
				(max_range is None or player.distance(x, y) <= max_range)):
				return (x, y)
				
def target_monster(max_range=None):
	#returns a clicked monster inside FOV
	while True:
		(x, y) = target_tile(max_range)
		if x is None: #if action is cancelled
			return None
			
		#returns the first clicked monster
		for obj in objects:
			if obj.x == x and obj.y == y and obj.fighter and obj != player:
				return obj
				
def player_death(player):
	#the player dies and the game ends
	global game_state
	message("You died!", libtcod.red)
	game_state = 'dead'
	
	#transforms character into corpse
	player.char = '%'
	player.color = libtcod.dark_red
	
def monster_death(monster):
	#transforms monster into corpse
	message('The ' + monster.name + ' is dead! You gain ' + str(monster.fighter.xp) + ' experience points.', libtcod.orange)
	monster.char = '%'
	monster.color = libtcod.dark_red
	monster.blocks = False
	monster.fighter = None
	monster.ai = None
	monster.name = 'remains of ' + monster.name
	monster.send_to_back()
		
def closest_monster(max_range):
	#finds closest enemy within fov
	closest_enemy = None
	closest_dist = max_range + 1
	
	for object in objects:
		if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y):
			#calcuates distance between object and player
			dist = player.distance_to(object)
			if dist < closest_dist: 
				closest_enemy = object
				clostest_dist = dist
	return closest_enemy
		
def cast_heal():
	#heals the player
	if player.fighter.hp == player.fighter.max_hp:
		message('You are already at full health', libtcod.red)
		return 'cancelled'
		
	message('Your wounds start to feel better!', libtcod.light_violet)
	player.fighter.heal(HEAL_AMOUNT)
	
def cast_more_heal():
	#heals the player more
	if player.fighter.hp == player.fighter.max_hp:
		message('You are already at full health', libtcod.red)
		return 'cancelled'
		
	message('Your wounds start to feel better!', libtcod.red)
	player.fighter.heal(MORE_HEAL_AMOUNT)
		
def cast_max_heal():
	#heals a whole entire bunch
	if player.fighter.hp == player.fighter.max_hp:
		message('You are already at full health', libtcod.red)
		return 'cancelled'
		
	message('Your wounds start to feel better!', libtcod.red)
	player.fighter.heal(MAX_HEAL_AMOUNT)
		
def cast_lightning():
	#find closest enemy within range and damage it
	monster = closest_monster(LIGHTNING_RANGE)
	if monster is None: #no enemy within range
		message('No enemy is close enough to strike.', libtcod.red)
		return 'cancelled'
	
	#successful lightning bolt
	message('A lightning bolt strikes the ' + monster.name + ' with a loud thunder! The damage is '
		+ str(LIGHTNING_DAMAGE) + ' hit points.', libtcod.light_blue)
	monster.fighter.take_damage(LIGHTNING_DAMAGE)
	
def cast_confuse():
	#asks player to choose a target
	message('Left-click an enemy to confuse them, or right-click to cancel.', libtcod.light_cyan)
	monster = target_monster(CONFUSE_RANGE)
	if monster is None: return 'cancelled'
		
	#successful confuse, temporarily replaces the monster's ai
	old_ai = monster.ai
	monster.ai = ConfusedMonster(old_ai)
	monster.ai.owner = monster #tells the component which monster is confused
	message('The eyes of the  ' + monster.name + ' look vacant, as he starts to stumble around!', libtcod.light_green)

def cast_fireball():
	#uses the tile targetting system
	message('Left-click a target tile for the fireball, or right-click to cancel.', libtcod.light_cyan)
	(x, y) = target_tile()
	if x is None: return 'cancelled'
	message('The fireball explodes, burnign everything within ' + str(FIREBALL_RADIUS) + ' tiles!', libtcod.orange)
	
	for obj in objects: #damages every fighter in range, including player
		if obj.distance(x, y) <= FIREBALL_RADIUS and obj.fighter:
			message('The ' + obj.name + 'gets burned for ' + str(FIREBALL_DAMAGE) + ' hit points.', libtcod.orange)
			obj.fighter.take_damage(FIREBALL_DAMAGE)
	
def load_customfont():
	#the index of the first custom tile in the file
	a = 256
	
	#the 'y' is the row index
	for y in range(5, 6):
		libtcod.console_map_ascii_codes_to_font(a, 32, 0, y)
		a += 32
	
def save_game():
	#open a new empy shelve to write game data
	file = shelve.open('savegame', 'n')
	file['map'] = map
	file['objects'] = objects
	file['player_index'] = objects.index(player)
	file['inventory'] = inventory
	file['game_msgs'] = game_msgs
	file['game_state'] = game_state
	file['stairs_index'] = objects.index(stairs)
	file['dungeon_level'] = dungeon_level
	file.close()
	
def load_game():
	#opens the previously shelved game
	global map, objects, player, inventory, game_msgs, game_state, stairs, dungeon_level
	
	file = shelve.open('savegame', 'r')
	map = file['map']
	objects = file['objects']
	player = objects[file['player_index']] 
	inventory = file['inventory']
	game_msgs = file['game_msgs']
	game_state = file['game_state']
	stairs = objects[file['stairs_index']]
	dungeon_level = file['dungeon_level']
	file.close()

	initialize_fov()
	
def new_game():
	global player, inventory, game_msgs, game_state, dungeon_level
	
	#create object representing the player
	fighter_component = Fighter(hp=100, defence=1, power=2, xp=0, death_function=player_death) #100, 1, 2
	player = Object(0, 0, player_tile, 'player', libtcod.white, blocks=True, fighter=fighter_component)
	
	player.level = 1
	#generate map
	dungeon_level = 1
	make_map()
	initialize_fov()
	
	game_state = 'playing'
	inventory = []
	
	#creates the list of game messages
	game_msgs = []
	
	#a welcoming message
	message('Welcome to TREASURE QUEST! can you reach the riches on the 50th floor?', libtcod.red)
	
	#initial equipment: a dagger
	equipment_component = Equipment(slot='right hand', power_bonus=2)
	obj = Object(0, 0, '-', 'dagger', libtcod.sky, equipment=equipment_component)
	inventory.append(obj)
	equipment_component.equip()
	obj.always_visible = True
	
	
def next_level():
	global dungeon_level
	
	#creates a new dungeon level
	message('You take a moment to rest, and recover your strength.', libtcod.light_violet)
	player.fighter.heal(player.fighter.max_hp / 2) #heals by 50%
	
	message('After a moment of peace you go deeper into the dungeon...', libtcod.red)
	dungeon_level += 1
	make_map()
	initialize_fov()
	
	
def initialize_fov():
	global fov_recompute, fov_map
	fov_recompute = True
	
	#create the FOV map
	fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
	for y in range(MAP_HEIGHT):
		for x in range(MAP_WIDTH):
			libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)
			
	libtcod.console_clear(con) #fixes a bug when starting a new game with the main menu
def play_game():
	global key, mouse
	
	player_action = None
	
	mouse = libtcod.Mouse()
	key = libtcod.Key()
	while not libtcod.console_is_window_closed():
		#render the screen
		libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE, key, mouse)
		render_all()
		
		load_customfont()
		
		libtcod.console_flush()
		
		check_level_up()
		
		#erase all objects at their old locations
		for object in objects:
			object.clear()
			
		#handle keys and exit game
		player_action = handle_keys()
		if player_action == 'exit':
			save_game()
			break
			
		#lets monsters take their turns
		if game_state == 'playing' and player_action != 'didnt-take-turn':
			for object in objects:
				if object.ai:
					object.ai.take_turn()

def main_menu():
	img = libtcod.image_load('menu_background3.png')
	
	while not libtcod.console_is_window_closed():
		#shows the background image
		libtcod.image_blit_2x(img, 0, 0, 0)
		
		#credits and title
		libtcod.console_set_default_foreground(0, libtcod.light_yellow)
		libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT/2-4, libtcod.BKGND_NONE, libtcod.CENTER,
			'TREASURE QUEST V2')
		libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT-2, libtcod.BKGND_NONE, libtcod.CENTER,
			'By Matthew')
		
		#show options and wait for player's choice
		choice = menu('', ['Play a new game', 'Continue last game', 'Help', 'Quit'], 24)
		
		if choice == 0: #new game
			new_game()
			play_game()
		if choice == 1: #loads previous game
			try:
				load_game()
			except:
				msgbox('\n No saved game to load.\n', 24)
				continue
			play_game()
		elif choice == 2: #shows controls in msgbox
			msgbox('\nControls:\n Arrow keys to move \n around\n g to grab items\n i to open inventory\n < to go down stairs\n d to drop items\n c to check character          information', 24) #need to fix this
			libtcod.console_flush()
			key = libtcod.console_wait_for_keypress(True)
		elif choice == 3: #quit
			break
	
###########################
#Main loop (see above)
###########################

#libtcod.console_set_custom_font('arial10x10.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)
libtcod.console_set_custom_font('TiledFont.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD, 32, 10)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'python/TreasureQuestV2', False)
libtcod.sys_set_fps(LIMIT_FPS)
con = libtcod.console_new(SCREEN_WIDTH, SCREEN_HEIGHT)
panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)

main_menu()
				
				
				
				
#Update to do list:
"""
-Fix equipment spawn rates
-Download/use gimp to fix sprites and remove black background
-Actually test before converting to exe
"""
