
from queue import *
import time
"""
Receive a file using the MP2 transport
"""

import sys
import os
if os.environ.get("MP2_TEST", None) == "yes":
    from transport_cffi import MP2Socket, MP2SocketError
else:
    from transport import MP2Socket, MP2SocketError
'''
if len(sys.argv) != 3:
    print("Usage: python {} <port> <filename>".format(__file__))
    sys.exit(1)
'''

port = 18506 #int(sys.argv[1])
filename = 'dump.txt' #sys.argv[2]

f = open(filename, 'wb')

socket = MP2Socket()
try:
    (client_host, client_port) = socket.accept(port)
except MP2SocketError:
    print("Error connecting to host")
    sys.exit(1)
start_time = time.time()
total_data = 0


print("Got connection from {}:{}".format(client_host, client_port))
while True:
    data = socket.recv(1488)
    #print("RECV COMPLETE")
    #print(len(data))
    total_data += len(data)
    if not data:
        break
    f.write(data)

end_time = time.time()
bits = total_data * 8
bps = bits / (end_time - start_time)
Kbps = bps / 1000
time_elapsed = end_time - start_time
print("Total Transfer Time: " + str(time_elapsed))
print(total_data)
print("Throughput: " + str(Kbps) + " Kbps")
print("Sending successful")

f.close()
socket.close()
