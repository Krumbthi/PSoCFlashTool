import serial
import time
import os
import argparse
import logging
import struct

from flashtool import FlashTool
import crc16pure


# -------------------------------------------------------------------------------
# Defines
# -------------------------------------------------------------------------------
FORMAT='%(asctime)-15s %(name)s - %(levelname)s - %(message)s'

# -------------------------------------------------------------------------------
# Declarations
# -------------------------------------------------------------------------------
logging.basicConfig(format=FORMAT)
Logger = logging.getLogger(__name__)
Logger.setLevel(logging.DEBUG)


# -------------------------------------------------------------------------------
# Classes
# -------------------------------------------------------------------------------
class FlashApp:
    SAP_ID = 0x01
    RUN_BOOTLOADER = 0x85

    def __init__(self, device, baudrate):
        try:
            self.device = serial.Serial(port=device, baudrate=baudrate, timeout=3)
        except:
            Logger.debug('Connection error')

    def switch_to_bl_mode(self):
        Logger.debug('switch to bootloader mode')
        packet = struct.pack(">BBHH", self.SAP_ID, self.RUN_BOOTLOADER, 2, 1)

        checksum = crc16pure.calculateCRC2(packet, len(packet))
        packet = packet + struct.pack('<H', checksum)
        self.device.write(packet)

        ret = self.device.read(8)
        Logger.debug(ret)

    def start_fw(self, callback=None):
        ft = FlashTool(self.device, lambda d: print(d))
        # jump into firmware
        ft.startFirmware()
        self.device.close()

    def flash_fw(self, fileName):
        ft = FlashTool(self.device, callback=lambda d: print(d))
        ft.readFirmware(fileName)
        #ft.flash()
        Logger.debug(ft.getFirmwareMetadata())
        retval = ft.getPsocMetadata()

        Logger.debug("Flashing FW done: %s" % retval)

        # jump into firmware
        ft.startFirmware()
        Logger.debug('start FW')

        # backup fw file
        timestamp = time.strftime('%H%M-%Y%m%d')
        os.rename(fileName, '%s_%s.bak' % (fileName, timestamp))

def main():
    parser = argparse.ArgumentParser(description="Flash PSoC firmware")
    parser.add_argument("-v", "--verbosity", help="increase output verbosity", action="store_true")
    req_args = parser.add_argument_group('required named arguments')
    req_args.add_argument("-f", "--firmware", help="path of the firmware file", type=str, required=True)
    req_args.add_argument("-d", "--device", help="communication device", type=str, required=True)
    req_args.add_argument("-s", "--speed", help="baudrate of the communication device ", type=int, required=True)
    parser.add_argument("-r", "--run", help="Run PSoC firmware ", type=int)

    args = parser.parse_args()

    fn = os.path.normpath(str(args.firmware))
    Logger.debug(fn)

    if args.device and args.speed:
        fl_app = FlashApp(args.device, args.speed)
    else:
        Logger.debug('no port given')
        exit(1)
    
    if args.run:
        fl_app.start_fw()
        exit(0)

    if os.path.isfile(fn):
        fl_app.switch_to_bl_mode()
        fl_app.flash_fw(fn)
    else:
        Logger.debug('no such file or directory')


# -------------------------------------------------------------------------------
# Main loop
# -------------------------------------------------------------------------------
if __name__ == "__main__":
    main()

