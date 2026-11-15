# MiniDNS/1.0

CS-327 Computer Communication Networks, Complex Engineering Problem, Option B (Mini DNS Service).
Group: Maryam Siddiqa (CS-24012) and Nikeeta Kumari (CS-24046).

MiniDNS/1.0 is our own text-based protocol over UDP. The client, the resolver and the auth server are written in Python 3 with standard library modules only.

## Hosts

| Host | Program | UDP port |
|-------------------|-----------|-----------|
| H1 client (phone) | client.py | ephemeral |
| H2 resolver (laptop) | resolver.py | 8000 |
| H3 auth server (phone, hotspot) | authserver.py | 9000 |

## How to run

1. Start authserver.py on H3.
2. Start resolver.py on H2.
3. Start client.py on H1 and use the menu.

The IP addresses are set at the top of client.py and resolver.py. check_ip.py prints the IP address of the phone on the hotspot network.

## Files

- client.py, resolver.py, authserver.py: the three programs
- check_ip.py: prints the IP address of the auth server phone
- client.log, resolver.log, authserver.log: logs of the three programs
- performance_results.csv: results of the performance test
- MiniDNS_capture.pcapng: Wireshark capture of the system
- Graphs_MiniDNS.ipynb: Matplotlib notebook that draws the graphs of the report
