#   Copyright (C) 2011 Jason Anderson
#
#
# This file is part of PseudoTV.
#
# PseudoTV is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# PseudoTV is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with PseudoTV.  If not, see <http://www.gnu.org/licenses/>.

import xbmc
import os, struct

from resources.lib.Globals import ascii
from resources.lib.FileAccess import FileAccess


class TSPacket:
    def __init__(self):
        self.pid = 0
        self.errorbit = 1
        self.pesstartbit = 0
        self.adaption = 1
        self.adaptiondata = ''
        self.pesdata = ''


class TSParser:
    def __init__(self):
        pass


    def log(self, msg, level = xbmc.LOGDEBUG):
        xbmc.log('TSParser: ' + ascii(msg), level)


    def determineLength(self, filename):
        self.log("determineLength " + filename)
        self.pid = -1

        try:
            self.File = FileAccess.open(filename, "rb", None)
        except:
            self.log("Unable to open the file")
            return

        self.filesize = self.getFileSize()
        start = self.getStartTime()
        self.log('Start - ' + str(start))
        end = self.getEndTime()
        self.log('End - ' + str(end))
        
        if end > start:
            dur = int((end - start) / 90000)
        else:
            dur = 0

        self.File.close()
        self.log("Duration: " + str(dur))
        return dur


    def getFileSize(self):
        size = 0
        
        try:
            pos = self.File.tell()
            self.File.seek(0, 2)
            size = self.File.tell()
            self.File.seek(pos, 0)
        except:
            pass

        return size

        
    def getStartTime(self):
        # A reasonably high number of retries in case the PES starts in the middle
        # and is it's maximum length
        maxpackets = 12000
        self.log('getStartTime')

        while maxpackets > 0:
            packet = self.readTSPacket()
            maxpackets -= 1

            if packet == None:
                return 0

            if packet.errorbit == 0 and packet.pesstartbit == 1:
                ret = self.getPTS(packet)

                if ret > 0:
                    self.pid = packet.pid
                    return ret

        return 0
        
        
    def getEndTime(self):
        self.log('getEndTime')
        packetcount = int(self.filesize / 188)

        try:
            self.File.seek((packetcount * 188)- 188, 0)
        except:
            return 0

        maxpackets = 12000

        while maxpackets > 0:
            packet = self.readTSPacket()
            maxpackets -= 1
        
            if packet == None:
                return 0

            if packet.errorbit == 0 and packet.pesstartbit == 1 and packet.pid == self.pid:
                ret = self.getPTS(packet)

                if ret > 0:
                    return ret
            else:
                try:
                    self.File.seek(-376, 1)
                except:
                    self.log('exception')
                    return 0
            
        return 0
        
    
    def getPTS(self, packet):
        timestamp = 0
        
        try:
            data = struct.unpack('19B', packet.pesdata[:19])

            # start code
            if data[0] == 0 and data[1] == 0 and data[2] == 1:
                # cant be a navigation packet
                if data[3] != 190 and data[3] != 191:
                    offset = 0
                    
                    if (data[9] >> 4) == 3:
                        offset = 5

                    # a little dangerous...ignoring the LSB of the timestamp
                    timestamp = ((data[9 + offset] >> 1) & 7) << 30
                    timestamp = timestamp | (data[10 + offset] << 22)
                    timestamp = timestamp | ((data[11 + offset] >> 1) << 15)
                    timestamp = timestamp | (data[12 + offset] << 7)
                    timestamp = timestamp | (data[13 + offset] >> 1)
                    return timestamp                        
        except:
            pass

        return 0
        
    
    def readTSPacket(self):
        packet = TSPacket()
        pos = 0
        
        try:
            data = self.File.read(4)
            pos = 4
            data = struct.unpack('4B', data)
            
            if data[0] == 71:
                packet.pid = (data[1] & 31) << 8
                packet.pid = packet.pid | data[2]
                
                # skip tables and null packets
                if packet.pid < 21 or packet.pid == 8191:
                    self.File.seek(184, 1)
                else:
                    packet.adaption = (data[3] >> 4) & 3
                    packet.errorbit = data[1] >> 7
                    packet.pesstartbit = (data[1] >> 6) & 1

                    if packet.adaption > 1:
                        data = self.File.read(1)
                        length = struct.unpack('B', data)[0]
                        data = self.File.read(length)
                        pos += length + 1
                    
                    if pos < 188:
                        # read the PES data
                        packet.pesdata = self.File.read(188 - pos)
        except:
            return None
            
        return packet
