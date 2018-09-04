#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# Esp32PlainImageToFlashEncBoard.py
#
# A Tool to Import ESP32 plain flash partition images to
# the Flash-Encryption mode board.
#
# Copyright (c) 2018 KLab Inc.
#
# Released under the MIT license
# https://opensource.org/licenses/mit-license.php
#
# This tool enables you to import the flash partition images on
# the ESP32 board which is not in Flash-Encryption mode to
# the ESP32 board which is in Flash-Encryption mode.
#
#    ESP32 Board A                         ESP32 Board B
# +------------------+  copy & encrypt  +------------------+
# | Flash Encryption | partition images | Flash Encryption |
# |     DISABLED     | ===============> |     ENABLED      | 
# +------------------+                  +------------------+
#
# In the course of processing, images will be encrypted as necessary.
# The "Pregenerated Flash Encryption Key" is required.
# For details of Flash Encryption, refer to the following document.
# https://docs.espressif.com/projects/esp-idf/en/latest/security/flash-encryption.html
#
# Requires 'esptool', 'espefuse', 'espsecure' by Espressif Systems.
# https://github.com/espressif/esptool
#
# Supports Linux, MacOSX, Windows. Please edit the "Environment Dependent"
# section according to your environment.
#

import struct
import subprocess
import sys
import os
import glob
import serial

# common
_ESPTOOL   = 'esptool'
_ESPEFUSE  = 'espefuse'
_ESPSECURE = 'espsecure'
_ENCSUFFIX = '.CRYPT'
_ENCKEY    = './mykey.bin'

_OFS_BOOTLOADER      = '0x1000'
_LEN_BOOTLOADER      = '0x7000'
_BOOTLOADER          = _OFS_BOOTLOADER + '_bootloader.bin'

_OFS_PARTITION_TABLE = '0x8000'
_LEN_PARTITION_TABLE = '0x0c00'
_PARTITION_TABLE     = _OFS_PARTITION_TABLE + '_partition_table.bin'

# >>>>>>>> Environment Dependent >>>>>>>>>>>>

# sample for Linux
python       = '/usr/bin/python'
port         = '/dev/ttyUSB0'
baudRate     = '921600'
toolsDir     = '/home/t/esp/esp-idf/components/esptool_py/esptool/'
esptool      = toolsDir + _ESPTOOL   + '.py'
espefuse     = toolsDir + _ESPEFUSE  + '.py'
espsecure    = toolsDir + _ESPSECURE + '.py'

# sample for MacOSX
"""
port         = '/dev/tty.SLAB_USBtoUART'
baudRate     = '115200'
python       = '/usr/bin/python'
toolsDir     = '/usr/local/bin/'
esptool      = toolsDir + _ESPTOOL   + '.py'
espefuse     = toolsDir + _ESPEFUSE  + '.py'
espsecure    = toolsDir + _ESPSECURE + '.py'
"""

# sample for Windows
"""
port         = 'COM9'
baudRate     = '256000'
toolsDir     = 'C:/msys32/mingw32/bin/'
esptool      = toolsDir + _ESPTOOL   + '.py.exe'
espefuse     = toolsDir + _ESPEFUSE  + '.py.exe'
espsecure    = toolsDir + _ESPSECURE + '.py.exe'
"""

# <<<<<<<<<<<< Environment dependent <<<<<<<<<<<<

# command options
OPT_SUMMARY    = '--port ' + port + ' summary'
OPT_ENCRYPT    = 'encrypt_flash_data --keyfile ' + _ENCKEY + ' --address '
OPT_READFLASH  = '--port ' + port + ' --baud ' + baudRate + ' ' + \
                 '--chip esp32 --after no_reset read_flash '
OPT_WRITEFLASH = '--port ' + port + ' --baud ' + baudRate + ' ' + \
                 '--chip esp32 --after no_reset write_flash '

def command(cmd):
    env = platform()
    if env == 'win':
        return [cmd]
    return [python, cmd]

def platform():
    env = sys.platform.lower()
    if env.startswith('win') or env.startswith('cygwin'):
        return 'win'
    elif env.startswith('darwin'):
        return 'mac'
    elif env.startswith('linux'):
        return 'linux'
    return ''

def readImages():
    # download bootloader 
    s = OPT_READFLASH + _OFS_BOOTLOADER + ' ' + \
        _LEN_BOOTLOADER +  ' ' + _BOOTLOADER
    cmd = command(esptool) + s.split()
    sts = subprocess.check_call(cmd)
    if sts != 0:
        return sts

    # encrypt bootloader 
    s = OPT_ENCRYPT + _OFS_BOOTLOADER + ' -o ' + \
        _BOOTLOADER + _ENCSUFFIX + ' ' + _BOOTLOADER
    print '\n===> ' + _BOOTLOADER + _ENCSUFFIX + '\n'
    cmd = command(espsecure) + s.split()
    sts = subprocess.check_call(cmd)
    if sts != 0:
        return sts
    os.remove(_BOOTLOADER)

    # download partition table
    s = OPT_READFLASH + _OFS_PARTITION_TABLE + ' ' + \
        _LEN_PARTITION_TABLE +  ' ' + _PARTITION_TABLE
    cmd = command(esptool) + s.split()
    sts = subprocess.check_call(cmd)
    if sts != 0:
        return sts
    try:
        f = open(_PARTITION_TABLE, 'rb')
    except:
        print 'faild to open [' + _PARTITION_TABLE + ']'
        return 1

    # process each partitions
    while True:
        buf = f.read(32)
        h1, h2, type, sub, start, size, name = \
            struct.unpack('<BBBBII20s', buf)
        if h1 != 0xAA and h2 != 0x50:
            break
        name = name.rstrip('\0')
        name = hex(start) + '_' + name + '.bin'

        # download image
        print "\n===> " + name + '\n'
        s = OPT_READFLASH + hex(start) + ' ' + hex(size) + ' ' + name
        cmd = command(esptool) + s.split()
        sts = subprocess.check_call(cmd)
        if sts != 0:
            return sts
        if type == 0x00: # Type = app
            # encrypt
            print '\n===> ' + name + _ENCSUFFIX + '\n'
            s = OPT_ENCRYPT + hex(start) + ' -o ' + name + \
                _ENCSUFFIX + ' ' + name
            cmd = command(espsecure) + s.split()
            sts = subprocess.check_call(cmd)
            if sts != 0:
                return sts
            os.remove(name)
    f.close()

    # encrypt partition table
    print '\n===> ' + _PARTITION_TABLE + '\n'
    s = OPT_ENCRYPT + _OFS_PARTITION_TABLE + ' -o ' + \
        _PARTITION_TABLE + _ENCSUFFIX + ' ' + _PARTITION_TABLE
    cmd = command(espsecure) + s.split()
    sts = subprocess.check_call(cmd)
    if sts != 0:
        return sts
    os.remove(_PARTITION_TABLE)
    return 0

def writeImages():
    ar = glob.glob('0x*_*.bin*')
    for imgName in ar:
        offset = imgName.split('_')[0]
        s = OPT_WRITEFLASH + offset + ' ' + imgName
        print "\n===> " + imgName + '\n'
        cmd = command(esptool) + s.split()
        sts = subprocess.check_call(cmd)
        if sts != 0:
            return sts
        os.remove(imgName)
    return 0

def getFlashCryptCount():
    found = 0
    v = -1
    cmd = command(espefuse) + OPT_SUMMARY.split()
    result = subprocess.check_output(cmd)

    ar = result.split('\n')
    for line in ar:
        if line.startswith('FLASH_CRYPT_CNT'):
            found = 1
            break
    if found == 0:
        print 'FLASH_CRYPT_CNT line not found'
        return -1
    ar = line.split()
    for i, item in enumerate(ar):
        if item == '=':
            v = int(ar[i+1])
    if v == -1:
        print 'FLASH_CRYPT_CNT value not found'
        return -1
    return v

####
if __name__ == '__main__':

    # dependent tools
    if not os.path.isfile(esptool) or \
        not os.path.isfile(espefuse) or \
        not os.path.isfile(espsecure):
        print "This script requires 'esptool', 'espefuse', 'espsecure'"
        sys.exit(1)

    # check serial port
    try:
        s = serial.Serial(port, int(baudRate))
    except serial.SerialException:
        print 'failed to open [' + port + ']'
        sys.exit(1)
    s.close()

    # avoid confusing files
    if len(glob.glob('0x*_*.bin*')) > 0:
        print 'already exists file(s): [0x*_*.bin*]'
        sys.exit(1)

    # download partition images from the source board
    while True:
        try:
            raw_input('ESP32: Connect the source board and press any key ')
        except KeyboardInterrupt:
            sys.exit(0)
        print 'Please wait..'
        v = getFlashCryptCount()
        print 'FLASH_CRYPT_CNT=' + str(v)
        if v == 1 or v == 7 or v == 31 or v == 127:
            print 'The board is in encryption mode..'
            continue
        k = raw_input('Really start downloading? (y/n) ')
        if k != 'Y' and k != 'y':
            print "aborted.."
            sys.exit(1)
        if readImages() != 0:
            sys.exit(1)
        break

    # upload partition images to the destination board
    while True:
        try:
            raw_input('ESP32: Connect the target board in encryption mode and press any key ')
        except KeyboardInterrupt:
            sys.exit(0)
        print 'Please wait..'
        v = getFlashCryptCount()
        print 'FLASH_CRYPT_CNT=' + str(v)
        if v != 1 and v != 7 and v != 31 and v != 127:
            print 'The board is not in encryption mode..'
            continue
        k = raw_input('Really start flashing? (y/n) ')
        if k != 'Y' and k != 'y':
            print "aborted.."
            sys.exit(1)
        if writeImages() != 0:
            sys.exit(1)
        break

    sys.exit(0)
