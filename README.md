# Cloudflare IP 扫描与测试工具

## 项目概述

这是一个用于扫描和测试 Cloudflare CDN 网络 IP 的工具，可以帮助用户找到延迟最低、最适合自己网络环境的 Cloudflare IP 地址。该工具支持 IPv4 和 IPv6 地址的扫描与测试，并提供详细的数据分析结果。

## 功能特点

- 支持 IPv4 和 IPv6 地址扫描
- 自动从 Cloudflare CIDR 列表中随机生成 IP 进行测试
- 获取 Cloudflare 数据中心位置信息（城市、地区）
- 测量 IP 地址的网络延迟
- 详细测试选定 IP 的稳定性（最小延迟、最大延迟、平均延迟、丢包率）
- 结果排序与筛选，便于选择最优 IP
- 提供 Go 和 Python 两种实现版本

## 文件说明

- `cfdata.go`: Go 语言实现版本
- `cfdata.py`: Python 实现版本
- `get_best_cf_ips.py`: 优化版 Python 实现，专注于获取最佳 Cloudflare IP
- `cfdata-windows-amd64.exe`: Windows 平台预编译可执行文件
- `ip.csv`: IP 扫描结果，包含 IP 地址、数据中心代码、地区、城市和网络延迟
- `result.csv`: 详细测试结果，包含 IP 地址、最小延迟、最大延迟、平均延迟和丢包率
- `ips-v4.txt`: Cloudflare IPv4 CIDR 列表
- `ips-v6.txt`: Cloudflare IPv6 CIDR 列表
- `locations.json`: Cloudflare 数据中心位置信息
- `ip.txt`: 筛选后的优质 IP 列表（可用于其他程序）
- `cf-ip.txt`: 经过优化筛选的高质量 Cloudflare IP 列表

## 使用方法

### Go 版本

```bash
# 基本使用
go run cfdata.go

# 指定参数
go run cfdata.go -scan 100 -test 50 -port 443 -delay 300
```

### Python 版本

```bash
# 安装依赖
pip install requests

# 基本使用
python cfdata.py

# 指定参数
python cfdata.py --scan 100 --test 50 --port 443 --delay 300
```

### 预编译版本（Windows）

```bash
# 基本使用
cfdata-windows-amd64.exe

# 指定参数
cfdata-windows-amd64.exe -scan 100 -test 50 -port 443 -delay 300
```

## 参数说明

- `-scan`/`--scan`: 扫描阶段最大并发数，默认为 100
- `-test`/`--test`: 详细测试阶段最大并发数，默认为 50
- `-port`/`--port`: 详细测试使用的端口，默认为 443
- `-delay`/`--delay`: 延迟阈值（毫秒），用于筛选 IP，默认为 300

## 数据文件格式

### ip.csv

包含初步扫描的 Cloudflare IP 信息，按网络延迟排序：

| 字段 | 说明 |
| --- | --- |
| IP地址 | Cloudflare IP 地址 |
| 数据中心 | 数据中心代码（如 SJC、IAD、AMS 等） |
| 地区 | 所在地区（如 North America、Europe 等） |
| 城市 | 所在城市（如 San Jose、Ashburn、Amsterdam 等） |
| 网络延迟 | TCP 连接延迟（毫秒） |

### result.csv

包含详细测试结果，按平均延迟排序：

| 字段 | 说明 |
| --- | --- |
| IP地址 | Cloudflare IP 地址 |
| 最小延迟(ms) | 测试中观察到的最小延迟 |
| 最大延迟(ms) | 测试中观察到的最大延迟 |
| 平均延迟(ms) | 测试中的平均延迟 |
| 丢包率(%) | 测试中的丢包百分比 |

## 工作流程

1. 程序首先检查是否存在 `ip.csv` 文件，如果不存在或用户选择更新，则进入扫描阶段
2. 扫描阶段：
   - 从 Cloudflare CIDR 列表中随机生成 IP 地址
   - 并发测试这些 IP 的可用性和延迟
   - 获取数据中心位置信息
   - 将结果按延迟排序并保存到 `ip.csv`
3. 详细测试阶段：
   - 从 `ip.csv` 中选择延迟低于阈值的 IP
   - 对这些 IP 进行多次连接测试，计算最小/最大/平均延迟和丢包率
   - 将结果按平均延迟排序并保存到 `result.csv`
4. 生成 `ip.txt` 文件，包含筛选后的优质 IP 列表

## 注意事项

- 测试结果会因网络环境和时间而异
- 建议定期运行程序以获取最新的最优 IP
- 对于不同的应用场景，可能需要调整延迟阈值参数