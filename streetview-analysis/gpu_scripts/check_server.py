#!/usr/bin/env python3
"""Try to reconnect, report status."""
import socket, sys

HOST = "connect.bjb1.seetacloud.com"
PORT = 12996

try:
    sock = socket.create_connection((HOST, PORT), timeout=10)
    sock.close()
    print(f"Port {PORT} is OPEN")
except Exception as e:
    print(f"Port {PORT} is NOT reachable: {e}")
    print("\nThe AutoDL GPU instance appears to be stopped.")
    print("Please restart it from the AutoDL console at: https://www.autodl.com")
    print("Once restarted, I'll try reconnecting.")
