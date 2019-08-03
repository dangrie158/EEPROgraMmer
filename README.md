# EEPROgraMmer

**Arduino EEPROM Programmer**

Universal Programmer for parallel EEPROMS using a python CLI and a simple Arduino with 2 shift-registers to interface the EEPROM.

Based on the [Arduino Code](https://github.com/beneater/eeprom-programmer) written by [Ben Eater](https://eater.net).

## Schematic

check out the [original project](https://github.com/beneater/eeprom-programmer)

## Synopsys

```
usage: eepro [-h] -p PORT [-f FILE] [-v] [-c] [--check-empty] [-b BAUD]
             [-s SIZE]

Write a binfile to an EEPROM

optional arguments:
  -h, --help            show this help message and exit
  -p PORT, --port PORT  serial port to the programmer
  -f FILE, --file FILE  binary file to write
  -v                    verify file contents after writing
  -c                    clear the eeprom (with 0xff bytes) before writing
  --check-empty         make sure the EEPROM is empty (filled with 0xff)
  -b BAUD, --baud BAUD  baudrate for communication with the programmer
  -s SIZE, --size SIZE  size of the eeprom in bytes
```
