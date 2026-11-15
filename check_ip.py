# check_ip.py
# Prints the IP address of the auth server phone on the hotspot network.

import socket

# Any device on the hotspot network will do as a target, here it is the resolver laptop.
PEER_IP = "10.178.163.16"
PEER_PORT = 8000

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# connect() on a UDP socket sends nothing. It only makes the OS
# choose the network interface used to reach the peer.
sock.connect((PEER_IP, PEER_PORT))

# getsockname() returns the local address of the socket, so the first field is the phone's own IP.
print("This phone's IP on the hotspot network:", sock.getsockname()[0])
sock.close()