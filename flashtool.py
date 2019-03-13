import codecs
import struct
import logging

from serialBootLoaderHost import SerialBootloaderHost

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
hex_decoder = codecs.getdecoder('hex')


class Firmware(object):
    def __init__(self):
        self.filename = None

        self.siliconID = None
        self.siliconRev = None
        self.checksumType = None

        self.applicationID = None
        self.applicationVersion = None
        self.applicationCustomVersion = None

        self.data = []

    def __str__(self):
        ret = "PSoC Firmware file\n"
        ret = ret + "filename    %s\n" % self.filename
        ret = ret + "chip        ID 0x%08x REV 0x%02x   CKS 0x%02x\n" % (self.siliconID, self.siliconRev, self.checksumType)
        ret = ret + "application ID 0x%04x     VER 0x%04x CUS 0x%08x\n" % (self.applicationID, self.applicationVersion, self.applicationCustomVersion)
        ret = ret + "data rows   %i" % len(self.data)
        return ret

    def _readHeader(self, fh):
        # header format:
        # [4-byte siliconID][1-byte siliconRev][1-byte checksumType]

        header = hex_decoder(fh.readline().strip())[0]
        #.decode('hex')

        if len(header) != 6:
            raise Exception(2, "wrong header")

        return struct.unpack('>LBB', header)

    def _readRow(self, row):
        # row format:
        # :[1-byte arrayID][2-byte rowNumber][2-byte rowDataLength][N-byte rowData][1-byte rowChecksum]

        if row[0] != ':':
            raise Exception(3, "data row must start with a colon")

        data = hex_decoder(row[1:])[0]

        arrayID, rowNumber, rowDataLength = struct.unpack('>BHH', data[:5])
        rowData = data[5:-1]

        if len(rowData) != rowDataLength:
            raise Exception(4, "rowDataLength not correct")

        # (rowChecksum,) = struct.unpack('B', data[-1])
        rowChecksum = data[-1]
        computeChecksum = 0x100 - (sum(x for x in data[:-1]) & 0xFF)
        if computeChecksum == 0x100:
            computeChecksum = 0

        if computeChecksum != rowChecksum:
            raise Exception(5, "rowChecksum missmatch")

        return (arrayID, rowNumber, rowData)

    def _getMetadata(self):
        # metadata format (last row 192:256):
        # 0x14 [2-byte applicationID]
        # 0x16 [2-byte applicationVersion]
        # 0x18 [4-byte applicationCustomVersion]

        (self.applicationID, self.applicationVersion, self.applicationCustomVersion) = struct.unpack('<HHL', self.data[-1]['rowData'][212:220])

    def read(self, filename):
        self.filename = filename
        fh = open(filename, 'r')

        self.siliconID, self.siliconRev, self.checksumType = self._readHeader(fh)

        for line in fh:
            arrayID, rowNumber, rowData = self._readRow(line.strip())
            self.data.append({'arrayID': arrayID, 'rowNumber': rowNumber, 'rowData': rowData})

        fh.close()

        self._getMetadata()

    def getMetadata(self):
        return { 'siliconID': self.siliconID,
                 'siliconRev': self.siliconRev,
                 'applicationID': self.applicationID,
                 'applilcationVersion': self.applicationVersion,
                 'applicationCustomVersion': self.applicationCustomVersion }


class FlashTool():
    def __init__(self, serial, callback):
        self._bootloader = SerialBootloaderHost(serial)
        self._callback = callback
        self._firmware = None

    def readFirmware(self, filename):
        self._firmware = Firmware()
        self._firmware.read(filename)

    def getFirmwareMetadata(self):
        if self._firmware is not None:
            return self._firmware.getMetadata()
        else:
            return None

    def getPsocMetadata(self):
        self._bootloader.cmdEnterBootloader()
        return self._bootloader.cmdGetMetadata(0x00)

    def startFirmware(self):
        self._bootloader.cmdExitBootloader()

    def flash(self):
        if self._firmware is None:
            raise Exception(2, "no firmware file loaded")

        # entering bootloader
        Logger.debug('entering bootloader')
        # siliconID = 0x2BA01477; siliconRev = , blVersion, blVerison2
        siliconID, siliconRev, blVersion, blVerison2 = self._bootloader.cmdEnterBootloader()

        if siliconID != self._firmware.siliconID | siliconRev != self._firmware.siliconRev:
            raise Exception(3, "firmware file is not compatible")

        # write_rows
        Logger.debug('writing firmware: '  + str(self._firmware) )
        i = 0
        for row in self._firmware.data:
            i += 1
            Logger.debug('writing %i/%i' % (i, len(self._firmware.data)))
            self._bootloader.cmdProgramRow(row['arrayID'], row['rowNumber'], row['rowData'])
        Logger.debug("error count: " + str(self._bootloader._errcount))

        # verify_checksum
        Logger.debug('verify firmware checksum')
        if not self._bootloader.cmdVerifyApplicationChecksum():
            raise Exception(5, "firmware checksum check failed")


