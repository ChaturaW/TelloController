"""
Tello keyboard controller & FPV based on tellopy & cv2  

Controls:
- tab to lift off
- arrow keys to move the drone
- space/shift to ascend/descent slowly
- Q/E to yaw slowly
- WSAD to ascend, descend, or yaw quickly
- backspace to land, or P to palm-land
"""

import time
import sys
import tellopy
import pygame
import pygame.display
import pygame.key
import pygame.locals
import pygame.font
import av
#import cv2
import numpy
import os
#import datetime
import threading
import traceback
#from subprocess import Popen, PIPE

screen = None
stop_video_thread = False
videoThread = None
prev_flight_data = None
video_player = None
video_recorder = None
font = None
wid = None
date_fmt = '%Y-%m-%d_%H%M%S'

def palm_land(drone, speed):
    if speed == 0:
        return
    drone.palm_land()

def exit_app(drone):
    global stop_video_thread
    print("Attempting to stop the application..")
    drone.quit() 
    stop_video_thread = True
    #time.sleep(5)
    print("Exiting application..")
       
    sys.exit()

controls = {
    'w': lambda drone, speed: drone.up(speed),
    's': lambda drone, speed: drone.down(speed),
    'a': lambda drone, speed: drone.counter_clockwise(speed),
    'd': lambda drone, speed: drone.clockwise(speed),
    'space': 'up',
    'left shift': 'down',
    'right shift': 'down',
    'q': 'counter_clockwise',
    'e': 'clockwise',
    # arrow keys for fast turns and altitude adjustments
    'left': lambda drone, speed: drone.left(speed), #'left',
    'right': lambda drone, speed: drone.right(speed), #'right',
    'up': lambda drone, speed: drone.forward(speed), #'forward',
    'down': lambda drone, speed: drone.backward(speed), #'backward',
    'tab': lambda drone, speed: drone.takeoff(),
    'backspace': lambda drone, speed: drone.land(),    
    'p': palm_land           
}


class FlightDataDisplay(object):
    # previous flight data value and surface to overlay
    _value = None
    _surface = None
    # function (drone, data) => new value
    # default is lambda drone,data: getattr(data, self._key)
    _update = None
    def __init__(self, key, format, colour=(255,255,255), update=None):
        self._key = key
        self._format = format
        self._colour = colour

        if update:
            self._update = update
        else:
            self._update = lambda drone,data: getattr(data, self._key)

    def update(self, drone, data):
        new_value = self._update(drone, data)
        if self._value != new_value:
            self._value = new_value
            self._surface = font.render(self._format % (new_value,), True, self._colour)
        return self._surface

def flight_data_mode(drone, *args):
    return (drone.zoom and "VID" or "PIC")

def update_hud(hud, drone, flight_data):
    (w,h) = (158,0) # width available on side of screen in 4:3 mode
    blits = []
    for element in hud:
        surface = element.update(drone, flight_data)
        if surface is None:
            continue
        blits += [(surface, (0, h))]
        # w = max(w, surface.get_width())
        h += (surface.get_height() + 20)
    h += 64  # add some padding
    overlay = pygame.Surface((w, h), pygame.SRCALPHA)
    overlay.fill((21,27,31)) # remove for mplayer overlay mode
    for blit in blits:
        overlay.blit(*blit)
    pygame.display.get_surface().blit(overlay, (20,20))
    pygame.display.update(overlay.get_rect())

def status_print(text):
    pygame.display.set_caption(text)

hud = [
    FlightDataDisplay('height', 'ALT %3d'),
    FlightDataDisplay('ground_speed', 'SPD %3d'),
    FlightDataDisplay('battery_percentage', 'BAT %3d%%'),
    FlightDataDisplay('wifi_strength', 'NET %3d%%'),
    FlightDataDisplay(None, 'CAM %s', update=flight_data_mode),
    # FlightDataDisplay(None, '%s', colour=(255, 0, 0), update=flight_data_recording),
]

def flightDataHandler(event, sender, data):
    global prev_flight_data
    text = str(data)
    if prev_flight_data != text:
        update_hud(hud, sender, data)
        prev_flight_data = text

def video_thread():
    global drone    
    global av
    global screen
    global stop_video_thread

    print('?????????? START Video thread')
    drone.start_video()
    try:                                                                                                                                    
        container = av.open(drone.get_video_stream())
        frame_count = 0
        while True:
            if stop_video_thread:
                break    
            for frame in container.decode(video=0):
                frame_count = frame_count + 1
                # skip first 300 frames                                                                                                                                                        
                #if frame_count < 300:
                #    continue                
                image = numpy.array(frame.to_image())
                image = image.swapaxes(0,1)                
                image = pygame.surfarray.make_surface(image)
                screen.blit(image, (180,0))
                pygame.display.update()                                            
        #cv2.destroyWindow('Original')
    except KeyboardInterrupt as e:
        print("?????????? KEYBOARD INTERRUPT Video thread " + e)
    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_exception(exc_type, exc_value, exc_traceback)
        print("?????????? EXCEPTION Video thread " + e)

def main():
    global screen
    pygame.init()
    pygame.display.set_caption('CIS Drone Controller')
    pygame.display.init()
    screen = pygame.display.set_mode((1280, 720))
    pygame.font.init()

    global font
    font = pygame.font.SysFont("dejavusansmono", 28)

    global wid
    if 'window' in pygame.display.get_wm_info():
        wid = pygame.display.get_wm_info()['window']
    print("Tello video WID:", wid)

    screen.fill((21, 27, 31))
    pygame.display.update()

    global drone
    drone = tellopy.Tello()
    drone.connect()
    #drone.start_video()
    drone.subscribe(drone.EVENT_FLIGHT_DATA, flightDataHandler)    
    speed = 60
    
    global stop_video_thread

    try:
        videoThread = threading.Thread(target=video_thread)
        videoThread.start()

        while 1:
            time.sleep(0.01)  # loop with pygame.event.get() is too mush tight w/o some sleep
            for e in pygame.event.get():
                
                if e.type == pygame.locals.KEYDOWN:
                    print('+' + pygame.key.name(e.key))
                    keyname = pygame.key.name(e.key)
                    if keyname == 'b':
                        exit_app(drone) 
                    if keyname == 'j':
                        print("speed - 30")
                        speed = 30
                    if keyname == 'k':
                        print("speed - 60")
                        speed = 60
                    if keyname == 'l':
                        print("speed - 120")
                        speed = 120                       
                    if keyname in controls:
                        key_handler = controls[keyname]
                        if type(key_handler) == str:
                            getattr(drone, key_handler)(speed)
                        else:
                            key_handler(drone, speed)

                elif e.type == pygame.locals.KEYUP:
                    print('-' + pygame.key.name(e.key))
                    keyname = pygame.key.name(e.key)
                    if keyname in controls:
                        key_handler = controls[keyname]
                        if type(key_handler) == str:
                            getattr(drone, key_handler)(0)
                        else:
                            key_handler(drone, 0)
    except e:
        print(str(e))
    finally:
        print('Shutting down connection to drone...')        
        drone.quit()
        exit(1)

if __name__ == '__main__':
    main()
