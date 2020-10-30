import re

__version__ = "1.2.0"

ESP32_DEFAULT_BOOTLOADER_FORMAT = 'https://fujinet.online/firmware/bootloader.bin'
ESP32_DEFAULT_OTA_DATA = 'https://fujinet.online/firmware/boot_app0.bin'
ESP32_DEFAULT_PARTITIONS = 'https://fujinet.online/firmware/partitions.bin'
ESP32_DEFAULT_FIRMWARE = 'https://fujinet.online/firmware/firmware.bin'
ESP32_DEFAULT_SPIFFS = 'https://fujinet.online/firmware/spiffs.bin'
FUJINET_VERSION_URL = 'https://fujinet.online/firmware-dl/version_info.txt'

# https://stackoverflow.com/a/3809435/8924614
HTTP_REGEX = re.compile(r'https?://(www\.)?[-a-zA-Z0-9@:%._+~#=]{2,256}\.[a-z]{2,6}\b([-a-zA-Z0-9@:%_+.~#?&/=]*)')
