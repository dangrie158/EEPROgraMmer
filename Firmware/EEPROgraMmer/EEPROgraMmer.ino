/*
 * Based on the EEPROM Programmer Project by Ben Eater 
 * https://github.com/beneater/eeprom-programmer
 * 
 */
#include <stdint.h>

#define SHIFT_DATA 2
#define SHIFT_CLK 3
#define SHIFT_LATCH 4
#define EEPROM_D0 5
#define EEPROM_D7 12
#define WRITE_EN 13

#define END_CHAR '\x04'  // EOT
#define ESC_CHAR '\x1B'  // ESC
#define ACK_CHAR '\x06'  // ACK
#define NACK_CHAR '\x15' // NACK

enum Mode
{
  // Command Mode, waiting for instruction byte
  COMMAND,
  // write mode, initialized by a 'w' char in
  // command mode followed by a single integer
  // (start address to begin writing).
  // enters WRITE_BYTES mode after receiving the address
  WRITE,
  // write mode, reading bytes from the serial port
  // and writing them to the current writeAddress
  // until the end character is received
  WRITE_BYTES,
  // read bytes, initialized by a 'r' char in
  // command mode, followed by 2 integers:
  // the start address and length to be read
  READ
};

typedef uint32_t address_t;
typedef uint8_t byte;
typedef uint8_t pin_t;

Mode currentMode = COMMAND;
address_t writeAddress = 0x00;
address_t writeStartAddress = 0x00;

/*
   Output the address bits and outputEnable signal using shift registers.
*/
void setAddress(address_t address, bool outputEnable)
{
  shiftOut(SHIFT_DATA, SHIFT_CLK, MSBFIRST, (address >> 8) | (outputEnable ? 0x00 : 0x80));
  shiftOut(SHIFT_DATA, SHIFT_CLK, MSBFIRST, address);

  digitalWrite(SHIFT_LATCH, LOW);
  digitalWrite(SHIFT_LATCH, HIGH);
  digitalWrite(SHIFT_LATCH, LOW);
}

/*
   Read a byte from the EEPROM at the specified address.
*/
byte readEEPROM(address_t address)
{
  for (pin_t pin = EEPROM_D0; pin <= EEPROM_D7; pin += 1)
  {
    pinMode(pin, INPUT);
  }
  setAddress(address, /*outputEnable*/ true);

  byte data = 0;
  for (pin_t pin = EEPROM_D7; pin >= EEPROM_D0; pin -= 1)
  {
    data = (data << 1) + digitalRead(pin);
  }
  return data;
}

/*
   Write a byte to the EEPROM at the specified address.
*/
void writeEEPROM(address_t address, byte data)
{
  setAddress(address, /*outputEnable*/ false);
  for (pin_t pin = EEPROM_D0; pin <= EEPROM_D7; pin += 1)
  {
    pinMode(pin, OUTPUT);
  }

  for (pin_t pin = EEPROM_D0; pin <= EEPROM_D7; pin += 1)
  {
    digitalWrite(pin, data & 1);
    data = data >> 1;
  }
  digitalWrite(WRITE_EN, LOW);
  delayMicroseconds(1);
  digitalWrite(WRITE_EN, HIGH);
  delay(10);
}

void setup()
{
  // put your setup code here, to run once:
  pinMode(SHIFT_DATA, OUTPUT);
  pinMode(SHIFT_CLK, OUTPUT);
  pinMode(SHIFT_LATCH, OUTPUT);
  digitalWrite(WRITE_EN, HIGH);
  pinMode(WRITE_EN, OUTPUT);
  Serial.setTimeout(200);
  Serial.begin(115200);
}

void loop()
{
  if (currentMode == COMMAND && Serial.available() > 0)
  {
    byte command = Serial.read();

    if (command == 'w')
    {
      currentMode = WRITE;
      Serial.write(ACK_CHAR);
    }
    else if (command == 'r')
    {
      currentMode = READ;
      Serial.write(ACK_CHAR);
    }
    else
    {
      Serial.write(NACK_CHAR);
      Serial.print("ERROR!: Invalid Command: ");
      Serial.print(command, HEX);
      Serial.print(" (");
      Serial.write(command);
      Serial.println(").");
    }
  }
  else if (currentMode == READ)
  {
    address_t startAddress = Serial.parseInt(SKIP_WHITESPACE);
    Serial.write(ACK_CHAR);
    address_t length = Serial.parseInt(SKIP_WHITESPACE);
    Serial.write(ACK_CHAR);

    address_t bytesWritten = 0;

    for (address_t offset = 0; offset < length; offset++)
    {
      byte content = readEEPROM(startAddress + offset);
      if (content == END_CHAR || content == ESC_CHAR)
      {
        Serial.write(ESC_CHAR);
        bytesWritten += 1;
      }
      Serial.write(content);
      bytesWritten += 1;
    }

    Serial.write(END_CHAR);
    Serial.println(bytesWritten, DEC);

    currentMode = COMMAND;
  }
  else if (currentMode == WRITE)
  {
    writeAddress = Serial.parseInt(SKIP_WHITESPACE);
    writeStartAddress = writeAddress;
    currentMode = WRITE_BYTES;
    Serial.write(ACK_CHAR);
  }
  else if (currentMode == WRITE_BYTES)
  {

    if (Serial.available() > 0)
    {
      byte nextByte = Serial.read();

      if (nextByte == END_CHAR)
      {
        currentMode = COMMAND;
        Serial.write(ACK_CHAR);
        Serial.println(writeAddress - writeStartAddress, DEC);
        return;
      }
      else if (nextByte == ESC_CHAR)
      {
        //skip the escape character and read the next byte
        Serial.write(ACK_CHAR);
        while (!Serial.available())
          ;
        nextByte = Serial.read();
        if (nextByte != ESC_CHAR && nextByte != END_CHAR)
        {
          Serial.write(NACK_CHAR);
          Serial.print("ERROR!: Invalid ESC sequence: 0x");
          Serial.print(nextByte, HEX);
          Serial.print(" (");
          Serial.write(nextByte);
          Serial.println(").");
        }
      }

      writeEEPROM(writeAddress, nextByte);
      writeAddress += 1;
      Serial.write(ACK_CHAR);
    }
  }
}
