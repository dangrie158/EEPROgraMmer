#!/usr/bin/env python3
"""
CLI implementation to communicate with a connected Arduino based EEPROM Programmer
"""

import argparse
import time
import sys
from difflib import context_diff as diff_func
from io import BytesIO

from typing import Sequence, Union, BinaryIO

from serial import Serial
from tqdm import tqdm


def format_hex(in_bytes: bytes) -> Sequence[str]:
    """
    format an input sequence of bytes into a ordered form with lines of
    8 hex-formatted bytes prefixed by the address of the first byte in the line.

    :param in_bytes: the bytes to format
    :return: a list of formatted lines

    Example:
    >>> print('\n'.join(eepro.format_hex(b'0123456789ABCDEF')))

    0x0000:    30 31 32 33  34 35 36 37
    0x0008:    38 39 41 42  43 44 45 46

    """
    chunk_size = 8
    byte = "{:02X} "
    address = "0x{:04X}:    "
    formatted_str = ""

    for i, in_byte in enumerate(in_bytes):
        if i % (chunk_size) == 0:
            formatted_str += "\n" + address.format(i)
        elif i % (chunk_size // 2) == 0:
            formatted_str += " "
        formatted_str += byte.format(in_byte)

    return formatted_str.split("\n")


class FillBytes(BytesIO):
    """
    File like object that is filled with ``length`` occurrences of
    ``fill_byte`` bytes. Sole purpose of the class is to overwrite
    the ``__repr__`` of ``io.ByteIO``

    :param fill_byte: the byte to fill the file with
    :param length: number of bytes in the file
    """

    def __init__(self, fill_byte: bytes, length: int):
        self.fill_byte = fill_byte
        super().__init__(fill_byte * length)

    def __repr__(self) -> str:
        return f"fill bytes (0x{self.fill_byte[0]:02X})"


class EEProgrammer(Serial):
    """
    Represents the connection to an Arduino based EEPROM programmer
    via a (virtual) serial port
    """

    esc_char = b"\x1B"
    end_char = b"\x04"
    ack_char = b"\x06"

    def reset(self) -> None:
        """
        Resets the connected programmer and waits for it to start back up.

        Useful to start in a known state
        """
        self.dtr = True
        time.sleep(0.11)
        self.dtr = False
        time.sleep(2)

    def acknowledged_write(self, byte: bytes) -> None:
        """
        Write a single byte to the programmer and wait for an acknowledge response.

        :param byte: the byte to write
        :raises ConnectionError: If the programmer responds with anything but an
            acknowledge or the operation times out
        """
        self.write(byte)
        self.flush()
        if self.read() != EEProgrammer.ack_char:
            raise ConnectionError(
                "Programmer did not acknowledge write",
                self.flush_read_buffer().decode("ascii"),
            )

    def write_file(self, file: Union[str, BinaryIO], start_address: int = 0x00) -> None:
        """
        Write the contents of a file to the EEPROM.
        Any control bytes in the input file are automatically escaped before sending

        :param file: path to a file or an already opened file-like object in binary mode
        :param start_address: offset in the EEPROM where to start writing the file
        :raises AssertionError: if the programmer responds to have received less bytes
            than could be read from the file
        :raises ConnectionError: if the programmer fails to acknowledge any byte send to it
        """
        self.acknowledged_write("w ".encode("ascii"))
        self.acknowledged_write(f"{start_address}".encode("ascii"))

        if isinstance(file, str):
            with open(file, "rb") as bin_file:
                raw_content = bin_file.read()
        else:
            raw_content = file.read()

        escaped_content = EEProgrammer.escape_file_contents(raw_content)
        for byte in tqdm(escaped_content, desc=f"writing {file}"):
            self.acknowledged_write(bytes([byte]))

        self.acknowledged_write(EEProgrammer.end_char)

        response = self.readline()
        bytes_written = int(response)
        if bytes_written != len(raw_content):
            raise AssertionError(
                f"written {bytes_written} bytes, expected {len(raw_content)}"
            )

    def read_file(self, file: str, length: int, start_address: int = 0x00) -> None:
        """
        read the contents of the EEPROM to a file

        :param file: path to a file that will be opened in binary mode (does not need to exist)
        :param length: number of bytes to read
        :param start_address: offset in the EEPROM where to start reading
        :raises AssertionError: if the programmer responds to have sent more bytes
            than could be read from the connection or the programmer sends an invalid
            escape sequence
        :raises ConnectionError: if the programmer fails to acknowledge any byte send to it
        """
        contents = self.read_contents(start_address, length)
        with open(file, "wb") as outfile:
            outfile.write(contents)

    def fill(self, fill_byte: bytes, length: int, start_address: int = 0x00) -> None:
        """
        fill an area of the EEPROM memory with a single value

        :param fill_byte: value to fill the EEPROM memory section
        :param length: length of the memory block in bytes
        :param start_address: offset of the memory block from the start of the EEPROM
        :raises AssertionError: if the programmer responds to have received less bytes
            than specified
        :raises ConnectionError: if the programmer fails to acknowledge any byte send to it
        """
        dummy_file = FillBytes(fill_byte, length)
        self.write_file(dummy_file, start_address=start_address)

    def check_filled(
        self, fill_byte: bytes, length: int, start_address: int = 0x00
    ) -> None:
        """
        Check if a section of EEPROM is filled with a specific byte

        :param fill_byte: value that should be read by every cell in the specified memory area
        :param length: length of the memory block in bytes
        :param start_address: offset of the memory block from the start of the EEPROM
        :raises AssertionError: if the EEPROM reads back any byte different from the specified value
        :raises ConnectionError: if the programmer fails to acknowledge any byte send to it
        """
        dummy_file = FillBytes(fill_byte, length)
        try:
            self.verify_file(dummy_file, start_address=start_address)
        except AssertionError as err:
            raise AssertionError(
                f"EEPROM is not filled with 0x{fill_byte:02X}", err.args[1]
            ) from err

    def verify_file(
        self, file: Union[str, BinaryIO], start_address: int = 0x00
    ) -> None:
        """
        Read the contents of the EEPROM and compare each byte to a specified file.
        The number of bytes to read is determined by the file length.

        :param file: path to a file that will be opened in binary mode
        :param start_address: offset in the EEPROM where to start reading
        :raises AssertionError: if the EEPROM memory differs in any byte from the specified file
        :raises ConnectionError: if the programmer fails to acknowledge any byte send to it
        """
        if isinstance(file, str):
            with open(file, "rb") as bin_file:
                raw_content = bin_file.read()
        else:
            raw_content = file.read()

        eeprom_content = self.read_contents(start_address, len(raw_content))

        if raw_content != eeprom_content:
            diff = diff_func(
                format_hex(raw_content),
                format_hex(eeprom_content),
                fromfile=repr(file),
                tofile="EEPROM Contents",
            )
            raise AssertionError("Contents do not match input file", "\n".join(diff))

    def read_contents(self, start_address: int, length: int) -> bytes:
        """
        Read a section of memory from the EEPROM into a bytearray. This method automatically handles
        the unescapeing of control sequences for the programmer.

        :param start_address: offset to the beginning of the memory block to read
        :param length: size of the memory block to read
        :return: bytes object with the specified memory block contents

        :raises AssertionError: if the programmer repors to have sent more bytes than were received
            or if an invalid escape sequence is received
        :raises ConnectionError: if the programmer fails to acknowledge any byte send to it
        """
        self.acknowledged_write("r ".encode("ascii"))
        self.acknowledged_write(f"{start_address}".encode("ascii"))
        self.acknowledged_write(f"{length}".encode("ascii"))

        content = b""

        progress = tqdm(desc="reading contents", total=length)
        while True:
            char = self.read()
            if char == EEProgrammer.end_char:
                progress.close()

                response = self.readline()
                bytes_read = int(response)
                escaped_content = EEProgrammer.escape_file_contents(content)
                if bytes_read != len(escaped_content):
                    raise AssertionError(
                        f"read {len(escaped_content)} bytes, expected {bytes_read}"
                    )

                return content

            if char == EEProgrammer.esc_char:
                char = self.read()

                if char not in [EEProgrammer.end_char, EEProgrammer.esc_char]:
                    raise AssertionError("Invalid escape sequence received")

            content += char
            progress.update()

    def flush_read_buffer(self) -> bytes:
        """
        Read the serial buffer until empty and return the result

        :return: bytes object with the current contents of the serial read buffer
        """
        content = b""
        while True:
            line = self.readline()
            if line == b"":
                break
            content += line
        return content

    @staticmethod
    def escape_file_contents(contents: bytes) -> bytearray:
        """
        Escape each control character in a sequence of bytes.

        :param contents: the sequence to escape (bytes or list of ints)
        :return: bytes of the escaped sequence
        """
        escaped_bytes = bytearray()
        for byte in contents:
            escaped_bytes += EEProgrammer.escape_byte(bytes([byte]))
        return escaped_bytes

    @staticmethod
    def escape_byte(byte: bytes) -> bytes:
        """
        Escape a single byte. For non-control characters this is a no-op.
        Control characters (``EEProgrammer.end_char`` and ``EEProgrammer.esc_char``)
        will be prefixed with an additional ``EEProgrammer.end_char``.

        :param byte: the byte to escape
        :return: a ``bytes`` object containing the escaped input
        """
        if byte in [EEProgrammer.end_char, EEProgrammer.esc_char]:
            return EEProgrammer.esc_char + byte

        return byte


def main() -> None:
    """
    Entrypoint for the CLI application
    """
    parser = argparse.ArgumentParser(description="Write to or read from an EEPROM")

    parser.add_argument(
        "-p", "--port", help="serial port to the programmer", required=True
    )
    parser.add_argument("-f", "--file", help="binary file to write")
    parser.add_argument(
        "-b",
        "--baud",
        type=int,
        default=115200,
        help="baudrate for communication with the programmer",
    )
    parser.add_argument("-s", "--size", type=int, help="size of the EEPROM in bytes")

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-w",
        dest="write",
        default=False,
        action="store_true",
        help="write <file> to the EEPROM",
    )
    group.add_argument(
        "-r",
        dest="read",
        default=False,
        action="store_true",
        help="read the contents of the EEPROM into file",
    )
    parser.add_argument(
        "-v",
        dest="verify",
        default=False,
        action="store_true",
        help="verify file contents after writing",
    )
    parser.add_argument(
        "-c",
        dest="clear",
        default=False,
        action="store_true",
        help="clear the EEPROM (with 0xff bytes) before writing or reading",
    )
    parser.add_argument(
        "--check-empty",
        default=False,
        action="store_true",
        help="make sure the EEPROM is empty (filled with 0xff)",
    )
    args = parser.parse_args()

    if (args.write or args.read or args.verify) and not args.file:
        parser.error("for write and read actions, the file parameter is required")

    if (args.clear or args.check_empty or args.read) and not args.size:
        parser.error(
            "for clear, check-empty and read actions, you need to specify the size of the EEPROM"
        )

    with EEProgrammer(args.port, args.baud, timeout=1) as programmer:
        try:
            print("resetting programmer...")
            programmer.reset()

            if args.clear:
                print("cleaning eeprom...")
                programmer.fill(b"\xff", args.size)

            if args.check_empty:
                print("checking eeprom for non-empty bytes...")
                programmer.check_filled(b"\xff", args.size)

            if args.write:
                print("writing file...")
                programmer.write_file(args.file)

            elif args.read:
                print("reading eeprom contents...")
                programmer.read_file(args.file, args.size, 0x00)

            if args.verify:
                print("verifying contents...")
                programmer.verify_file(args.file)

        except (ConnectionError, AssertionError) as err:
            print()
            print(f"{err.__class__.__name__}: {err.args[0]}", file=sys.stderr)
            for reason in err.args[1:]:
                print(reason, file=sys.stderr)


if __name__ == "__main__":
    main()
