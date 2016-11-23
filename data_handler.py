import signal
import sys
import socket
import threading
import math
from struct import *
from datetime import datetime
from queue import *


__IN_ORDER__ = 1
__OUT_OF_ORDER = 2


__MSS__ = 1488
__ALPHA__ = 8
__BETA__ = 4
__SLOW_START__ = 1
__CONGESTION_AVOIDANCE__ = 2
__FAST_RECOVERY__ = 3
__CONNECTION_CLOSED__ = 1
__CONNECTION_OPEN__ = 2
__SOCKET_OPEN__ = 1
__SOCKET_CLOSED__ = 0
__ACK__ = 1
__SYN__ = 2
__FIN__ = 3
__DATA_PACKET__ = 4
__HANDSHAKE_SOCKET__ = 1
__TRANSFER_SOCKET__ = 2

class MSG(object):

    def __init__(self, ty=None, seq_number=0, rwnd=0, data=None):
        self.type = ty
        self.seq_number = seq_number
        self.rwnd = rwnd
        self.data = data
        if data != None:
            self.length = len(data)
        else:
            self.length = 0
        self.packet = None

    def encode_packet(self):
        self.header = pack("III", self.type, self.seq_number, self.rwnd)
        if self.type == __DATA_PACKET__:
            self.packet = self.header + self.data
        else:
            self.packet = self.header

    def decode_packet(self, packet):
        self.packet = packet
        self.header = packet[:12]
        self.type, self.seq_number, self.rwnd = unpack("III", self.header)
        if self.type == __DATA_PACKET__:
            self.data = packet[12:]
            self.length = len(self.data)
        else:
            self.data = None




class RCV_BUFFER(object):

    def __init__(self):
        self.rwnd_size = 1024 * 100
        self.rwnd = self.rwnd_size
        self.received_ooo = set()
        self.ooo_queue = PriorityQueue()
        self.last_received_io = -1
        self.data_processed = 0
        self.data_buffer = b''
        self.buffer_size = 0

    def put(self, seq_number, length, data):


        ''' if packet is within the range of rwnd'''
        if (seq_number - self.last_received_io) * __MSS__ + self.data_processed  <= self.rwnd:

            if seq_number == self.last_received_io + 1:
                self.data_buffer += data
                self.last_received_io += 1
                self.data_processed += length
                '''' cycle through to check out of order packets'''
                while True:

                    if (self.last_received_io + 1) in self.received_ooo:
                        self.received_ooo.remove(self.last_received_io + 1)
                        self.last_received_io += 1
                        packet = self.ooo_queue.get()
                        self.data_buffer += packet.data
                        self.data_processed += packet.length
                    else:
                        break
            elif seq_number > self.last_received_io and seq_number not in self.received_ooo:
                self.received_ooo.add(seq_number)
                p = buffer_packet(seq_number, data)
                self.ooo_queue.put(p)

        self.buffer_size = len(self.data_buffer)
        self.rwnd = self.rwnd_size + self.data_processed



    def return_data(self, length):
        return_data = b''
        curr_length = 0
        if self.buffer_size <= length:
            return_data = self.data_buffer
            self.data_buffer = b''
        else:
            return_data = self.data_buffer[:length]
            self.data_buffer = self.data_buffer[length:]

        self.buffer_size = len(self.data_buffer)
        self.rwn = self.rwnd_size -  + self.data_processed
        return return_data

    def data_ready(self):
        if self.buffer_size > 0:
            return True
        else:
            return False

    def should_not_buffer(self, seq_number):

        if (seq_number - self.last_received_io) * __MSS__ + self.data_processed  > self.rwnd:
            return True
        else:
            return False



    def clear(self):
        self.rwnd = self.rwnd_size
        self.data = b''
        self.ooo_queue.queue.clear()
        self.length = 0
        self.last_received_io = -1

class buffer_packet(object):

    def __init__(self, priority, data):
        self.data = data
        self.length = len(data)
        self.seq_number = priority
        self.priority = priority

    def return_data(self, length):
        if length >= self.length:
            return_data = self.data
            self.data = b''
            self.length = 0
            return return_data

        else:
            return_data = self.data[:length]
            self.data = self.data[length:]
            self.length = len(self.data)
            return return_data

    def __eq__(self, other):
        try:
            return self.priority == other.priority
        except AttributeError:
            return NotImplemented
    def __lt__(self, other):
        try:
            return self.priority < other.priority
        except AttributeError:
            return NotImplemented
