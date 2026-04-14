#!/usr/bin/env python3
"""
MAC Address Flash Script - MAC 地址烧录脚本

用于将自定义 MAC 地址烧录到 ESP32 设备的 eFuse 或 NVS 存储。

使用方式:
    python flash_mac.py --port /dev/cu.usbmodem001 --mac AA:BB:CC:DD:EE:FF

注意事项:
- eFuse 烧录是永久性的，请谨慎操作
- 推荐使用 NVS 方式，可多次修改
"""

import argparse
import subprocess
import sys
import os


def validate_mac(mac: str) -> str:
    """验证并规范化 MAC 地址"""
    cleaned = mac.upper().replace("-", "").replace(":", "")
    if len(cleaned) != 12:
        raise ValueError(f"Invalid MAC address: {mac}")
    
    for char in cleaned:
        if char not in "0123456789ABCDEF":
            raise ValueError(f"Invalid character in MAC: {char}")
    
    # 格式化为 AA:BB:CC:DD:EE:FF
    pairs = [cleaned[i:i+2] for i in range(0, 12, 2)]
    return ":".join(pairs)


def flash_mac_nvs(port: str, mac: str):
    """通过 NVS 分区烧录 MAC 地址（推荐，可修改）"""
    import json
    import csv
    import tempfile
    
    normalized_mac = validate_mac(mac)
    
    # 创建 NVS CSV 文件
    nvs_csv = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
    writer = csv.writer(nvs_csv)
    writer.writerow(['key', 'type', 'encoding', 'value'])
    writer.writerow(['device_config', 'namespace', '', ''])
    writer.writerow(['mac_address', 'data', 'string', normalized_mac])
    nvs_csv.close()
    
    print(f"[INFO] Created NVS CSV: {nvs_csv.name}")
    print(f"[INFO] MAC Address: {normalized_mac}")
    
    # 生成 NVS 分区二进制
    nvs_bin = tempfile.NamedTemporaryFile(suffix='.bin', delete=False)
    nvs_bin.close()
    
    try:
        # 使用 nvs_partition_gen.py 生成 NVS 分区
        # 这需要 ESP-IDF 或 esptool
        cmd = [
            sys.executable, "-m", "esptool",
            "--chip", "esp32s3",
            "--port", port,
            "write_flash",
            "0x9000", nvs_bin.name
        ]
        
        print(f"[INFO] Would run: {' '.join(cmd)}")
        print("\n[NOTE] NVS flashing requires ESP-IDF tools.")
        print("Alternative: Configure MAC via serial commands in firmware.")
        
    finally:
        os.unlink(nvs_csv.name)
        os.unlink(nvs_bin.name)


def read_mac_from_device(port: str) -> str:
    """从设备读取当前 MAC 地址"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "esptool", "--chip", "esp32s3", "--port", port, "read_mac"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        for line in result.stdout.split('\n'):
            if "MAC:" in line:
                mac = line.split("MAC:")[1].strip()
                return mac
        
        return None
    except Exception as e:
        print(f"[ERROR] Failed to read MAC: {e}")
        return None


def list_serial_ports():
    """列出可用串口"""
    import glob
    
    if sys.platform == 'darwin':
        ports = glob.glob('/dev/cu.*')
    elif sys.platform == 'linux':
        ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
    elif sys.platform == 'win32':
        ports = ['COM%d' % i for i in range(1, 20)]
    else:
        ports = []
    
    return ports


def main():
    parser = argparse.ArgumentParser(description='ESP32 MAC 地址烧录工具')
    parser.add_argument('--port', '-p', help='串口端口，如 /dev/cu.usbmodem001')
    parser.add_argument('--mac', '-m', help='要烧录的 MAC 地址，如 AA:BB:CC:DD:EE:FF')
    parser.add_argument('--read', '-r', action='store_true', help='读取设备当前 MAC 地址')
    parser.add_argument('--list', '-l', action='store_true', help='列出可用串口')
    
    args = parser.parse_args()
    
    if args.list:
        print("Available serial ports:")
        for port in list_serial_ports():
            print(f"  {port}")
        return
    
    if args.read:
        if not args.port:
            print("Error: --port is required for reading MAC")
            sys.exit(1)
        
        mac = read_mac_from_device(args.port)
        if mac:
            print(f"Device MAC: {mac}")
        else:
            print("Failed to read MAC address")
        return
    
    if args.mac:
        if not args.port:
            print("Error: --port is required for flashing MAC")
            sys.exit(1)
        
        try:
            normalized_mac = validate_mac(args.mac)
            print(f"[INFO] Preparing to flash MAC: {normalized_mac}")
            print(f"[INFO] Port: {args.port}")
            
            confirm = input("\nProceed with flashing? (yes/no): ")
            if confirm.lower() != 'yes':
                print("Aborted.")
                return
            
            flash_mac_nvs(args.port, args.mac)
            
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
