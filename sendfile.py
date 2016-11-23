#test2.py
import time

"""
Send a file using the MP2 transport
"""



import sys
import os
if os.environ.get("MP2_TEST", None) == "yes":
    from transport_cffi import MP2Socket, MP2SocketError
else:
    from transport import MP2Socket, MP2SocketError

'''
if len(sys.argv) != 4:
    print("Usage: python {} <host> <port> <filename>".format(__file__))
    sys.exit(1)
'''



host =  sys.argv[1]
port = 18506 #int(sys.argv[2])
filename = '100KB_file.txt'#sys.argv[3]

f = open(filename, 'rb')

socket = MP2Socket()
try:
    socket.connect((host, port))
except MP2SocketError:
    print("Error connecting to host")
    sys.exit(1)

start_time = time.time()
total_data = 0
while True:
    data = f.read(1488)
    total_data += len(data)
    if not data:
        print("done with data")
        break
    socket.send(data)


socket.close()
end_time = time.time()
bits = total_data * 8
bps = bits / (end_time - start_time)
Kbps = bps / 1000
time_elapsed = end_time - start_time
print("Total Transfer Time: " + str(time_elapsed))
print(total_data)
print("Throughput: " + str(Kbps) + " Kbps")
socket.close()
f.close()
