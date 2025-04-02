import csv

def extract_top_ips():
    # 读取result.csv文件
    with open('result.csv', 'r', encoding='utf-8') as csvfile:
        # 跳过标题行
        next(csvfile)
        # 读取CSV内容
        reader = csv.reader(csvfile)
        # 获取前10个IP地址
        top_ips = [row[0] for row in reader][:10]
    
    # 将IP地址写入新文件
    with open('cf-ip.txt', 'w') as f:
        for ip in top_ips:
            f.write(f'{ip}\n')

if __name__ == '__main__':
    extract_top_ips()
    print('已成功提取前10个IP地址到cf-ip.txt文件')