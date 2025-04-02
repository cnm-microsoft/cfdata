#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import ipaddress
import json
import os
import random
import re
import signal
import socket
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple, Union

import requests

# ----------------------- 数据类型定义 -----------------------

class DataCenterInfo:
    def __init__(self, data_center: str, city: str, ip_count: int = 0, min_latency: int = 0):
        self.data_center = data_center
        self.city = city
        self.ip_count = ip_count
        self.min_latency = min_latency  # 毫秒

class ScanResult:
    def __init__(self, ip: str, data_center: str, region: str, city: str, latency_ms: int):
        self.ip = ip
        self.data_center = data_center
        self.region = region
        self.city = city
        self.latency_ms = latency_ms
        self.latency_str = f"{latency_ms} ms"

class TestResult:
    def __init__(self, ip: str, min_latency: int, max_latency: int, avg_latency: int, loss_rate: float):
        self.ip = ip
        self.min_latency = min_latency  # 毫秒
        self.max_latency = max_latency  # 毫秒
        self.avg_latency = avg_latency  # 毫秒
        self.loss_rate = loss_rate

class Location:
    def __init__(self, iata: str, lat: float, lon: float, cca2: str, region: str, city: str):
        self.iata = iata
        self.lat = lat
        self.lon = lon
        self.cca2 = cca2
        self.region = region
        self.city = city

# ----------------------- 工具函数 -----------------------

def read_line() -> str:
    """从标准输入读取一行数据（去除换行符）"""
    return input().strip()

def get_url_content(url: str) -> str:
    """根据指定URL下载内容"""
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.text

def get_file_content(filename: str) -> str:
    """从本地读取指定文件的内容"""
    with open(filename, 'r', encoding='utf-8') as f:
        return f.read()

def save_to_file(filename: str, content: str) -> None:
    """将内容保存到指定文件中"""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

def parse_ip_list(content: str) -> List[str]:
    """按行解析文本内容，返回非空行组成的字符串列表"""
    return [line.strip() for line in content.splitlines() if line.strip()]

def get_random_ipv4s(ip_list: List[str]) -> List[str]:
    """从类似 'xxx.xxx.xxx.xxx/24' 的CIDR中随机生成一个IPv4地址（只替换最后一段）"""
    random_ips = []
    for subnet in ip_list:
        if not subnet.endswith('/24'):
            continue
        base_ip = subnet[:-3]
        octets = base_ip.split('.')
        if len(octets) != 4:
            continue
        octets[3] = str(random.randint(0, 255))
        random_ip = '.'.join(octets)
        random_ips.append(random_ip)
    return random_ips

def get_random_ipv6s(ip_list: List[str]) -> List[str]:
    """从类似 'xxxx:xxxx:xxxx::/48' 的CIDR中随机生成一个IPv6地址（保留前三组）"""
    random_ips = []
    for subnet in ip_list:
        if not subnet.endswith('/48'):
            continue
        base_ip = subnet[:-3]
        sections = base_ip.split(':')
        if len(sections) < 3:
            continue
        sections = sections[:3]
        # 生成后五组随机数据（使总组数达到8组）
        for _ in range(5):
            sections.append(f"{random.randint(0, 65535):x}")
        random_ip = ':'.join(sections)
        random_ips.append(random_ip)
    return random_ips

def write_ips_to_file(filename: str, ips: List[str]) -> None:
    """将IP地址写入指定文本文件"""
    with open(filename, 'w', encoding='utf-8') as f:
        for ip in ips:
            f.write(f"{ip}\n")

# ----------------------- 功能模块 -----------------------

def run_ip_scan(ip_type: int, scan_max_threads: int) -> None:
    """根据用户选择的IPv4/IPv6，从指定URL获取CIDR列表、生成随机IP，然后扫描测试数据中心信息，最终写入 ip.csv"""
    filename = "ips-v6.txt" if ip_type == 6 else "ips-v4.txt"
    url = "https://www.baipiao.eu.org/cloudflare/ips-v6" if ip_type == 6 else "https://www.baipiao.eu.org/cloudflare/ips-v4"

    # 检查本地文件是否存在
    try:
        if not os.path.exists(filename):
            print(f"文件 {filename} 不存在，正在从 URL {url} 下载数据")
            content = get_url_content(url)
            save_to_file(filename, content)
        else:
            content = get_file_content(filename)
    except Exception as e:
        print(f"获取IP列表失败: {e}")
        return

    # 提取IP列表，并随机生成IP（每个子网取一个随机IP）
    ip_list = parse_ip_list(content)
    if ip_type == 6:
        ip_list = get_random_ipv6s(ip_list)
    else:
        ip_list = get_random_ipv4s(ip_list)

    # 下载或读取 locations.json 文件以获取数据中心位置信息
    locations = []
    try:
        if not os.path.exists("locations.json"):
            print("本地 locations.json 不存在，正在从 https://speed.cloudflare.com/locations 下载")
            response = requests.get("https://speed.cloudflare.com/locations", timeout=10)
            response.raise_for_status()
            locations_data = response.json()
            save_to_file("locations.json", json.dumps(locations_data))
            locations = [Location(**loc) for loc in locations_data]
        else:
            print("本地 locations.json 已存在，无需重新下载")
            with open("locations.json", 'r', encoding='utf-8') as f:
                locations_data = json.load(f)
                locations = [Location(
                    iata=loc.get('iata', ''),
                    lat=loc.get('lat', 0.0),
                    lon=loc.get('lon', 0.0),
                    cca2=loc.get('cca2', ''),
                    region=loc.get('region', ''),
                    city=loc.get('city', '')
                ) for loc in locations_data]
    except Exception as e:
        print(f"获取数据中心位置信息失败: {e}")
        return

    # 构造 location 映射，key 为数据中心代码
    location_map = {loc.iata: loc for loc in locations}

    # 并发测试每个IP，用于获取数据中心、城市和延迟信息
    results = []
    count = 0
    total = len(ip_list)
    lock = threading.Lock()

    def scan_ip(ip: str) -> Optional[ScanResult]:
        nonlocal count
        try:
            # 测试TCP连接延迟
            start_time = time.time()
            sock = socket.socket(socket.AF_INET6 if ip_type == 6 else socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            sock.connect((ip, 80))
            tcp_duration_ms = int((time.time() - start_time) * 1000)
            
            # 发送HTTP请求获取数据中心信息
            sock.send(b"GET /cdn-cgi/trace HTTP/1.1\r\nHost: " + ip.encode() + b"\r\nUser-Agent: Mozilla/5.0\r\nConnection: close\r\n\r\n")
            sock.settimeout(2)
            response = b""
            while True:
                data = sock.recv(4096)
                if not data:
                    break
                response += data
                if b"\r\n\r\n" in response:
                    break
            sock.close()
            
            response_text = response.decode('utf-8', errors='ignore')
            if "uag=Mozilla/5.0" in response_text:
                match = re.search(r'colo=([A-Z]+)', response_text)
                if match:
                    data_center = match.group(1)
                    loc = location_map.get(data_center)
                    if loc:
                        print(f"有效IP: {ip}, {loc.city}, 延迟: {tcp_duration_ms} ms")
                        return ScanResult(ip, data_center, loc.region, loc.city, tcp_duration_ms)
                    else:
                        print(f"有效IP: {ip}, 数据中心: {data_center}, 未知位置信息, 延迟: {tcp_duration_ms} ms")
                        return ScanResult(ip, data_center, "", "", tcp_duration_ms)
        except Exception:
            pass
        finally:
            with lock:
                count += 1
                percentage = count / total * 100
                print(f"扫描进度: {count}/{total} ({percentage:.2f}%)\r", end="")
                if count == total:
                    print("")
        return None

    with ThreadPoolExecutor(max_workers=scan_max_threads) as executor:
        futures = [executor.submit(scan_ip, ip) for ip in ip_list]
        for future in futures:
            result = future.result()
            if result:
                results.append(result)

    # 如果没有有效IP，直接退出程序
    if not results:
        print("未发现有效IP，程序退出。")
        sys.exit(1)

    # 按延迟排序
    results.sort(key=lambda x: x.latency_ms)

    # 将扫描结果写入 ip.csv
    try:
        with open("ip.csv", 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["IP地址", "数据中心", "地区", "城市", "网络延迟"])
            for res in results:
                writer.writerow([res.ip, res.data_center, res.region, res.city, res.latency_str])
        print("扫描完成，ip.csv生成成功。")
    except Exception as e:
        print(f"写入 ip.csv 失败: {e}")

def select_data_center_from_csv() -> Tuple[str, List[str]]:
    """读取 ip.csv，统计各数据中心信息供用户选择，并返回选定数据中心及对应IP列表"""
    try:
        with open("ip.csv", 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            records = list(reader)
    except Exception as e:
        print(f"无法打开或读取 ip.csv: {e}")
        return "", []

    # 统计数据中心信息
    data_centers = {}
    for i, record in enumerate(records):
        if i == 0:
            continue
        if len(record) < 5:
            continue
        dc = record[1]
        city = record[3]
        try:
            latency = int(record[4].split()[0])
        except (ValueError, IndexError):
            latency = 0
        
        if dc in data_centers:
            info = data_centers[dc]
            info.ip_count += 1
            if latency < info.min_latency or info.min_latency == 0:
                info.min_latency = latency
        else:
            data_centers[dc] = DataCenterInfo(dc, city, 1, latency)

    print("请选择数据中心：")
    for dc, info in data_centers.items():
        print(f"{info.data_center} ({info.city}) (IP数量: {info.ip_count}, 最低延迟: {info.min_latency} ms)")

    selected_dc = ""
    while True:
        print("请输入数据中心名称（直接回车提取所有）：", end="")
        input_dc = read_line()
        if not input_dc:
            selected_dc = ""
            break
        
        found = False
        for dc in data_centers:
            if dc.lower() == input_dc.lower():
                selected_dc = dc
                found = True
                break
        
        if not found:
            print("输入数据中心无效，请重新输入。")
            continue
        break

    # 根据选择提取IP列表
    ip_list = []
    if not selected_dc:
        print("提取所有数据中心的IP地址...")
        for i, record in enumerate(records):
            if i == 0:
                continue
            if len(record) >= 1:
                ip_list.append(record[0])
    else:
        print(f"提取数据中心 '{selected_dc}' 的IP地址...")
        for i, record in enumerate(records):
            if i == 0:
                continue
            if len(record) >= 2 and record[1] == selected_dc:
                ip_list.append(record[0])

    return selected_dc, ip_list

def run_detailed_test(ip_list: List[str], selected_dc: str, port: int, delay: int, test_threads: int) -> None:
    """对选中的IP列表进行详细测试（10次TCP连接测试指定端口），统计延迟和丢包率，结果写入CSV文件"""
    results = []
    count = 0
    total = len(ip_list)
    lock = threading.Lock()

    def test_ip(ip: str) -> Optional[TestResult]:
        nonlocal count
        try:
            success_count = 0
            total_latency = 0
            min_latency = float('inf')
            max_latency = 0

            # 进行10次测试
            for _ in range(10):
                try:
                    start_time = time.time()
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(delay / 1000)
                    sock.connect((ip, port))
                    latency_ms = int((time.time() - start_time) * 1000)
                    sock.close()
                    
                    if latency_ms > delay:
                        continue
                    
                    success_count += 1
                    total_latency += latency_ms
                    min_latency = min(min_latency, latency_ms)
                    max_latency = max(max_latency, latency_ms)
                except Exception:
                    continue

            if success_count > 0:
                avg_latency = total_latency // success_count
                loss_rate = (10 - success_count) / 10.0
                print(f"有效IP {ip} : 最小 {min_latency} ms, 最大 {max_latency} ms, 平均 {avg_latency} ms, 丢包 {loss_rate*100:.2f}%")
                return TestResult(ip, min_latency, max_latency, avg_latency, loss_rate)
            else:
                print(f"无效IP {ip}, 丢包率100%, 已丢弃")
        except Exception as e:
            print(f"测试IP {ip} 时出错: {e}")
        finally:
            with lock:
                count += 1
                perc = count / total * 100
                print(f"详细测试进度: {count}/{total} ({perc:.2f}%)\r", end="")
                if count == total:
                    print("")
        return None

    with ThreadPoolExecutor(max_workers=test_threads) as executor:
        futures = [executor.submit(test_ip, ip) for ip in ip_list]
        for future in futures:
            result = future.result()
            if result:
                results.append(result)

    # 如果没有成功测试的IP，不进行分析
    if not results:
        print("详细测试：未发现有效IP")
        return

    # 按丢包率和平均延迟排序
    results.sort(key=lambda x: (x.loss_rate, x.avg_latency))

    # 写入结果文件
    out_filename = f"{selected_dc}.csv" if selected_dc else "result.csv"
    try:
        with open(out_filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["IP地址", "最小延迟(ms)", "最大延迟(ms)", "平均延迟(ms)", "丢包率(%)"])
            for res in results:
                writer.writerow([
                    res.ip,
                    str(res.min_latency),
                    str(res.max_latency),
                    str(res.avg_latency),
                    str(int(res.loss_rate * 100))
                ])
        print(f"详细测试结束，结果已写入文件: {out_filename}")
    except Exception as e:
        print(f"写入结果文件时出现错误: {e}")
        return

    # 调用分析函数，对详细测试结果进行统计分析
    analyze_results(results, total)

def analyze_results(results: List[TestResult], total_ips: int) -> None:
    """
    根据传入的测试结果以及总测试 IP 数量（ip.txt中），将成功测试的结果按丢包率桶分组（每10%一桶），
    未成功测试的 IP 数量视为丢包率 100%
    """
    # 对成功测试结果分桶（0%,10%,...90%）
    groups = {}
    for res in results:
        # 按整数百分比取桶，如 5~9%归入0%，10~19%归入10%
        bucket = (int(res.loss_rate * 100) // 10) * 10
        if bucket not in groups:
            groups[bucket] = []
        groups[bucket].append(res)
    
    # 未成功测试的 IP 数量视为 100% 丢包
    unsuccessful_count = total_ips - len(results)

    # 输出横向柱状图（固定 0%,10%,...,100% 桶）
    print("------ 横向柱状图 （丢包率占比） ------")
    max_bar_width = 50
    for bucket in range(0, 101, 10):
        if bucket == 100:
            count = unsuccessful_count
            avg_lat_str = "N/A"
        else:
            count = len(groups.get(bucket, []))
            if count > 0:
                total_latency = sum(res.min_latency for res in groups[bucket])
                avg_lat = total_latency / count
                avg_lat_str = f"{avg_lat:.0f} ms"
            else:
                avg_lat_str = "N/A"
        
        proportion = count / total_ips * 100.0
        bar_length = int(proportion / 100 * max_bar_width)
        bar = "#" * bar_length
        print(f"丢包率 {bucket:3d}% |{bar:<50s}| ({proportion:.2f}%, {count}个, 平均延迟: {avg_lat_str})")

# ----------------------- 主程序入口 -----------------------

def main():
    # 定义命令行参数
    parser = argparse.ArgumentParser(description='CloudFlare IP 扫描与测试工具')
    parser.add_argument('--scan', type=int, default=100, help='扫描阶段最大并发数')
    parser.add_argument('--test', type=int, default=50, help='详细测试阶段最大并发数')
    parser.add_argument('--port', type=int, default=443, help='详细测试使用的端口')
    parser.add_argument('--delay', type=int, default=300, help='延迟阈值，单位毫秒')
    args = parser.parse_args()

    # 检查 ip.csv 是否存在
    update_choice = "n"
    if os.path.exists("ip.csv"):
        # 文件存在时提示用户是否更新
        while True:
            print("检测到 ip.csv 文件已存在，是否更新数据？(y/n, 默认n): ", end="")
            input_choice = read_line()
            if not input_choice:
                input_choice = "n"
            input_choice = input_choice.lower()
            if input_choice in ["y", "n"]:
                update_choice = input_choice
                break
            print("输入无效，请输入 y 或 n！")
    else:
        # 文件不存在，直接更新数据
        update_choice = "y"

    if update_choice == "y":
        # 用户选择更新数据，询问测试 IPv4 或 IPv6
        ip_type = 4
        while True:
            print("请选择测试IPv4还是IPv6 (输入4或6，直接回车默认4): ", end="")
            input_type = read_line()
            if not input_type:
                ip_type = 4
                break
            try:
                ip_type = int(input_type)
                if ip_type in [4, 6]:
                    break
                print("输入无效，请输入4或6！")
            except ValueError:
                print("输入无效，请输入4或6！")
        
        print(f"你选择的是: IPv{ip_type}")
        run_ip_scan(ip_type, args.scan)

    # 从 ip.csv 中读取数据中心信息，供用户选择
    selected_dc, ip_list = select_data_center_from_csv()
    if not ip_list:
        print("未找到IP地址，程序退出。")
        return

    # 将IP列表写入 ip.txt（便于查看）
    try:
        write_ips_to_file("ip.txt", ip_list)
        if not selected_dc:
            print("已将所有数据中心的IP地址写入 ip.txt")
        else:
            print(f"已将数据中心 '{selected_dc}' 的IP地址写入 ip.txt")
    except Exception as e:
        print(f"写入 ip.txt 文件失败: {e}")

    # 对选中的IP列表做详细延迟和丢包测试
    run_detailed_test(ip_list, selected_dc, args.port, args.delay, args.test)

    # 提示用户CTRL+C退出程序，防止在Windows下窗口立即关闭
    print("\n程序执行结束，请按 CTRL+C 退出程序。")
    try:
        signal.pause()  # 在Unix系统上等待信号
    except (AttributeError, KeyboardInterrupt):
        # Windows没有signal.pause()，使用简单的无限循环
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    # 设置随机数种子
    random.seed(time.time())
    main()