import signal
import sys
import socket
import threading
import math
from struct import *
from data_handler import *
from select import *
import time


__MSS__ = 1488
__ALPHA__ = round((1 / 8), 3)
__BETA__ = round((1 / 4), 3)
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
__SERVER__ = 1
__CLIENT__ = 2



def signal_handler(signal, frame):
        print('You pressed Ctrl+C!')
        sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


class MP2SocketError(Exception):
    """ Exception base class for protocol errors """
    pass



class MP2Socket:
    def __init__(self):
        self.target = None
        self.rwnd = 1024 * 100
        self.cwnd = 10 * __MSS__
        self.ssthresh = 1024 * 100
        self.RTO = 1.0
        self.RTTVAR = None
        self.SRTT = None
        self.socket = None
        self.seq_number = 0
        self.connection_state = __CONNECTION_CLOSED__
        self.socket_type = None
        self.rcv_buffer = None
        self.protocol = __SLOW_START__
        self.send_buffer = {}
        self.send_time = {}
        self.threads = []
        self.ack_thread = None
        self.last_ack = 0
        self.lock = threading.Lock()
        self.port = None
        self.stop = True
        self.data_received = 0
        self.ack_address_check = None
        self.send_length = {}
        self.throughput = 0
        self.data_sent = 0
        self.data_acked = 0
        #print("Init", file=sys.stdout)


    def connect(self, addr):
        """
        Connects to a remote MP2 transport server. Address is specified by a
        pair `(host,port)`, where `host` is a string with either an IP address
        or a hostname, and `port` is a UDP port where data will arrive

        A client must call `connect` as the first operation on the socket.

        This call raises MP2SocketError if a connection cannot be established.
        It does not return any value on success
        """

        ''' create socket and send initial handshake ack '''
        self.f = open('log.txt', 'w')
        self.target = addr
        self.socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        init_ack = MSG(__ACK__, self.seq_number)
        init_ack.encode_packet()


        send_time_ms = time.time()
        self.socket.sendto(init_ack.packet, self.target)

        ''' get local port'''
        local_address = self.socket.getsockname()
        self.port = local_address[1]

        ''' initialize timeout and wait for respone '''
        self.socket.settimeout(1.0)

        attempts = 0
        while True:

            try:
                second_ack, address = self.socket.recvfrom(50)
                print("Heard from {}".format(address), file=sys.stdout)
                break

            except socket.timeout:
                if attempts == 12:
                    raise MP2SocketError
                else:
                    print("connect timed out")
                    self.socket.sendto(init_ack.packet, self.target)
                    send_time_ms = time.time()
                    attempts += 1

        self.socket.settimeout(None)
        self.socket.setblocking(0)
        self.connection_state = __CONNECTION_OPEN__


        self.ack_address_check = address

        ''' calculate inital RTT'''
        receive_time_ms = time.time()
        R_PRIME = round(receive_time_ms - send_time_ms, 3)
        self.SRTT = R_PRIME
        self.RTTVAR = R_PRIME / 2
        self.RTTVAR = (1 - __BETA__) * self.RTTVAR + __BETA__ * abs(self.SRTT - R_PRIME)
        self.RTTVAR = round(self.RTTVAR, 3)
        self.SRTT = (1 - __ALPHA__) * self.SRTT + __ALPHA__ * R_PRIME
        self.SRTT =  round(self.SRTT, 3)
        self.RTO = self.SRTT + 4 * self.RTTVAR




        ''' process handshake response'''
        rec_ack = MSG()
        rec_ack.decode_packet(second_ack)
        self.rwnd = rec_ack.rwnd
        self.socket_type = __CLIENT__

        thread = threading.Thread(target=self.handle_acks)
        self.ack_thread = thread
        self.threads.append(thread)
        thread.start()


        """ spawn ack thread """





    def accept(self, port):
        """
        Waits for a connection on a given (UDP) port. Returns a pair
        `(host,port)` representing the client address.

        A server must call `accept` as the first operation on the socket.

        Raises MP2SocketError if an error is encountered (e.g., UDP port
        already in use)


        """
        #should take care of bind, listen, and accept

        #sys.stderr.write("Called Connect")
        if self.connection_state == __CONNECTION_OPEN__:
            sys.stderr.write("CONNECTION ALREADY EXISTS")
        print("ACCEPT")

        self.port = port
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.bind(('', self.port))
        except socket.error:
            raise MP2SocketError
        ''' wait for initial connection and log address of sender '''
        initial_handshake, self.target = self.socket.recvfrom(16)
        initial_ack = MSG()
        initial_ack.decode_packet(initial_handshake)


        ''' send response ack'''
        response_ack = MSG(__ACK__, self.seq_number, self.rwnd)
        response_ack.encode_packet()
        self.socket.sendto(response_ack.packet, self.target)
        ''' get local port'''
        self.rcv_buffer = RCV_BUFFER()
        self.connection_state = __CONNECTION_OPEN__
        self.socket_type = __SERVER__


        return self.target

    def send(self, data):
        """
        Send data to the remote destination. Data may be of arbitrary length
        and should be split into smaller packets. This call should block
        for flow control, though you can buffer some small amount of data.
        This call should behave like `sendall` in Python; i.e., all data must
        be sent. Does not return any value.

        Should be called on a socket after connect or accept
        """

        """ add data to send buffer """

        #

        length_buffered = 0
        start_seq = self.seq_number
        #print("IN SEND")
        while len(data) != 0:
            if len(data) > __MSS__:
                send_data = data[:__MSS__]
                data = data[__MSS__:]
            else:
                send_data = data
                data = b''

            packet = MSG(__DATA_PACKET__, self.seq_number, 0, send_data)
            packet.encode_packet()
            self.send_buffer[self.seq_number] = packet
            self.send_length[self.seq_number] = packet.length


            while True:
                if self.rwnd  > self.cwnd:
                    upper_bound = self.cwnd + self.data_acked
                else:
                    upper_bound = self.rwnd + self.data_acked
                if packet.length + self.data_sent <= upper_bound:
                    break




            self.data_sent += packet.length

            r = [self.socket]
            w = [self.socket]
            e = [self.socket]

            readable, writeable, exceptions = select(r, w, e)

            while self.socket not in writeable:
                readable, writeable, exceptions = select(r, w, e)


            self.lock.acquire()
            send_time = time.time()
            data_sent = self.socket.sendto(packet.packet, self.target)
            self.lock.release()
            end_time = time.time()
            self.send_time[self.seq_number] = send_time
            self.seq_number += 1


    def recv(self, length):
        """
        Receive data from the remote destination. Should wait until data
        is available, then return up to `length` bytes. Should return "" when
        the remote end closes the socket
        """
        #print("Entering Recv")
        if self.connection_state == __CONNECTION_CLOSED__ and not self.rcv_buffer.data_ready():
            return ""

        r = [self.socket]
        w = [self.socket]
        e = [self.socket]
        #print("Requested Length {}\n ".format(length), file=sys.stderr)


        return_data = b''
        while True:

            readable, writeable, exceptions = select(r, w, e)

            if self.socket in readable and self.connection_state == __CONNECTION_OPEN__:

                packet , sender = self.socket.recvfrom(1500)

                if sender == self.target:
                    msg = MSG()
                    msg.decode_packet(packet)
                    ''' Client Socket Closed, send FIN and return '''
                    if msg.type == __FIN__:

                        fin_ack = MSG(__FIN__, msg.seq_number, self.rcv_buffer.rwnd)
                        fin_ack.encode_packet()
                        self.socket.sendto(fin_ack.packet, self.target)
                        self.connection_state = __CONNECTION_CLOSED__
                        sys.stderr.write("Received Fin")


                        if not self.rcv_buffer.data_ready():
                            return ""

                    elif msg.type == __ACK__:
                        connect_ack = MSG(__SYN__, msg.seq_number, self.rcv_buffer.rwnd)
                        connect_ack.encode_packet()
                        self.socket.sendto(connect_ack.packet, self.target)


                    elif msg.type == __DATA_PACKET__:


                        if msg.seq_number > self.rcv_buffer.last_received_io:
                            self.rcv_buffer.put(msg.seq_number, msg.length, msg.data)
                            ack = MSG(__ACK__, self.rcv_buffer.last_received_io + 1, self.rcv_buffer.rwnd)
                            ack.encode_packet()
                            numbytes = self.socket.sendto(ack.packet, self.target)


                    if self.rcv_buffer.data_ready():
                        return self.rcv_buffer.return_data(length)

            elif self.rcv_buffer.data_ready():
                return self.rcv_buffer.return_data(length)



    def close(self):
        """
        Closes the socket and informs the other end that no more data will
        be sent
        """
        if self.socket_type == __CLIENT__:
            while True:
                if self.last_ack == self.seq_number:
                    self.connection_state = __CONNECTION_CLOSED__
                    break



            self.ack_thread.join()
            del self.threads[0]

            fin = MSG(__FIN__, self.seq_number)
            fin.encode_packet()
            self.socket.sendto(fin.packet, self.target)

            """ Wait for acknowledgement from receiver that connection is closed"""
            self.socket.settimeout(self.RTO)
            attempts = 0
            while attempts < 10:
                try:
                    self.socket.sendto(fin.packet, self.target)
                    attempts += 1
                except socket.gaierror:
                    print("Server closed")



            try:
                ack, address = self.socket.recvfrom(16)
            except socket.timeout:
                    print("DIDNT RECEIVE FIN")
            except socket.gaierror:
                    print("socket on other end is closed")



        self.socket.close()
        self.socket_state = __SOCKET_CLOSED__
        self.socket_type = None
        self.send_buffer = None
        self.send_time = None
        self.threads = None

    def handle_acks(self):



        ack_counter = 0
        new_acks = 0

        r = [self.socket]
        w = [self.socket]
        e = [self.socket]
        start_time = time.time()

        while self.connection_state == __CONNECTION_OPEN__:

            readable, writeable, exceptions = select(r, w, e)

            if self.socket in readable:

                self.lock.acquire()
                packet, address = self.socket.recvfrom(16)
                receive_time = time.time()
                self.lock.release()
                ack = MSG()
                ack.decode_packet(packet)



                if ack.type == __SYN__:
                    print("Acknowledgement from connection") # Because we the ack from the receiver may be dropped on connection

                elif address == self.ack_address_check:
                    #print("Recevied ACK {}".format(ack.seq_number))


                    if ack.seq_number > self.last_ack:
                        new_acks = ack.seq_number - self.last_ack

                        for i in range(self.last_ack, ack.seq_number):
                            if self.send_buffer.get(i) != None:
                                self.data_acked += len(self.send_buffer[i].data) # keep track of how much data has been acked

                        if ack.seq_number == self.last_ack + 1:
                            self.estimate_RTT(receive_time,  ack.seq_number)

                        self.last_ack = ack.seq_number

                    #congestion control and reliable transfer implementation

                    if self.protocol == __SLOW_START__:

                        if self.cwnd >= self.ssthresh:
                            self.protocol = __CONGESTION_AVOIDANCE__

                        elif new_acks > 0:
                            self.cwnd +=  2 * new_acks * __MSS__
                            new_acks = 0

                    elif self.protocol == __CONGESTION_AVOIDANCE__:
                        if new_acks > 0:
                            self.cwnd += math.ceil((2 * new_acks * __MSS__  * __MSS__)/ self.cwnd)
                            new_acks = 0

            # check to see if there was a timeout on the last unacknowledge segment
            elif self.last_ack in self.send_time:
                if round(time.time() - self.send_time[self.last_ack], 3) > self.RTO:

                    """ retransmit missing segment """

                    retransmit_packet = self.send_buffer[self.last_ack]
                    attempts = 0
                    while attempts < 2:
                        self.send_time[retransmit_packet.seq_number] = time.time()
                        self.lock.acquire()
                        self.socket.sendto(retransmit_packet.packet, self.target)
                        self.lock.release()
                        attempts += 1

                    #print("Retransmitted {}".format(self.last_ack))

                    self.ssthresh = self.cwnd / 2
                    self.cwnd = 5 *  __MSS__
                    self.protocol = __SLOW_START__




    def estimate_RTT(self, receive_time,  seq_number):

        #RTTVAR <- (1 - beta) * RTTVAR + beta * |SRTT - R'|
        #SRTT <- (1 - alpha) * SRTT + alpha * R'
        #RTO <- SRTT + max (G, K*RTTVAR)
        """ Calculate new timeout value """
        R_PRIME = round(receive_time - self.send_time[seq_number - 1], 3 )
        self.RTTVAR = (1 - __BETA__) * self.RTTVAR + __BETA__ * abs(self.SRTT - R_PRIME)
        self.RTTVAR = round(self.RTTVAR, 3)
        self.SRTT = (1 - __ALPHA__) * self.SRTT + __ALPHA__ * R_PRIME
        self.SRTT =  round(self.SRTT, 3)
        self.RTO = self.SRTT + 4 * self.RTTVAR

        """ clear old send times """
        for i in range(self.last_ack, seq_number):
            if self.send_time.get(i) != None :
                del self.send_time[i]
