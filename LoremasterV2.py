import asyncio
import os
import pickle
from threading import Thread
from functools import partial
from time import time

from wizwalker import utils
from wizwalker.constants import Keycode
from wizwalker.errors import MemoryReadError
from wizwalker.extensions.wizsprinter import (CombatConfigProvider, SprintyCombat, WizSprinter)
from wizwalker.utils import XYZ, wait_for_non_error

from utils import (auto_buy_potions, collect_wisps, decide_heal,
					 get_window_from_path, safe_tp_to_health, safe_tp_to_mana)

					 
def clearConsole():
	command = 'clear'
	if os.name in ('nt', 'dos'):	# If Machine is running on Windows, use cls
		command = 'cls'
	os.system(command)

def check_position_near(xyz_one, xyz_two, nearness):
		x_nearness = abs(xyz_one.x - xyz_two.x)
		y_nearness = abs(xyz_one.y - xyz_two.y)
		
		return x_nearness < nearness and y_nearness < nearness

class LoremasterBot(WizSprinter):
	# Combat Assignment
	combat_handlers = []
	start = 0
	total = time()
	total_count = 0
	min_time = float("inf")
	max_time = 0
	cur = None
	running = True
	paused = False
	
	# All session data
	try:
		data = pickle.load(open( "save.p", "rb"))
	except (OSError, IOError) as e:
		data = {"count" : 0, "time" : 0, "min" : float("inf"), "max" : 0}
		pickle.dump(data, open( "save.p", "wb"))
	
	# Potion Text Assignment
	potion_ui_buy = [
		"fillallpotions",
		"buyAction",
		"btnShopPotions",
		"centerButton",
		"fillonepotion",
		"buyAction",
		"exit"
		]

	async def run(self):
		clearConsole()
		
		# Register clients
		self.get_new_clients()
		clients = self.get_ordered_clients()
		#p1, p2, p3, p4 = [*clients, None, None, None, None][:4]
		#xyz = [2, 4, 10]
		
		for i, p in enumerate(clients, 1):
			p.title = "p" + str(i)
			
		
		# Hook activation
		for p in clients:
			self.conPrint(f"[{p.title}] Activating Hooks")
			await p.activate_hooks()
			await p.mouse_handler.activate_mouseless()


		await self.run_begin()
		await self.run_manahpcheck()
		
		while self.running:
			while self.paused:
				pass
			self.start = time()
			await self.run_manahpcheck()
			await self.run_teamup()
			await self.run_lore_battleTP()
			await self.run_battle()
			await self.run_reset()
			await self.run_timer()
		

	async def get_window_from_path(root_window, name_path):
		async def _recurse_follow_path(window, path):
			if len(path) == 0:
				return window

			for child in await window.children():
				if await child.name() == path[0]:
					found_window = await _recurse_follow_path(child, path[1:])
					if not found_window is False:
						return found_window

			return False

		return await _recurse_follow_path(root_window, name_path)

	async def click_window_from_path(self, path_array):
		for client in self.clients:
			coro = partial(get_window_from_path, client.root_window, path_array)
			window = await utils.wait_for_non_error(coro)
			await client.mouse_handler.click_window(window)

	async def click_window_named(self, button_name):
		for client in self.clients:
			coro = partial(client.mouse_handler.click_window_with_name, button_name)
			await utils.wait_for_non_error(coro)
		
	async def run_begin(self):
		# Go to starting area
		self.conPrint("Placing marker")
		await asyncio.gather(*[client.teleport(XYZ(-3136.481689453125, 464.997802734375, 0), False) for client in self.clients])
		await asyncio.gather(*[client.send_key(Keycode.A, 0.1) for client in self.clients])
		await asyncio.sleep(0.01)
		await asyncio.sleep(0.8)
		await asyncio.gather(*[client.send_key(Keycode.PAGE_DOWN, 0.1) for client in self.clients])
		await asyncio.sleep(0.1)

	async def run_teamup(self):
		# Click Team Up, Farming, and minimum of 4 buttons
		self.conPrint("Teaming up", 1)
		await self.click_window_named("TeamUpButton")
		await asyncio.sleep(0.7)
		await self.click_window_named("TeamSize4CheckBox")
		await asyncio.sleep(0.1)
		await self.click_window_named("TeamTypeFarmingCheckBox")
		await asyncio.sleep(0.1)
		await self.click_window_from_path(["WorldView", "TeamUpConfirmationWindow", "TeamUpConfirmationBackground", "TeamUpButton"])
		
		# Wait for zone change
		self.conPrint("Waiting in queue", 2)
		await asyncio.gather(*[client.wait_for_zone_change() for client in self.clients])
		await asyncio.sleep(0.1)

	async def run_lore_battleTP(self):
		self.conPrint("Teleporting to Loremaster", 2)
		await asyncio.gather(*[client.teleport(XYZ(-46.86019515991211, -28.653949737548828, 0), False) for client in self.clients])
		await asyncio.sleep(0.1)
		await asyncio.gather(*[client.send_key(Keycode.A, 0.1) for client in self.clients])
		await asyncio.sleep(0.1)

	async def run_battle(self):
		# Battle:
		self.conPrint("Initiating combat", 3)
		combat_handlers = []
		for client in self.clients: # Setting up the parsed configs to combat_handlers
			combat_handlers.append(SeanNoLikeMobs(client, CombatConfigProvider(f'configs/{client.title}spellconfig.txt', cast_time=0.4))) 
		self.conPrint("In battle", 3)
		try:
			await asyncio.gather(*[h.wait_for_combat() for h in combat_handlers]) # .wait_for_combat() to wait for combat to then go through the battles
		except: #Exception e:
			#print(e)
			await self.run_battle()
		self.conPrint("Combat ended", 4)
		await asyncio.sleep(0.1)

	async def run_reset(self):
		await asyncio.gather(*[client.teleport(XYZ(12.702668190002441,1612.439208984375, 0), False) for client in self.clients])
		await asyncio.sleep(0.1)
		await asyncio.gather(*[client.send_key(Keycode.A, 0.1) for client in self.clients])
		await asyncio.sleep(0.1)
		await asyncio.gather(*[client.wait_for_zone_change() for client in self.clients])
		await asyncio.sleep(0.1)
		await asyncio.gather(*[client.goto(-3136.481689453125, 464.997802734375) for client in self.clients])
		await asyncio.sleep(0.7)

	async def run_manahpcheck(self):
		# Healing
		await asyncio.gather(*[client.use_potion_if_needed(health_percent=65, mana_percent=5) for client in self.clients])
		await asyncio.gather(*[decide_heal(client) for client in self.clients])
		await asyncio.sleep(1.5)

	async def run_timer(self):
		# Time
		self.total_count += 1
		cur = round((time() - self.start) / 60, 2)
		self.min_time = min(self.min_time, cur)
		self.max_time = max(self.max_time, cur)
		self.data["count"] += 1
		self.data["time"] += cur
		self.data["min"] = min(self.data["min"], cur)
		self.data["max"] = max(self.data["max"], cur)
		# Pickle
		pickle.dump(self.data, open( "save.p", "wb"))
		
		self.cur = cur
		self.prev = time()
		self.conPrint("Battle Finished")
	
	def conPrint(self, msg, i=0):
		clearConsole()
		
		if self.cur:
			print(" --- Session Data --- ")
			print("Count:", self.total_count)
			print("Time:", round((self.prev - self.total) / 60, 2), "minutes")
			print("Average:", round(((self.prev - self.total) / 60) / self.total_count, 2), "minutes")
			print("Last run time: ", self.cur, "minutes\n")
		
			print(" -- Total Data --- ")
			print(*[f"{a.capitalize()}: {round(self.data[a], 2)}" for a in self.data], sep = "\n")
			print("Average:", round(self.data["time"] / self.data["count"], 2), "minutes")
			print()
		
		print(f"Progress: [{'x'*i}{' '*(4-i)}] {msg}")
		#for client in self.clients:
		#	zone = client.zone_name()
		#	print(f"Current zone: {zone}")
		if not self.running:
			print("Bot stopping after current cycle")
		if self.paused:
			print("Bot pausing or paused")
		
		print("\n --- Commands ---\n\tq: exit\n\tp: pause\n\ts: start")
		

	async def auto_buy_potions_TP(self):
		return
		# Head to home world gate
		await asyncio.sleep(0.1)
		await self.send_key(Keycode.HOME, 0.1)
		await self.wait_for_zone_change()
		while not await self.is_in_npc_range():
			await self.send_key(Keycode.S, 0.1)
		await self.send_key(Keycode.X, 0.1)
		await asyncio.sleep(1.2)
		# Go to Wizard City
		await self.mouse_handler.click_window_with_name('wbtnWizardCity')
		await asyncio.sleep(0.3)
		await self.mouse_handler.click_window_with_name('teleportButton')
		await self.wait_for_zone_change()
		await asyncio.sleep(0.3)
		# TP to potion vendor
		await self.teleport(XYZ(-7.503681, -3141.505859, 244.030518), False)
		await self.send_key(Keycode.A, 0.1)
		await asyncio.sleep(0.1)
		await self.wait_for_zone_change()
		await self.teleport(XYZ(-1.195801, -2155.578125, -153.288666), False)
		await self.send_key(Keycode.A, 0.1)
		await asyncio.sleep(0.1)
		await self.wait_for_zone_change()
		await self.teleport(XYZ(-4352.091797, 1111.261230, 229.000793), False)
		await self.send_key(Keycode.A, 0.1)
		await asyncio.sleep(0.5)
		if not await self.is_in_npc_range():
			await self.teleport(XYZ(-4352.091797, 1111.261230, 229.000793), False)
			await self.send_key(Keycode.A, 0.1)
			await asyncio.sleep(3.5)
		await self.send_key(Keycode.X, 0.1)
		await asyncio.sleep(1) 
		# Buy potions
		for i in self.potion_ui_buy:
			await self.mouse_handler.click_window_with_name(i)
			await asyncio.sleep(1)
		# Return to marker
		await self.send_key(Keycode.PAGE_UP, 0.1)
		await self.wait_for_zone_change()
		await self.send_key(Keycode.PAGE_DOWN, 0.1)
		if await self.needs_mana(mana_percent=5):
			self.conPrint(f'[{self.title}] Needs mana, quick teleporting to the Athenium and collecting mana wisps')
			await self.collect_quick_manawisps()
	
	async def needs_mana(self, mana_percent: int = 10) -> bool:
		return await self.calc_mana_ratio() * 100 <= mana_percent

	async def needs_health(self, health_percent: int = 20) -> bool:
		return await self.calc_health_ratio() * 100 <= health_percent

	async def calc_health_ratio(self) -> float:
		"""Simply returns current health divided by max health"""
		return await self.stats.current_hitpoints() / await self.stats.max_hitpoints()

	@staticmethod
	async def calc_mana_ratio(self) -> float:
		"""Simply returns current health divided by max health"""
		return await self.stats.current_mana() / await self.stats.max_mana()


# Fix for CombatMember Error -Thanks to Starrfox
class SeanNoLikeMobs(SprintyCombat):
	async def get_client_member(self):
		return await utils.wait_for_non_error(super().get_client_member)


class UserInput(Thread):
	def __init__(self, lm : LoremasterBot):
		Thread.__init__(self)
		self.lm = lm
		
	def run(self):
		while True:
			inp = input()
			if inp == "q":
				print("Finishing battle and exiting bot")
				self.lm.running = False
				break
			elif inp == "p":
				print("Pausing bot")
				self.lm.running = False
			elif inp == "s":
				print("Starting bot")
				self.lm.paused = True
		self.lm.running = False # in the event of a keyboard interupt

async def startBot(loremasterbot : LoremasterBot):
	try:
		await loremasterbot.run()
	except:
		import traceback
		traceback.print_exc()
	
		
# Error Handling
async def main():
	loremasterbot = LoremasterBot() 
	userInput = UserInput(loremasterbot)
	userInput.start()
	await startBot(loremasterbot)
	userInput.join()
	await loremasterbot.close()


# Start
if __name__ == "__main__":
	asyncio.run(main())
