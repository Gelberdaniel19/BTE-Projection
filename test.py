from pynput.keyboard import Key, Listener
import keyboard
import pymem
import pymem.process
import pywinauto
from pywinauto.keyboard import send_keys
import pyperclip
import easygui
import time
import threading

''' Global variable which, when triggered, will stop sending
commands to Minecraft. Used like a kill switch. '''
stop_routine = False

''' List of coordinates loaded from google earth pro. '''
coords_list = []

''' Thread which runs minecraft commands. '''
execution_thread = None

''' Get the longitude, latitude, altitude tuple from google earth
based on the current mouse position of the user in the google earth
pro graphical interface. '''
def get_coords_from_gep():
	pm = pymem.Pymem("googleearth.exe")
	client = pymem.process.module_from_name(pm.process_handle, "googleearth_pro.dll").lpBaseOfDll
	addr1 = pm.read_longlong(client + 0x0272EDD8)
	addr2 = pm.read_longlong(addr1 + 0x8)
	addr3 = pm.read_longlong(addr2 + 0x28)
	addr4 = pm.read_longlong(addr3 + 0xF0)
	latitude = pm.read_double(addr4 + 0x78)
	longitude = pm.read_double(addr4 + 0x70)
	altitude = pm.read_double(addr4 + 0x80)
	return latitude, longitude, altitude

''' Bring the minecraft window into focus. '''
def focus_minecraft():
	minecraft_handle = pywinauto.Application().connect(title_re="Minecraft.*")
	minecraft_window = minecraft_handle['Minecraft 1.12.2']
	minecraft_window.set_focus()

''' Sent a chat message/command in the minecraft window. '''
def send_chat(command):
	pyperclip.copy(command)
	send_keys("t", vk_packet=False)
	send_keys("^v", vk_packet=False)
	send_keys("~", vk_packet=False)
	time.sleep(0.2)
	print("Sent command: ", command)

''' Draws a polygon. Accounts for some extra ping on servers. '''
def draw_poly(polygon_coords_list):
	# Focus and unpause
	focus_minecraft()
	send_keys("{VK_ESCAPE}", pause=0.2)

	# Initial position
	la, lo, al = polygon_coords_list[0]
	altitude = f"{al}"
	altitude = altitude[:altitude.find('.')]
	send_chat(f"/tpll {la} {lo}")
	time.sleep(1)
	send_chat(f"/tp ~ {altitude} ~")
	send_chat(f"//pos1")
	set2 = True

	# Draw polygon
	for coord in polygon_coords_list[1:]:
		global stop_routine
		print("Stop? ", stop_routine)
		if stop_routine:
			stop_routine = False
			break
		la, lo, al = coord
		send_chat(f"/tpll {la} {lo}")
		time.sleep(0.3)
		send_chat(f"/tp ~ {altitude} ~")
		send_chat(f"//pos{2 if set2 else 1}")
		send_chat(f"//line sponge")
		set2 = not set2
		time.sleep(0.3)

''' Takes a list of coordinates and returns a new list where the
altitudes are set to the highest measured altitude plus a buffer. '''
def normalize_altitude(coords, buffer):
	copied = []
	maxheight = coords[0][2]
	for coord in coords[1:]:
		if coord[2] > maxheight: 
			maxheight = coord[2]
	for i in range(len(coords)):
		copied.append((coords[i][0], coords[i][1], maxheight + buffer))
	return copied

''' Selects an area in minecraft entirely enclosing a set
of coordinates. '''
def select_coords(coords):
	if len(coords) == 0: return

	xmin, xmax = coords[0][0], coords[0][0]
	zmin, zmax = coords[0][1], coords[0][1]
	ymin, ymax = coords[0][2], coords[0][2]
	for i in range(1, len(coords)):
		if coords[i][0] < xmin: xmin = coords[i][0]
		if coords[i][0] > xmax: xmax = coords[i][0]
		if coords[i][1] < zmin: zmin = coords[i][1]
		if coords[i][1] > zmax: zmax = coords[i][1]
		if coords[i][2] < ymin: ymin = coords[i][2]
		if coords[i][2] > ymax: ymax = coords[i][2]

	altmin = str(ymin)[:str(ymin).find('.')]
	altmax = str(ymax)[:str(ymax).find('.')]
	send_chat(f"/tpll {xmin} {zmin}")
	time.sleep(0.3)
	send_chat(f"/tp Buggo ~ {altmin} ~")
	send_chat("//pos1")
	send_chat(f"/tpll {xmax} {zmax}")
	time.sleep(0.3)
	send_chat(f"/tp Buggo ~ {altmax} ~")
	send_chat("//pos2")

''' Extends a selection of sponge some number of blocks down
onto the ground, then replaces all blocks under sponge with a
given target block. Cleans up all sponge after. '''
def expand_down(distance, block):
	focus_minecraft()
	send_keys("{VK_ESCAPE}")
	send_chat(f"//expand {distance} down")
	send_chat(f"//replace !#solid air")
	time.sleep(1)
	for i in range(distance):
		send_chat(f'//replace "air <sponge" sponge')
		time.sleep(1)
	send_chat(f'//replace "!sponge <sponge" {block}')
	time.sleep(1)
	send_chat(f'//replace sponge 0')

### User Input / Application Loop ####################################
#
''' Does something when a key is pressed. Right now only checks if
the program should exit when pressing Ctrl+Esc '''
def on_press(key):
	if keyboard.is_pressed('esc') and keyboard.is_pressed("left shift"):
		return False

''' Does something when a key is released. This is how all the
commands are triggered. The commands are:
	F6	- Clears the coordinate list from Google Earth Pro
	F7	- Adds a coordinate from Google Earth Pro
	F8	- Draws a polygon in Minecraft based on coordinates
	F9	- Selects the set of coordinates in Minecraft
	F10	- Project a sponge selection onto the ground
	Del - Cancel the current operation '''
def on_release(key):
	global coords_list
	global stop_routine

	# Kill switch
	if key == Key.delete:
		print("Stopping...")
		stop_routine = True
		
	# Clear the coords list
	if key == Key.f6:
		coords_list.clear()

	# Add a coordinate from Google Earth Pro
	if key == Key.f7:
		coords_list.append(get_coords_from_gep())

	# Draw polygon
	if key == Key.f8:
		if len(coords_list) < 2: return
		coords_list = normalize_altitude(coords_list, 10)
		global execution_thread
		if execution_thread is None or not execution_thread.is_alive():
			stop_routine = False
			execution_thread = threading.Thread(target=draw_poly, args=(list(coords_list),))
			execution_thread.start()
	
	# Select coords list in Minecraft
	if key == Key.f9:
		select_coords(coords_list)

	# Project sponge selection onto ground
	if key == Key.f10:
		try:
			distance = int(easygui.enterbox("Distance to ground: "))
			block = easygui.enterbox("Block to project: ")
			expand_down(distance, block)
		except: 
			return
		
''' Collect keyboard events and don't exit. '''
with Listener(
		on_press=on_press,
		on_release=on_release) as listener:
	listener.join()
#
######################################################################