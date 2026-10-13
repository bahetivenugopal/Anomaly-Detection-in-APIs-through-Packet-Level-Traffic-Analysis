"""
live_sniffer.py
---------------
BONUS MODULE — Real-world packet capture using Scapy + Npcap (Windows).
Captures actual packets from the network interface (real browser traffic).
Streams packet data to the dashboard via the proxy's WebSocket broadcaster.

Run this as Administrator on Windows.
Requires: Npcap installed (https://npcap.com)

Usage:
  python live_sniffer.py                      # Sniff all interfaces
  python live_sniffer.py --iface "Wi-Fi"      # Specific interface
  python live_sniffer.py --filter "tcp port 443"  # HTTPS only
  python live_sniffer.py --list               # List available interfaces
"""

import sys
import os
import time
import threading
import argparse
import json
import requests

try:
    from scapy.all import (
        sniff, get_if_list, get_working_ifaces,
        IP, TCP, UDP, ICMP, Ether, Raw,
        conf
    )
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False

# Push sniffer packets to proxy WebSocket via a simple HTTP relay
PROXY_URL = "http://localhost:8080"

_packet_queue = []
_queue_lock = threading.Lock()
_running = True
_packet_count = 0


def decode_tcp_flags(flags_int: int) -> str:
    """Decode TCP flags integer to readable string."""
    flag_map = {
        0x001: "FIN",
        0x002: "SYN",
        0x004: "RST",
        0x008: "PSH",
        0x010: "ACK",
        0x020: "URG",
        0x040: "ECE",
        0x080: "CWR",
    }
    active = [name for bit, name in flag_map.items() if flags_int & bit]
    return ",".join(active) if active else "NONE"


def get_protocol(pkt) -> str:
    if TCP in pkt:
        dst_port = pkt[TCP].dport
        src_port = pkt[TCP].sport
        if 443 in (dst_port, src_port):
            return "HTTPS/TLS"
        elif 80 in (dst_port, src_port):
            return "HTTP"
        elif 53 in (dst_port, src_port):
            return "DNS/TCP"
        return "TCP"
    elif UDP in pkt:
        dst_port = pkt[UDP].dport
        src_port = pkt[UDP].sport
        if 53 in (dst_port, src_port):
            return "DNS/UDP"
        elif 443 in (dst_port, src_port):
            return "QUIC"
        return "UDP"
    elif ICMP in pkt:
        return "ICMP"
    return "OTHER"


def packet_callback(pkt):
    """Called for every captured packet."""
    global _packet_count

    if not IP in pkt:
        return  # Skip non-IP packets

    _packet_count += 1

    # Extract fields
    src_ip = pkt[IP].src
    dst_ip = pkt[IP].dst
    ttl    = pkt[IP].ttl
    ip_len = pkt[IP].len
    proto  = get_protocol(pkt)

    tcp_flags  = ""
    src_port   = 0
    dst_port   = 0
    seq        = 0
    ack_num    = 0
    window     = 0
    payload_sz = 0

    if TCP in pkt:
        tcp_flags = decode_tcp_flags(int(pkt[TCP].flags))
        src_port  = pkt[TCP].sport
        dst_port  = pkt[TCP].dport
        seq       = pkt[TCP].seq
        ack_num   = pkt[TCP].ack
        window    = pkt[TCP].window
        payload_sz = len(pkt[TCP].payload) if pkt[TCP].payload else 0

    elif UDP in pkt:
        src_port  = pkt[UDP].sport
        dst_port  = pkt[UDP].dport
        payload_sz = len(pkt[UDP].payload) if pkt[UDP].payload else 0

    record = {
        "packet_id":    _packet_count,
        "timestamp":    time.time(),
        "src_ip":       src_ip,
        "dst_ip":       dst_ip,
        "src_port":     src_port,
        "dst_port":     dst_port,
        "protocol":     proto,
        "tcp_flags":    tcp_flags,
        "seq_num":      seq,
        "ack_num":      ack_num,
        "window_size":  window,
        "ttl":          ttl,
        "ip_length":    ip_len,
        "payload_size": payload_sz,
        "source":       "real_capture",
    }

    with _queue_lock:
        _packet_queue.append(record)
        if len(_packet_queue) > 200:
            _packet_queue.pop(0)

    # Print to console
    print(
        f"[{_packet_count:5}] {proto:12} "
        f"{src_ip:15}:{src_port:<5} → {dst_ip:15}:{dst_port:<5} "
        f"Flags={tcp_flags:12} Len={ip_len:5} Seq={seq}"
    )


def relay_to_dashboard():
    """Background thread: push captured packets to proxy for WebSocket broadcast."""
    while _running:
        time.sleep(0.5)
        with _queue_lock:
            if not _packet_queue:
                continue
            batch = list(_packet_queue[-10:])  # Send latest 10

        try:
            requests.post(
                f"{PROXY_URL}/api/sniffer_batch",
                json={"packets": batch},
                timeout=2
            )
        except Exception:
            pass  # Proxy may not be running — that's OK for standalone mode


def list_interfaces():
    """Print all available network interfaces."""
    print("\nAvailable network interfaces:")
    print("-" * 50)
    try:
        ifaces = get_working_ifaces()
        for i, iface in enumerate(ifaces):
            print(f"  [{i}] {iface.name}")
    except Exception:
        for name in get_if_list():
            print(f"  {name}")
    print()


def run_sniffer(iface=None, bpf_filter="", count=0):
    """Start the packet sniffer."""
    if not SCAPY_AVAILABLE:
        print("ERROR: Scapy not installed. Run: pip install scapy")
        print("Also install Npcap from https://npcap.com (Windows)")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  REAL-WORLD PACKET SNIFFER  (Bonus Demo Module)")
    print("=" * 60)
    print(f"  Interface : {iface or 'All interfaces'}")
    print(f"  Filter    : {bpf_filter or 'All packets'}")
    print(f"  Run this as Administrator on Windows!")
    print("=" * 60)
    print(f"\n{'ID':>6}  {'Proto':12} {'Src IP':15}:{'SPort':<5}  {'Dst IP':15}:{'DPort':<5}  {'Flags':12} {'Len':>5}")
    print("-" * 100)

    # Start relay thread
    relay_thread = threading.Thread(target=relay_to_dashboard, daemon=True)
    relay_thread.start()

    try:
        sniff(
            iface=iface,
            filter=bpf_filter if bpf_filter else None,
            prn=packet_callback,
            count=count,
            store=False,
        )
    except PermissionError:
        print("\nERROR: Permission denied. Run as Administrator!")
    except KeyboardInterrupt:
        print(f"\n\nSniffer stopped. Captured {_packet_count} packets.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Real-World Packet Sniffer (Scapy)")
    parser.add_argument("--iface",  type=str, default=None,  help="Network interface name")
    parser.add_argument("--filter", type=str, default="",    help="BPF filter (e.g. 'tcp port 443')")
    parser.add_argument("--count",  type=int, default=0,     help="Stop after N packets (0=infinite)")
    parser.add_argument("--list",   action="store_true",     help="List available interfaces and exit")
    args = parser.parse_args()

    if args.list:
        list_interfaces()
    else:
        run_sniffer(iface=args.iface, bpf_filter=args.filter, count=args.count)
