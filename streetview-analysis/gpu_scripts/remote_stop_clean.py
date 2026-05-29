#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stop remote seg_inference_offline processes and optionally clean outputs.

Usage:
  python remote_stop_clean.py --clean
  python remote_stop_clean.py  (stop only)

NOTE: requires Paramiko.
"""
import argparse
import paramiko
import time

HOST = "connect.bjb1.seetacloud.com"
PORT = 37625
USER = "root"
PWD = "roBbKv+ed3Vm"

CLEAN_CMDS = [
    "rm -f /root/gis_project/outputs/segmentation/checkpoint.json",
    "rm -f /root/gis_project/outputs/segmentation/seg_results.csv",
    "rm -f /root/gis_project/outputs/segmentation/viz/*.png 2>/dev/null || true",
]

STOP_CMDS = [
    "ps aux | grep seg_inference_offline | grep -v grep || true",
    "pkill -f seg_inference_offline.py || true",
    "pkill -f seg_inference_offline || true",
    "sleep 1",
    "ps aux | grep seg_inference_offline | grep -v grep || true",
]


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 20):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    return out, err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", action="store_true", help="Also remove checkpoint/csv/viz")
    args = ap.parse_args()

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PWD, timeout=10)

    print("=== Stop seg_inference_offline processes ===")
    for c in STOP_CMDS:
        out, err = run(ssh, c)
        if out.strip():
            print(out.rstrip())
        if err.strip():
            print(err.rstrip())

    if args.clean:
        print("\n=== Clean outputs ===")
        for c in CLEAN_CMDS:
            out, err = run(ssh, c)
            if out.strip():
                print(out.rstrip())
            if err.strip():
                print(err.rstrip())

        out, _ = run(ssh, "ls -l /root/gis_project/outputs/segmentation | sed -n '1,120p'", timeout=20)
        print("\n=== outputs/segmentation listing ===")
        print(out)

    ssh.close()


if __name__ == "__main__":
    main()
