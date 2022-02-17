from __future__ import print_function

import argparse
from datetime import datetime
import sys
import time
import zipfile
import json

from esphomeflasher.common import open_downloadable_binary, open_binary_from_zip
from esphomeflasher.common import fujinet_version_info, is_url

import esptool
import serial

from esphomeflasher import const
from esphomeflasher.common import ESP32ChipInfo, EsphomeflasherError, chip_run_stub, \
    configure_write_flash_args, detect_chip, detect_flash_size, read_chip_info, \
    read_firmware_info, MockEsptoolArgs
from esphomeflasher.const import ESP32_DEFAULT_BOOTLOADER_FORMAT, ESP32_DEFAULT_OTA_DATA, \
    ESP32_DEFAULT_PARTITIONS, ESP32_DEFAULT_FIRMWARE, ESP32_DEFAULT_SPIFFS, \
    FUJINET_VERSION_INFO, FUJINET_RELEASE_INFO
from esphomeflasher.helpers import list_serial_ports

def parse_args(argv):
    parser = argparse.ArgumentParser(prog='esphomeflasher {}'.format(const.__version__))
    parser.add_argument('-p', '--port',
                        help="Select the USB/COM port for uploading.")
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument('--esp8266', action='store_true')
    group.add_argument('--esp32', action='store_true')
    group.add_argument('--upload-baud-rate', type=int, default=460800,
                       help="Baud rate to upload with (not for logging)")
    parser.add_argument('--bootloader',
                        help="(ESP32-only) The bootloader to flash.",
                        default=ESP32_DEFAULT_BOOTLOADER_FORMAT)
    parser.add_argument('--partitions',
                        help="(ESP32-only) The partitions to flash.",
                        default=ESP32_DEFAULT_PARTITIONS)
    parser.add_argument('--otadata',
                        help="(ESP32-only) The otadata file to flash.",
                        default=ESP32_DEFAULT_OTA_DATA)
    parser.add_argument('--spiffs',
                        help="(ESP32-only) The SPIFFS file to flash.",
                        default=ESP32_DEFAULT_SPIFFS)
    parser.add_argument('--no-erase',
                        help="Do not erase flash before flashing",
                        action='store_true')
    parser.add_argument('--show-logs', help="Only show logs", action='store_true')
    parser.add_argument('--package', help="Flag to indicate the binary is a firmware package (zip which contains "
                                          "firmware, bootloader, partitions, SPIFFS and OTA data).",
                        action='store_true')
    parser.add_argument('binary', help="The binary image to flash.",
                        default=ESP32_DEFAULT_FIRMWARE)

    return parser.parse_args(argv[1:])

def select_port(args):
    if args.port is not None:
        print(u"Using '{}' as serial port.".format(args.port))
        return args.port
    ports = list_serial_ports()
    if not ports:
        raise EsphomeflasherError("No serial port found!")
    if len(ports) != 1:
        print("Found more than one serial port:")
        for port, desc in ports:
            print(u" * {} ({})".format(port, desc))
        print("Please choose one with the --port argument.")
        raise EsphomeflasherError
    print(u"Auto-detected serial port: {}".format(ports[0][0]))
    return ports[0][0]

def show_logs(serial_port):
    print("Showing logs:")
    with serial_port:
        while True:
            try:
                raw = serial_port.readline()
            except serial.SerialException:
                print("Serial port closed!")
                return
            text = raw.decode(errors='ignore')
            line = text.replace('\r', '').replace('\n', '')
            time = datetime.now().time().strftime('[%H:%M:%S] ')
            message = time + line
            try:
                print(message)
            except UnicodeEncodeError:
                print(message.encode('ascii', 'backslashreplace'))

# def detect_current_firmware(argv):
#     args = parse_args(argv)
#     port = select_port(args)
#     serial_port = serial.Serial(port, baudrate=921600)

#     print("Checking for current firmware version:")

#     # chip = detect_chip(port, args.esp8266, args.esp32)
#     # print("Resetting...")
#     # chip.hard_reset()
#     # chip.soft_reset(True)
#     print("Reset FujiNet now (button C)")

#     count = 1
#     with serial_port:
#         while True:
#             try:
#                 raw = serial_port.readline()
#             except serial.SerialException:
#                 print("Serial port closed!")
#                 return
#             text = raw.decode(errors='ignore')
#             line = text.replace('\r', '').replace('\n', '')
#             # message = line
#             # try:
#             #     print(message)
#             # except UnicodeEncodeError:
#             #     print(message.encode('ascii', 'backslashreplace'))
#             # count += 1
#             match = FN_VERSION_RE.match(text)
#             if match is None:
#                 if count < 50:
#                     continue
#                 print("Unable to detect current firmware version.")
#                 break
#             # TODO:
#             print("Detected Version: ", match.group(1))
#             print("Build Time: ", match.group(2))
#             break

def run_esphomeflasher(argv):
    """run esphomeflasher with command line arguments"""
    # parse arguments
    args = parse_args(argv)
    # run flasher
    return run_esphomeflasher_args(args)

def run_esphomeflasher_kwargs(**kwargs):
    """run esphomeflasher with key=value,... arguments"""
    # prepare args
    args_dct = {
        'port': None,
        'esp8266': False,
        'esp32': False,
        'upload_baud_rate': 460800,
        'bootloader': ESP32_DEFAULT_BOOTLOADER_FORMAT,
        'partitions': ESP32_DEFAULT_PARTITIONS,
        'otadata': ESP32_DEFAULT_OTA_DATA,
        'spiffs': ESP32_DEFAULT_SPIFFS,
        'no_erase': False,
        'show_logs': False,
        'package': False,
        'binary': ESP32_DEFAULT_FIRMWARE
    }
    args_dct.update(kwargs)
    args = argparse.Namespace(**args_dct)
    # run flasher
    return run_esphomeflasher_args(args)

def run_esphomeflasher_args(args):
    """run esphomeflasher with Namespace args object"""
    port = select_port(args)
    if args.show_logs:
        serial_port = serial.Serial(port, baudrate=921600)
        show_logs(serial_port)
        return

    print("Starting firmware upgrade...")
    if is_url(args.binary):
        print("Getting firmware: {}".format(args.binary))

    if args.package:
        # args.binary is zip file
        package = open_downloadable_binary(args.binary)
        zf = zipfile.ZipFile(package, 'r')
        addr_filename = []
        release_info = json.load(open_binary_from_zip(zf, FUJINET_RELEASE_INFO))
        filecount = 0
        # Get all the partition files ready
        for f in release_info['files']:
            fname = f['filename'][:len(f['filename']) - 4]
            thisfile = open_downloadable_binary(open_binary_from_zip(zf, f['filename']))
            addr_filename.append((int(f['offset'], 16), thisfile))
            # Verify "firmware" magic # and grab flash mode/frequency
            if fname == 'firmware':
                flash_mode, flash_freq = read_firmware_info(thisfile)
            filecount += 1
            print("File " + format(filecount) + ": " + format(f['filename']) + ", Offset: " + format(f['offset']))

        # Display firmware details
        print("FujiNet Version: {}".format(release_info['version']))
        print("Version Date: {}".format(release_info['version_date']))
        print("GIT Commit: {}".format(release_info['git_commit']))
        zf.close()
    else:
        firmware, bootloader, partitions, otadata, spiffs = \
            args.binary, args.bootloader, args.partitions, args.otadata, args.spiffs

    chip = detect_chip(port, args.esp8266, args.esp32)
    info = read_chip_info(chip)

    print()
    print("Chip Info:")
    print(" - Chip Family: {}".format(info.family))
    print(" - Chip Model: {}".format(info.model))
    if isinstance(info, ESP32ChipInfo):
        print(" - Number of Cores: {}".format(info.num_cores))
        print(" - Max CPU Frequency: {}".format(info.cpu_frequency))
        print(" - Has Bluetooth: {}".format('YES' if info.has_bluetooth else 'NO'))
        print(" - Has Embedded Flash: {}".format('YES' if info.has_embedded_flash else 'NO'))
        print(" - Has Factory-Calibrated ADC: {}".format(
            'YES' if info.has_factory_calibrated_adc else 'NO'))
    else:
        print(" - Chip ID: {:08X}".format(info.chip_id))

    print(" - MAC Address: {}".format(info.mac))

    stub_chip = chip_run_stub(chip)

    if args.upload_baud_rate != 115200:
        try:
            stub_chip.change_baud(args.upload_baud_rate)
        except esptool.FatalError as err:
            raise EsphomeflasherError("Error changing ESP upload baud rate: {}".format(err))

    flash_size = detect_flash_size(stub_chip)
    print(" - Flash Size: {}".format(flash_size))

    mock_args = MockEsptoolArgs(flash_size, addr_filename, flash_mode, flash_freq)

    print(" - Flash Mode: {}".format(mock_args.flash_mode))
    print(" - Flash Frequency: {}Hz".format(mock_args.flash_freq.upper()))

    try:
        stub_chip.flash_set_parameters(esptool.flash_size_bytes(flash_size))
    except esptool.FatalError as err:
        raise EsphomeflasherError("Error setting flash parameters: {}".format(err))

    if not args.no_erase:
        try:
            esptool.erase_flash(stub_chip, mock_args)
        except esptool.FatalError as err:
            raise EsphomeflasherError("Error while erasing flash: {}".format(err))

    try:
        esptool.write_flash(stub_chip, mock_args)
    except esptool.FatalError as err:
        raise EsphomeflasherError("Error while writing flash: {}".format(err))

    print("Hard Resetting...")
    stub_chip.hard_reset()

    print("Done! Flashing is complete!")
    print()

    if args.upload_baud_rate != 921600:
        stub_chip._port.baudrate = 921600
        time.sleep(0.05)  # get rid of crap sent during baud rate change
        stub_chip._port.flushInput()

    show_logs(stub_chip._port)

def main():
    try:
        if len(sys.argv) <= 1:
            from esphomeflasher import gui

            return gui.main() or 0
        return run_esphomeflasher(sys.argv) or 0
    except EsphomeflasherError as err:
        msg = str(err)
        if msg:
            print(msg)
        return 1
    except KeyboardInterrupt:
        return 1

if __name__ == "__main__":
    sys.exit(main())
