import struct
import logging

# -------------------------------------------------------------------------------
# Defines
# -------------------------------------------------------------------------------
FORMAT = '%(asctime)-15s %(name)s - %(levelname)s - %(message)s'
ERR = {
    0x00: 'CYRET_SUCCESS' , # The command was successfully received and executed
    0x02: 'BOOTLOADER_ERR_VERIFY', # The verification of flash failed
    0x03: 'BOOTLOADER_ERR_LENGTH',  # The amount of data available is outside the expected range
    0x04: 'BOOTLOADER_ERR_DATA', # The data is not of the proper form
    0x05: 'BOOTLOADER_ERR_CMD', # The command is not recognized
    0x06: 'BOOTLOADER_ERR_DEVICE',    # The expected device does not match the detected device.
    0x07: 'BOOTLOADER_ERR_VERSION',  # The bootloader version detected is not supported.
    0x08: 'BOOTLOADER_ERR_CHECKSUM',  # Packet checksum does not match the expected value
    0x09: 'BOOTLOADER_ERR_ARRAY',     # Flash array ID is not valid
    0x0A: 'BOOTLOADER_ERR_ROW',        # The flash row number is not valid
    0x0C: 'BOOTLOADER_ERR_APP',       # The application is not valid and cannot be set as active
    0x0D: 'BOOTLOADER_ERR_ACTIVE',    # The application is currently marked as active
    0x0F: 'BOOTLOADER_ERR_UNK'       # An unknown error occurred
}
# -------------------------------------------------------------------------------
# Declarations
# -------------------------------------------------------------------------------
logging.basicConfig(format=FORMAT)
Logger = logging.getLogger(__name__)
Logger.setLevel(logging.DEBUG)


class BootloaderError(Exception):
    def __init__(self, value, msg):
        self.value = value
        self.message = msg


def sum_2complement_checksum(data):
    if (type(data) is str):
        return (1 + ~sum([ord(c) for c in data])) & 0xFFFF
    elif (type(data) in (bytearray, bytes)):
        return (1 + ~sum(data)) & 0xFFFF


class SerialBootloaderHost(object):
    def __init__(self, ser):
        self._serial = ser
        self._serial.flushInput()
        self._serial.flushOutput()
        self._errcount = 0

    def cmdEnterBootloader(self):
        packet = struct.pack("<BBH", 0x01, 0x38, 0x0000)
        checksum = sum_2complement_checksum(packet)
        packet = packet + struct.pack('<HB', checksum, 0x17)

        self._send(packet)
        return self._recv("<IBHB")

    def cmdGetFlashSize(self, arrayID):
        data = struct.pack("<B", arrayID)
        packet = struct.pack("<BBH", 0x01, 0x32, len(data))
        packet = packet + data
        checksum = sum_2complement_checksum(packet)
        packet = packet + struct.pack('<HB', checksum, 0x17)

        self._send(packet)
        return self._recv("<HH")

    def cmdProgramRow(self, arrayID, rowNumber, rowData):
        rowdata = rowData
        chunk = 0
        errcount = 0
        while len(rowdata) > 32:
            chunkdata = rowdata[:32]
            rowdata = rowdata[32:]
            packet = struct.pack("<BBH", 0x01, 0x37, len(chunkdata))
            packet = packet + chunkdata
            checksum = sum_2complement_checksum(packet)
            packet = packet + struct.pack('<HB', checksum, 0x17)

            status = -1
            trycount = 0
            lastex = None

            while (status != 0 and trycount < 10):
                trycount += 1
                lastex = None
                try:
                    self._send(packet)
                    status = self._recv()
                except BootloaderError as ex:
                    lastex = ex
                    errcount += 1
                    pass

            if lastex != None:
                raise lastex

            chunk = chunk + 1

        data = struct.pack("<BH", arrayID, rowNumber)
        data = data + rowdata

        packet = struct.pack("<BBH", 0x01, 0x39, len(data))
        packet = packet + data
        checksum = sum_2complement_checksum(packet)
        packet = packet + struct.pack('<HB', checksum, 0x17)

        status = -1
        trycount = 0
        lastex = None

        while (status != 0 and trycount < 10):
            trycount += 1
            lastex = None
            try:
                self._send(packet)
                status = self._recv()
            except BootloaderError as ex:
                lastex = ex
                pass

        if lastex != None:
            raise lastex

        return status

    def cmdEraseRow(self, arrayID, rowNumber):
        data = struct.pack("<BH", arrayID, rowNumber)
        packet = struct.pack("<BBH", 0x01, 0x34, len(data))
        packet = packet + data
        checksum = sum_2complement_checksum(packet)
        packet = packet + struct.pack('<HB', checksum, 0x17)

        self._send(packet)
        return self._recv()

    def cmdGetChecksum(self, arrayID, rowNumber):
        data = struct.pack("<BH", arrayID, rowNumber)
        packet = struct.pack("<BBH", 0x01, 0x3a, len(data))
        packet = packet + data
        checksum = sum_2complement_checksum(packet)
        packet = packet + struct.pack('<HB', checksum, 0x17)

        self._send(packet)
        return self._recv("<B")

    def cmdVerifyApplicationChecksum(self):
        packet = struct.pack("<BBH", 0x01, 0x31, 0x0000)
        checksum = sum_2complement_checksum(packet)
        packet = packet + struct.pack('<HB', checksum, 0x17)

        self._send(packet)
        return self._recv("<B")

    def cmdSyncBootloader(self):
        packet = struct.pack("<BBH", 0x01, 0x35, 0x0000)
        checksum = sum_2complement_checksum(packet)
        packet = packet + struct.pack('<HB', checksum, 0x17)

        self._send(packet)

    def cmdExitBootloader(self):
        packet = struct.pack("<BBH", 0x01, 0x3b, 0x0000)
        checksum = sum_2complement_checksum(packet)
        packet = packet + struct.pack('<HB', checksum, 0x17)
        print(packet)
        self._send(packet)

    def cmdGetMetadata(self, appID):
        data = struct.pack("<B", appID)
        packet = struct.pack("<BBH", 0x01, 0x3c, len(data))
        packet = packet + data
        checksum = sum_2complement_checksum(packet)
        packet = packet + struct.pack('<HB', checksum, 0x17)

        self._send(packet)
        return self._recv("<20xHHL58x")
        #return self._recv() #"<16xH

    def cmdVerifyRow(self, arrayID, rowNumber, rowData):
        data = struct.pack("<BH", arrayID, rowNumber)
        data = data + rowData
        packet = struct.pack("<BBH", 0x01, 0x45, len(data))
        packet = packet + data
        checksum = sum_2complement_checksum(packet)
        packet = packet + struct.pack('<HB', checksum, 0x17)

        self._send(packet)
        return self._recv()

    def _send(self, packet):
        self._serial.write(packet)

    def _recv(self, format=None):
        data = self._serial.read(4)

        if len(data) < 4:
            raise BootloaderError(1, "receive timeout")

        start, status, size = struct.unpack("<BBH", data)

        if start != 0x01:
            Logger.debug("wrong protocol received")
            raise BootloaderError(2, "receive wrong start byte")

        data += self._serial.read(size + 3)

        if len(data) < size + 7:
            raise BootloaderError(1, "receive timeout")

        checksum, end = struct.unpack("<HB", data[-3:])

        if end != 0x17:
            raise BootloaderError(3, "receive wrong end byte")

        if checksum != sum_2complement_checksum(data[:size + 4]):
            raise BootloaderError(4, "receive wrong checksum")

        if status != 0x00:
            Logger.debug(ERR[status])
            raise BootloaderError(5, "receive error status 0x%02x" % status)

        if format:
            return struct.unpack(format, data[4:size + 4])
        else:
            return status
