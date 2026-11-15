# MiniDNS/1.0 resolver. It answers the queries of the client from its cache and asks
# the auth server only on a cache miss. Every datagram is handled in its own thread.

import socket
import threading
import time

LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 8000
AUTH_IP = "10.178.163.30"
AUTH_PORT = 9000
AUTH_TIMEOUT = 1.0      # the resolver waits 1 s for the auth server
LOG_FILE = "resolver.log"

# The cache maps a domain to its IP address and its expiry time, which is arrival time plus TTL.
cache = {}
cache_lock = threading.Lock()      # the lock protects the cache, because threads share it
log_lock = threading.Lock()


# Print a time-stamped line with millisecond resolution and append it to the log file.
def log(text):
    now = time.time()
    line = time.strftime("%H:%M:%S", time.localtime(now)) + ".%03d" % (now % 1 * 1000) + "  " + text
    with log_lock:
        print(line)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")


# Send one REQ with the same id to the auth server on a separate socket.
# It returns the reply, or None if no reply arrives within 1 s.
def ask_auth(rid, domain):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(AUTH_TIMEOUT)
    try:
        s.sendto(("REQ:%s:%s" % (rid, domain)).encode("utf-8"), (AUTH_IP, AUTH_PORT))
        data, _ = s.recvfrom(1024)
        return data.decode("utf-8", errors="replace").strip()
    except OSError:
        return None
    finally:
        s.close()


# Answer one REQ, from the cache on a hit and from the auth server on a miss.
def resolve(rid, domain):
    now = time.time()
    with cache_lock:
        entry = cache.get(domain)
        # The entry is valid while its expiry time lies in the future.
        if entry and entry[1] > now:
            left = max(1, int(entry[1] - now))      # the remaining TTL is at least 1
            ip = entry[0]
            hit = True
        else:
            hit = False
            if entry:
                del cache[domain]      # an expired entry is deleted and the query is a miss
                log("EXPIRED  id=%s %s" % (rid, domain))

    if hit:
        log("HIT      id=%s %s ttl_left=%ds" % (rid, domain, left))
        return "RES:%s:%s:%d:cache" % (rid, ip, left)

    # Cache miss. The time spent at the auth server is measured and logged.
    start = time.time()
    reply = ask_auth(rid, domain)
    ms = (time.time() - start) * 1000

    # No reply, or a reply with a different id, gives ERR 504.
    if reply is None:
        log("MISS     id=%s %s no reply from auth (%.1f ms)" % (rid, domain, ms))
        return "ERR:%s:504:UpstreamTimeout" % rid

    parts = reply.split(":")
    if len(parts) < 2 or parts[1] != rid:
        log("MISS     id=%s %s bad reply from auth: %s" % (rid, domain, reply))
        return "ERR:%s:504:UpstreamTimeout" % rid

    # A valid RES is stored for the full TTL and passed on with the source auth.
    if parts[0] == "RES" and len(parts) == 5:
        try:
            ttl = int(parts[3])
        except ValueError:
            return "ERR:%s:504:UpstreamTimeout" % rid
        with cache_lock:
            cache[domain] = (parts[2], time.time() + ttl)
        log("MISS     id=%s %s -> %s ttl=%d (auth took %.1f ms)" % (rid, domain, parts[2], ttl, ms))
        return "RES:%s:%s:%d:auth" % (rid, parts[2], ttl)

    # An ERR from the auth server is passed on unchanged and is not cached.
    if parts[0] == "ERR":
        log("MISS     id=%s %s auth said %s (%.1f ms)" % (rid, domain, reply, ms))
        return reply

    log("MISS     id=%s %s unexpected reply: %s" % (rid, domain, reply))
    return "ERR:%s:504:UpstreamTimeout" % rid


# Build the reply for one message. The message type is matched case-insensitively.
def handle(msg):
    parts = msg.split(":")
    kind = parts[0].upper()

    if kind == "PING" and len(parts) == 2 and parts[1]:
        return "PONG:" + parts[1]

    # FLUSH deletes all entries from the cache and is answered with an ACK.
    if kind == "FLUSH" and len(parts) == 2 and parts[1]:
        with cache_lock:
            cache.clear()
        log("CACHE    flushed")
        return "ACK:" + parts[1]

    if kind == "REQ" and len(parts) == 3 and parts[1] and parts[2]:
        return resolve(parts[1], parts[2].lower())      # domain names are case-insensitive

    # Anything else is a bad request. If no id can be read, the id is 0.
    rid = parts[1] if len(parts) > 1 and parts[1] else "0"
    return "ERR:%s:400:BadRequest" % rid


# Runs in its own thread, so several clients can be served at the same time.
def serve(sock, data, addr):
    msg = data.decode("utf-8", errors="replace").strip()
    log("IN       %s  from %s:%d" % (msg, addr[0], addr[1]))
    reply = handle(msg)
    try:
        # The reply goes to the source address of the request.
        sock.sendto(reply.encode("utf-8"), addr)
    except OSError:
        return
    log("OUT      %s  to %s:%d" % (reply, addr[0], addr[1]))


def main():
    # One UDP socket on port 8000. SO_REUSEADDR lets the resolver restart on the same port at once.
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    sock.bind((LISTEN_HOST, LISTEN_PORT))
    log("MiniDNS/1.0 resolver listening on port %d (auth server %s:%d)"
        % (LISTEN_PORT, AUTH_IP, AUTH_PORT))

    try:
        while True:
            try:
                data, addr = sock.recvfrom(1024)
            except ConnectionResetError:
                continue      # Windows reports an ICMP error of an earlier send this way, so it is ignored
            threading.Thread(target=serve, args=(sock, data, addr), daemon=True).start()
    except KeyboardInterrupt:
        log("Resolver stopped")      # Ctrl+C ends the resolver cleanly
    finally:
        sock.close()


main()
