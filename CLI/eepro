#!/usr/bin/env python3

import argparse
import time
import sys
from difflib import context_diff as diff_func
from io import BytesIO

from serial import Serial
from tqdm import tqdm

def format_hex(in_bytes):
    chunk_size = 8
    byte = '{:02X} '
    address = '0x{:04X}:    '
    formatted_str = ''

    for i in range(len(in_bytes)):
        if i % (chunk_size) == 0:
            formatted_str += '\n' + address.format(i)
        elif i % (chunk_size // 2) == 0:
            formatted_str += ' '
        formatted_str += byte.format(in_bytes[i])

    return formatted_str.split('\n')

class FillBytes(BytesIO):
    def __init__(self, fill_byte, length):
        self.fill_byte = fill_byte
        super().__init__(fill_byte * length)

    def __repr__(self):
        return f'fill bytes (0x{self.fill_byte[0]:02X})'

class EEProgrammer(Serial):

    esc_char = b'\x1B'
    end_char = b'\x04'
    ack_char = b'\x06'

    def reset(self):
        self.dtr = True
        time.sleep(0.11)
        self.dtr = False
        time.sleep(2)

    def acknowledged_write(self, byte):
        self.write(byte)
        self.flush()
        if self.read() != EEProgrammer.ack_char:
            raise ConnectionError('Programmer did not acknowledge write', self.flush_read_buffer().decode('ascii'))

    def write_file(self, file, start_address=0x00):
        self.acknowledged_write('w '.encode('ascii'))
        self.acknowledged_write(f'{start_address}'.encode('ascii'))

        if type(file) == str:
            with open(file, 'rb') as bin_file:
                raw_content =  bin_file.read()
        else:
            raw_content =  file.read()

        escaped_content = EEProgrammer.escape_file_contents(raw_content)
        for byte in tqdm(escaped_content, desc=f'writing {file}'):
            self.acknowledged_write(bytes([byte]))
                
        self.acknowledged_write(EEProgrammer.end_char)

        response = self.readline()
        bytes_written = int(response)
        if bytes_written != len(raw_content):
            raise AssertionError(f'written {bytes_written} bytes, expected {len(bin_file)}')

    def read_file(self, file, length, start_address=0x00):
        contents = self.read_contents(start_address, length)
        with open(file, 'wb') as outfile:
            outfile.write(contents)

    def fill(self, fill_byte, length):
        dummy_file = FillBytes(fill_byte, length)
        self.write_file(dummy_file)

    def check_filled(self, fill_byte, length):
        dummy_file = FillBytes(fill_byte, length)
        try:
            self.verify_file(dummy_file)
        except AssertionError as e:
            raise AssertionError('EEPROM is not empty', e.args[1]) from e

    def verify_file(self, file, start_address=0x00):

        if type(file) == str:
            with open(file, 'rb') as bin_file:
                raw_content =  bin_file.read()
        else:
            raw_content =  file.read()

        eeprom_content = self.read_contents(start_address, len(raw_content))

        if raw_content != eeprom_content:
            diff = diff_func(format_hex(raw_content), format_hex(eeprom_content), fromfile=repr(file), tofile='EEPROM Contents')
            raise AssertionError('Contents do not match input file', '\n'.join(diff))

    def read_contents(self, start_address, length):
        self.acknowledged_write('r '.encode('ascii'))
        self.acknowledged_write(f'{start_address}'.encode('ascii'))
        self.acknowledged_write(f'{length}'.encode('ascii'))

        content = b''

        progress = tqdm(desc='reading contents', total=length)
        while True:
            char = self.read()
            if char == EEProgrammer.end_char:
                progress.close()

                response = self.readline()
                bytes_read = int(response)
                escaped_content = EEProgrammer.escape_file_contents(content)
                if bytes_read != len(escaped_content):
                    raise AssertionError(f'read {len(escaped_content)} bytes, expected {bytes_read}')

                return content
            elif char == EEProgrammer.esc_char:
                char = self.read()

                if char not in [EEProgrammer.end_char, EEProgrammer.esc_char]:
                    raise AssertionError('Invalid escape sequence received')
            
            content += char
            progress.update()


    def flush_read_buffer(self):
        content = b''
        while True:
            line = self.readline()
            if line == b'':
                break
            content += line
        return content

    @staticmethod 
    def escape_file_contents(contents):
        escaped_bytes = bytearray()
        for byte in contents:
            escaped_bytes += EEProgrammer.escape_byte(bytes([byte]))
        return escaped_bytes

    @staticmethod 
    def escape_byte(byte):
        if byte in [EEProgrammer.end_char, EEProgrammer.esc_char]:
            return EEProgrammer.esc_char + byte
        else:
            return byte

parser = argparse.ArgumentParser(description='Write to or read from an EEPROM')

parser.add_argument('-p', '--port', help='serial port to the programmer', required=True)
parser.add_argument('-f', '--file', help='binary file to write')
parser.add_argument('-b', '--baud', type=int, default=115200, help='baudrate for communication with the programmer')
parser.add_argument('-s', '--size', type=int, help='size of the EEPROM in bytes')

group = parser.add_mutually_exclusive_group()
group.add_argument('-w', dest='write', default=False, action='store_true', help='write <file> to the EEPROM')
group.add_argument('-r', dest='read', default=False, action='store_true', help='read the contents of the EEPROM into file')
parser.add_argument('-v', dest='verify', default=False, action='store_true', help='verify file contents after writing')
parser.add_argument('-c', dest='clear', default=False, action='store_true', help='clear the EEPROM (with 0xff bytes) before writing or reading')
parser.add_argument('--check-empty', default=False, action='store_true', help='make sure the EEPROM is empty (filled with 0xff)')

if __name__ == '__main__':
    args = parser.parse_args()

    if (args.write or args.read) and not args.file:
        parser.error('for write and read actions, the file parameter is required')

    if (args.clear or args.check_empty or args.read) and not args.size:
            parser.error('for clear, check-empty and read actions, you need to specify the size of the EEPROM')

    with EEProgrammer(args.port, args.baud, timeout=1) as programmer:
        try:
            print('resetting programmer...')
            programmer.reset()

            if args.clear:
                print('cleaning eeprom...')
                programmer.fill(b'\xff', args.size)

            if args.check_empty:
                print('checking eeprom for non-empty bytes...')
                programmer.check_filled(b'\xff', args.size)

            if args.write:
                print('writing file...')
                programmer.write_file(args.file)

            elif args.read:
                print('reading eeprom contents...')
                programmer.read_file(args.file, args.size, 0x00)

            if args.verify:
                print('verifying contents...')
                programmer.verify_file(args.file)

        except (ConnectionError, AssertionError) as e:
            print()
            print(f'{e.__class__.__name__}: {e.args[0]}', file=sys.stderr)
            for reason in e.args[1:]:
                print(reason, file=sys.stderr)
