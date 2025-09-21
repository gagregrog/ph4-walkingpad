#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
import coloredlogs
import os
from ph4_walkingpad.pad import Scanner, Controller
from datetime import datetime

KNOWN_DEVICE = "99DB0444-F2EF-9F38-4238-E4CC8C1E00F3"


should_start = False
should_get_speed = False
should_change_speeds = False

def decode_treadmill_message(data):
    """
    Decode a 17-byte treadmill notification message.
    
    Message format (17 bytes):
    [0-1]: Header - always 84 24
    [2-3]: Speed (little-endian) - speed in units of 10 meters / 1 hour (0.01km/h)
    [4-5]: Distance (little-endian) - distance in meters (byte5 << 8 | byte4)
    [6]: Unknown - likely the most significant byte of distance
    [7]: Calories burned - cumulative calories in kcal
    [8-11]: Unknown - likely includes two more bytes for calories
    [12-13]: Time (little-endian) - seconds since start (can exceed 255)
    [14]: Unknown - likely the next significant byte of the time
    [15-16]: Unknown
    """
    if len(data) != 17:
        return None
    
    try:
        # Parse message components
        header = (data[1] << 8) | data[0]
        speed_raw = (data[3] << 8) | data[2] # bytes 2,3 in little endian (THIS IS CORRECT, DO NOT CHANGE THIS!!!)
        distance_raw = (data[5] << 8) | data[4]  # bytes 4,5 in little endian - distance in meters (THIS IS CORRECT, DO NOT CHANGE THIS!!!)
        calories = data[7]
        time_seconds = (data[13] << 8) | data[12]  # bytes 12,13 in little endian for time > 255 (THIS IS CORRECT, DO NOT CHANGE THIS!!!)
        
        # Calculate derived values
        # Distance: bytes 4,5 represent distance in meters
        distance_meters = distance_raw
        distance_miles = distance_meters / 1609.344  # Convert meters to miles
        distance_km = distance_meters / 1000.0  # Convert meters to km
        
        speed_kmh = speed_raw * 0.01  # (THIS IS CORRECT, DO NOT CHANGE THIS!!!)
        speed_mph = speed_kmh * 0.6213711922
        
        is_running = speed_kmh > 0
        
        return {
            'is_running': is_running,
            'speed_kmh': speed_kmh,
            'speed_mph': speed_mph,
            'calories': calories,
            'time_seconds': time_seconds,
            'time_formatted': f"{time_seconds // 60:02d}:{time_seconds % 60:02d}",
            'distance_km': distance_km,
            'distance_miles': distance_miles,
        }
    except Exception:
        return None
    
# Add custom message handler to see raw data
def custom_handler(sender, data, already_notified):
  if not already_notified:
      # Try to decode the message using our improved decoder
      decoded = decode_treadmill_message(data)
      
      if decoded:
          # Display decoded information
          status_emoji = "🟢" if decoded['is_running'] else "🛑"
          status_text = "Running" if decoded['is_running'] else "Stopped"
          
          print(f"{status_emoji} Status: {status_text}")
          print(f"🏃 Speed: {decoded['speed_kmh']:.1f} km/h ({decoded['speed_mph']:.1f} mph)")
          print(f"📏 Distance: {decoded['distance_km']:.3f} km ({decoded['distance_miles']:.3f} miles)")
          print(f"🔥 Calories: {decoded['calories']} kcal")
          print(f"⏱️  Time: {decoded['time_formatted']} ({decoded['time_seconds']}s)")
          print("---")

# Set up logging to both console and file
# Create logs directory if it doesn't exist
logs_dir = "logs"
os.makedirs(logs_dir, exist_ok=True)

log_filename = os.path.join(logs_dir, f"walkingpad_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

# Create logger
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Create file handler
file_handler = logging.FileHandler(log_filename)
file_handler.setLevel(logging.DEBUG)

# Create console handler with coloredlogs
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

# Create formatter
formatter = logging.Formatter('%(asctime)s %(name)s[%(process)d] %(levelname)s %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add handlers to logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Also apply coloredlogs to the console
coloredlogs.install(level=logging.DEBUG, logger=logger)

print(f"📝 Logging to file: {log_filename}")
logger = logging.getLogger(__name__)


async def main():
    device = None
    if KNOWN_DEVICE:
      device = { 'address': KNOWN_DEVICE, 'name': "Known Device" }
    else:
      # Create scanner instance
      scanner = Scanner()
    
      # Scan for walking pad devices
      print("Scanning for WalkingPad devices...")
      await scanner.scan(timeout=5.0, dev_name="KS-HD-Z1D")

      if scanner.walking_belt_candidates:
        # Connect to the first found device
        ble_device = scanner.walking_belt_candidates[0]
        device = { 'name': ble_device.name, 'address': ble_device.address } 
    
    if device:
        print(f"Connecting to device: {device['name']} ({device["address"]})")
        
        # Create controller and connect
        controller = Controller(address=device["address"], do_read_chars=False)
        controller.log_messages_info = True  # Show all messages as INFO
         
        try:
            # Connect to the device
            await controller.run()
            
            # Set up message handler
            controller.handler_message = custom_handler
            
            # Check if the device is compatible
            if controller.char_fe01 is None or controller.char_fe02 is None:
                print(f"Device {device["name"]} connected but is not compatible with WalkingPad protocol")
                print("Missing required characteristics (fe01/fe02)")
            else:
                print(f"Connected to walking pad: {device["name"]}")
              
                if should_get_speed:
                  try:
                      print("Reading supported speed range...")
                      # # Try to read the supported speed range characteristic (2AD4)
                      if hasattr(controller, 'client') and controller.client:
                          speed_range = await controller.client.read_gatt_char("00002ad4-0000-1000-8000-00805f9b34fb")
                          print(f"Speed range data: {speed_range.hex()}")
                  except Exception as e:
                      print(f"Could not read speed range: {e}")

                
                # WILL NOT ACCEPT START COMMANDS WITHOUT SENDING THIS BLOCK
                # Request Control Point features (OpCode 0x00)
                features_cmd = bytearray([0x00])
                await controller.send_cmd_raw(features_cmd)
                await asyncio.sleep(1.0)

                if should_start:
                    try:
                        print("Sending start command...")
                        # Start/Resume command (OpCode 0x07)
                        start_cmd = bytearray([0x07])  # Standard "Start or Resume" command
                        await controller.send_cmd_raw(start_cmd)
                        print("Sent standard start command")
                        await asyncio.sleep(3.0)
                        
                        await asyncio.sleep(1.5)
                        features_cmd = bytearray([0x00])
                        await controller.send_cmd_raw(features_cmd)

                        # here here here
                        await asyncio.sleep(3.0)
                        
                    except Exception as e:
                        print(f"Start/stop test failed: {e}")
              
                if should_change_speeds:
                    # Now try setting speeds with different approaches
                    speeds_to_try = [
                        # (0xA0, "1.6 km/h (1.0 mph)"),  # Starting speed
                        (0x140, "3.2 km/h (2.0 mph)"), # 2 mph
                        (0x1E0, "4.8 km/h (3.0 mph)"), # 3 mph
                        (0x280, "6.4 km/h (4.0 mph)"), # 4 mph
                        (0xF0, "2.4 km/h (1.5 mph)"),  # 1.5 mph
                    ]
                    
                    # Must send this command before speed commands will be accepted
                    await controller.send_cmd_raw(bytearray([0x08]))

                    for speed_hex, speed_name in speeds_to_try:
                        try:
                            print(f"Setting target speed to {speed_name}...")
                            speed_low = speed_hex & 0xFF
                            speed_high = (speed_hex >> 8) & 0xFF
                            speed_cmd = bytearray([0x02, speed_low, speed_high])
                            await controller.send_cmd_raw(speed_cmd)
                            await asyncio.sleep(5.0)
                            
                            print(f"Sent speed command: 0x02, 0x{speed_low:02x}, 0x{speed_high:02x}")
                            
                        except Exception as e:
                            print(f"Speed command for {speed_name} failed: {e}")
              
                # Wait until user terminates the program
                print("Motor start attempted! Monitoring device data... Press Ctrl+C to exit")
                try:
                    print("\n\n\n\nMADE IT!!!!\n\n\n\n")
                    while True:
                        await asyncio.sleep(1.0)
                except (KeyboardInterrupt, asyncio.CancelledError):
                    pass
                
        except Exception as e:
            logger.error(f"Error connecting to device: {e}")
        finally:
            try:
                await controller.disconnect()
                print("✅ Disconnected from device")
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")
            
    else:
        print("No WalkingPad devices found")


if __name__ == "__main__":
    # Run the async main function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print("Program terminated due to error")
