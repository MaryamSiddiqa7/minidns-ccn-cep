# MiniDNS/1.0 client. It sends REQ, PING, FLUSH and raw messages to the resolver over UDP
# and runs the performance test of menu option 5.

import socket
import time
import random
import statistics
import os

RESOLVER_IP = "10.178.163.16"
RESOLVER_PORT = 8000
TIMEOUT = 2.0              # the client waits 2 s for a reply
RETRIES = 2                # up to two retransmissions, so three attempts
LOG_FILE = "client.log"
MEASURE_FILE = "performance_results.csv"

# Print a time-stamped line with millisecond resolution and append it to the log file.
def log(text):
    now = time.time()
    line = time.strftime("%H:%M:%S", time.localtime(now)) + ".%03d" % (now % 1 * 1000) + "  " + text
    print(line)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass      # a failed log write must not stop the client


# The reply repeats this random four-digit id, so it can be matched to its request.
def new_id():
    return str(random.randint(1000, 9999))

# Send one message and wait for the reply with the same id.
# Returns the reply, the time in milliseconds and the number of attempts.
def exchange(msg, rid, silent=False):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)     # a new socket for every exchange
    start = time.perf_counter()      # the time starts at the first transmission
    try:
        for attempt in range(1, RETRIES + 2):
            try:
                s.sendto(msg.encode("utf-8"), (RESOLVER_IP, RESOLVER_PORT))
            except OSError as e:
                if not silent:
                    log("SEND ERROR %s" % e)
                return None, (time.perf_counter() - start) * 1000, attempt
            if not silent:
                log("OUT  %s  (attempt %d)" % (msg, attempt))
            deadline = time.perf_counter() + TIMEOUT
            while True:
                left = deadline - time.perf_counter()
                if left <= 0:
                    break
                s.settimeout(left)
                try:
                    data, _ = s.recvfrom(1024)
                except socket.timeout:
                    break      # no reply in 2 s, so the same message is sent again
                except OSError as e:
                    if not silent:
                        log("RECV ERROR %s" % e)
                    break
                reply = data.decode("utf-8", errors="replace").strip()
                parts = reply.split(":")
                if len(parts) >= 2 and parts[1] == rid:
                    ms = (time.perf_counter() - start) * 1000
                    if not silent:
                        log("IN   %s  (%.1f ms)" % (reply, ms))
                    return reply, ms, attempt
                # A reply with a different id is ignored and the wait continues.
                if not silent:
                    log("IGNORED reply with wrong id: %s" % reply)
            if not silent:
                log("TIMEOUT on attempt %d" % attempt)
        # All three attempts failed.
        return None, (time.perf_counter() - start) * 1000, RETRIES + 1
    finally:
        s.close()

# Show a reply. RES gives the IP address, TTL and source, ERR gives the code and reason.
def show(reply):
    if reply is None:
        print(">> ERROR: Resolver server is unreachable after %d attempts!" % (RETRIES + 1))
        return
    p = reply.split(":")
    if p[0] == "RES" and len(p) == 5:
        print(">> IP: %s | TTL: %ss | Source: %s" % (p[2], p[3], p[4]))
    elif p[0] == "ERR" and len(p) >= 4:
        print(">> ERROR %s: %s" % (p[2], p[3]))
    else:
        print(">> %s" % reply)

def query(domain):
    if not domain:
        print(">> ERROR: Domain name cannot be empty!")
        return None, 0.0, 0
    rid = new_id()
    reply, ms, tries = exchange("REQ:%s:%s" % (rid, domain), rid)
    show(reply)
    print("   [Time = %.1f ms | Attempts = %d]" % (ms, tries))
    return reply, ms, tries

# PING and PONG give the round-trip time to the resolver.
def ping():
    rid = new_id()
    reply, ms, tries = exchange("PING:%s" % rid, rid)
    if reply is None:
        print(">> ERROR: Resolver server is unreachable!")
    else:
        print(">> %s" % reply)
    print("   [RTT = %.1f ms]" % ms)


# FLUSH empties the cache of the resolver and is answered with an ACK.
def flush():
    rid = new_id()
    reply, ms, tries = exchange("FLUSH:%s" % rid, rid)
    if reply is None:
        print(">> ERROR: Resolver server is unreachable!")
    else:
        print(">> %s" % reply)


# Send any text as one message, for example HELLO to test ERR 400.
def raw():
    msg = input("Raw packet: ").strip()
    if not msg:
        print(">> ERROR: Packet cannot be empty!")
        return
    p = msg.split(":")
    rid = p[1] if len(p) > 1 and p[1] else "0"      # if no id can be read, the id is 0
    reply, ms, tries = exchange(msg, rid)
    show(reply)


def read_count():
    try:
        n = int(input("Number of runs (min 5): ") or "5")
    except ValueError:
        n = 5
    return max(n, 5)

# Append the values of one condition to the CSV file. If the file cannot be saved
# in the working folder, the Download folder is used instead.
def save_rows(test, domain, values):
    paths = [
        MEASURE_FILE,
        os.path.join("/sdcard/Download", MEASURE_FILE),
        os.path.join("/storage/emulated/0/Download", MEASURE_FILE)
    ]
    for path in paths:
        try:
            file_exists = os.path.exists(path)
            with open(path, "a") as f:
                if not file_exists or os.path.getsize(path) == 0:
                    f.write("test,domain,run,value\n")
                for i, v in enumerate(values, 1):
                    f.write("%s,%s,%d,%.2f\n" % (test, domain, i, v))
            return True
        except OSError:
            continue
    print("  [Note: Results displayed above; CSV save skipped due to storage permission]")
    return False


# One lookup of the performance test. It also returns the source of the reply, auth or cache.
def timed_query(domain, silent=True):
    rid = new_id()
    reply, ms, tries = exchange("REQ:%s:%s" % (rid, domain), rid, silent=silent)
    source = None
    if reply:
        p = reply.split(":")
        if p[0] == "RES" and len(p) == 5:
            source = p[4]
    return ms, tries, source


# Performance test, menu option 5. Each condition is measured n times, at least five.
# A run counts only if the reply came on the first attempt, so no 2 s timeout is included.
def measure():
    domain = input("Domain: ").strip()
    if not domain:
        print(">> ERROR: Domain name cannot be empty! Aborting test.")
        return

    # A first query checks that the resolver is reachable and the domain exists.
    rid = new_id()
    reply, ms, tries = exchange("REQ:%s:%s" % (rid, domain), rid, silent=True)

    if reply is None:
        print(">> ERROR: Resolver server is unreachable! Aborting test.")
        return
    elif reply.startswith("ERR:404"):
        print(">> ERROR: Domain '%s' not found in database! Aborting test." % domain)
        return
    elif reply.startswith("ERR:"):
        print(">> ERROR: Server returned %s! Aborting test." % reply)
        return

    n = read_count()
    rtts = []
    bursts = []
    misses = []
    hits = []
    tp_kbps = []
    tp_qps = []

    # Round-trip time with a pause of 0.2 s after each ping.
    print("\n[1/4] Running PING tests with 0.2 s gap (%d runs)..." % n)
    for i in range(n):
        rid = new_id()
        reply, ms, tries = exchange("PING:%s" % rid, rid, silent=True)
        if reply and reply.startswith("PONG:") and tries == 1:
            rtts.append(ms)
        print(".", end="", flush=True)
        time.sleep(0.2)
    print(" Done!")

    # Round-trip time of pings sent back to back.
    print("[2/4] Running back-to-back PING tests (%d runs)..." % n)
    for i in range(n):
        rid = new_id()
        reply, ms, tries = exchange("PING:%s" % rid, rid, silent=True)
        if reply and reply.startswith("PONG:") and tries == 1:
            bursts.append(ms)
        print(".", end="", flush=True)
    print(" Done!")

    # FLUSH makes the next query a miss and the one after it a hit.
    # The source field confirms which one each query was.
    print("[3/4] Running Cache MISS & HIT tests (%d runs)..." % n)
    for i in range(n):
        rid = new_id()
        exchange("FLUSH:%s" % rid, rid, silent=True)
        ms, tries, source = timed_query(domain, silent=True)
        if source == "auth" and tries == 1:
            misses.append(ms)
        ms, tries, source = timed_query(domain, silent=True)
        if source == "cache" and tries == 1:
            hits.append(ms)
        print(".", end="", flush=True)
        time.sleep(0.3)
    print(" Done!")

    # 30 queries in a row. A first query fills the cache, so the resolver answers all 30.
    print("[4/4] Running Throughput tests (%d runs x 30 queries)..." % n)
    rid = new_id()
    exchange("REQ:%s:%s" % (rid, domain), rid, silent=True)
    for i in range(n):
        total = 0
        ok = 0
        t0 = time.perf_counter()
        for j in range(30):
            rid = new_id()
            msg = "REQ:%s:%s" % (rid, domain)
            reply, ms, tries = exchange(msg, rid, silent=True)
            if reply:
                # Only the bytes of the request and the reply count, without headers.
                total += len(msg.encode("utf-8")) + len(reply.encode("utf-8"))
                ok += 1
        secs = time.perf_counter() - t0
        if ok and secs > 0:
            tp_kbps.append(total * 8 / secs / 1000.0)
            tp_qps.append(ok / secs)
        print(".", end="", flush=True)
        time.sleep(0.3)
    print(" Done!\n")

    # Summary with the average, standard deviation, minimum and maximum.
    print("=" * 65)
    print("              PERFORMANCE SUMMARY REPORT            ")
    print("=" * 65)
    print("Domain Target : %s" % domain)
    print("Total Runs    : %d per test condition" % n)
    print("-" * 65)
    print("%-12s %-10s %-10s %-10s %-10s" % ("METRIC", "AVG TIME", "STD DEV", "MIN TIME", "MAX TIME"))
    print("-" * 65)

    if rtts:
        print("%-12s %-10.1f %-10.1f %-10.1f %-10.1f" % 
              ("RTT (Ping)", statistics.mean(rtts), statistics.stdev(rtts) if len(rtts)>1 else 0.0, min(rtts), max(rtts)))
    if bursts:
        print("%-12s %-10.1f %-10.1f %-10.1f %-10.1f" % 
              ("RTT (burst)", statistics.mean(bursts), statistics.stdev(bursts) if len(bursts)>1 else 0.0, min(bursts), max(bursts)))
    if misses:
        print("%-12s %-10.1f %-10.1f %-10.1f %-10.1f" % 
              ("Cache MISS", statistics.mean(misses), statistics.stdev(misses) if len(misses)>1 else 0.0, min(misses), max(misses)))
    if hits:
        print("%-12s %-10.1f %-10.1f %-10.1f %-10.1f" % 
              ("Cache HIT", statistics.mean(hits), statistics.stdev(hits) if len(hits)>1 else 0.0, min(hits), max(hits)))
    print("-" * 65)

    if misses and hits:
        diff = statistics.mean(misses) - statistics.mean(hits)
        print(">> Cache Speedup (MISS avg - HIT avg) = %.1f ms" % diff)
    print("-" * 65)
    if tp_kbps:
        print("Throughput (kbit/s)   : avg %.1f | stdev %.1f | min %.1f | max %.1f" %
              (statistics.mean(tp_kbps), statistics.stdev(tp_kbps) if len(tp_kbps)>1 else 0.0, min(tp_kbps), max(tp_kbps)))
    if tp_qps:
        print("Throughput (queries/s): avg %.1f | stdev %.1f | min %.1f | max %.1f" %
              (statistics.mean(tp_qps), statistics.stdev(tp_qps) if len(tp_qps)>1 else 0.0, min(tp_qps), max(tp_qps)))
    print("=" * 65)

    # Save every run to the CSV file.
    s1 = save_rows("rtt", "-", rtts)
    s2 = save_rows("miss", domain, misses)
    s3 = save_rows("hit", domain, hits)
    s4 = save_rows("rtt_burst", "-", bursts)
    s5 = save_rows("throughput_kbps", domain, tp_kbps)
    s6 = save_rows("throughput_qps", domain, tp_qps)
    if s1 and s2 and s3 and s4 and s5 and s6:
        print("\n  [Success: Results recorded to %s]" % MEASURE_FILE)


# Menu of the client.
def main():
    print("MiniDNS/1.0 client -> %s:%d" % (RESOLVER_IP, RESOLVER_PORT))
    while True:
        print("\n--- MiniDNS Menu ---")
        print("1. DNS Query")
        print("2. Server Ping")
        print("3. Flush Cache")
        print("4. Raw Packet")
        print("5. Performance Test")
        print("0. Exit")
        c = input("Choice: ").strip()
        if c == "1":
            query(input("Domain: ").strip())
        elif c == "2":
            ping()
        elif c == "3":
            flush()
        elif c == "4":
            raw()
        elif c == "5":
            measure()
        elif c == "0":
            break


main()