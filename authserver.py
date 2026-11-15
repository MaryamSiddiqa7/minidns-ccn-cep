# MiniDNS/1.0 auth server. It holds the zone and answers REQ and PING messages over UDP.

import socket
import time

HOST = "0.0.0.0"          # listen on every interface of the phone
PORT = 9000
DELAY_MS = 0              # optional artificial delay before each reply, 0 in all runs
LOG_FILE = "authserver.log"

# The zone has seven records. Each host name maps to an IP address and a TTL in seconds.
ZONE = {
    "www.minidns.test":     ("10.0.0.10", 60),
    "mail.minidns.test":    ("10.0.0.20", 30),
    "ftp.minidns.test":     ("10.0.0.30", 10),
    "lab.minidns.test":     ("10.0.0.40", 120),
    "portal.minidns.test":  ("10.0.0.50", 45),
    "library.minidns.test": ("10.0.0.60", 90),
    "news.minidns.test":  ("10.0.0.70", 75),
}


# Print a time-stamped line with millisecond resolution and append it to the log file.
def log(text):
    now = time.time()
    line = time.strftime("%H:%M:%S", time.localtime(now)) + ".%03d" % (now % 1 * 1000) + "  " + text
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

# Build the reply for one message. Fields are split on the colon and the message
# type is matched case-insensitively.
def handle(msg):
    parts = msg.split(":")
    kind = parts[0].upper()

    # PING is answered with a PONG that carries the same id.
    if kind == "PING" and len(parts) == 2 and parts[1]:
        return "PONG:" + parts[1]

    if kind == "REQ" and len(parts) == 3 and parts[1] and parts[2]:
        rid = parts[1]
        domain = parts[2].lower()      # domain names are case-insensitive
        if domain in ZONE:
            ip, ttl = ZONE[domain]
            return "RES:%s:%s:%d:auth" % (rid, ip, ttl)
        return "ERR:%s:404:NotFound" % rid     # the domain is not in the zone

    # Anything else is a bad request. The id is repeated if it can be read, otherwise it is 0.
    rid = parts[1] if len(parts) > 1 and parts[1] else "0"
    return "ERR:%s:400:BadRequest" % rid


def main():
    # One UDP socket on port 9000 and one loop serve all messages.
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, PORT))
    log("MiniDNS/1.0 auth server listening on port %d" % PORT)

    try:
        while True:
            data, addr = sock.recvfrom(1024)     # one message is at most 1024 bytes
            msg = data.decode("utf-8", errors="replace").strip()
            log("IN  %s  from %s:%d" % (msg, addr[0], addr[1]))

            if DELAY_MS > 0:
                time.sleep(DELAY_MS / 1000)

            reply = handle(msg)
            # The reply goes to the source address of the request, so no client address is stored.
            sock.sendto(reply.encode("utf-8"), addr)
            log("OUT %s  to %s:%d" % (reply, addr[0], addr[1]))
    except KeyboardInterrupt:
        log("Server stopped")      # Ctrl+C ends the server cleanly
    finally:
        sock.close()


main()