#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
import coloredlogs
from ph4_walkingpad.pad import Scanner, Controller, WalkingPad

# Set up logging
coloredlogs.install(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def main():
    """Simple example of scanning for and connecting to a WalkingPad device"""
    
    # Create scanner instance
    scanner = Scanner()
    
    # Scan for walking pad devices
    print("Scanning for WalkingPad devices...")
    await scanner.scan(timeout=5.0, dev_name="KS-HD-Z1D")
    
    if scanner.walking_belt_candidates:
        # Connect to the first found device
        device = scanner.walking_belt_candidates[0]
        print(f"Found WalkingPad: {device.name} ({device.address})")
        
        # Create controller and connect
        controller = Controller(address=device.address, do_read_chars=False)
        controller.log_messages_info = False  # Enable debug logging for messages
        
        try:
            # Connect to the device
            await controller.run()
            
            # Check if the device is compatible
            if controller.char_fe01 is None or controller.char_fe02 is None:
                print(f"Device {device.name} connected but is not compatible with WalkingPad protocol")
                print("Missing required characteristics (fe01/fe02)")
            else:
              print(f"Connected to walking pad: {device.name}")
              
              # Ask for device profile/status
              await controller.ask_profile()
              await asyncio.sleep(1.0)
              
              # Ask for current stats
              await controller.ask_stats()
              
              # Wait until user terminates the program
              print("Monitoring device data... Press Ctrl+C to exit")
              try:
                  while True:
                      await asyncio.sleep(1.0)
              except (KeyboardInterrupt, asyncio.CancelledError):
                  print("\nTerminating...")
              
              print("Basic connection test completed successfully!")
            
        except Exception as e:
            logger.error(f"Error connecting to device: {e}")
        finally:
            # Clean up connection
            await controller.disconnect()
            
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
