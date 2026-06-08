#!/usr/bin/env python3
"""本地下载字体，然后上传到 GPU"""
import os, urllib.request, urllib.error, subprocess, sys

# 尝试多个镜像源下载字体
FONT_URLS = [
    ("https://github.com/notofonts/noto-cjk/releases/download/Sans2.004/07_NotoSansCJKsc-Regular.otf", "NotoSansCJK.otf"),
    ("https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf", "NotoSansCJK.otf"),
    ("https://raw.githubusercontent.com/googlefonts/noto-cjk/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf", "NotoSansCJK.otf"),
]
LOCAL_FONT = r"e:\xicha gis 智能定位\自选年份\NotoSansCJK.otf"

def download_with_progress(url, path):
    """带进度下载"""
    class ReportHook:
        def __init__(self):
            self.reported = 0
        def __call__(self, block_num, block_size, total_size):
            if total_size <= 0:
                return
            downloaded = block_num * block_size
            pct = min(100, downloaded * 100 // total_size)
            if pct >= self.reported + 10:
                print(f"  {pct}% ({downloaded/1024/1024:.1f}/{total_size/1024/1024:.1f} MB)")
                self.reported = pct

    print(f"下载: {url}")
    try:
        urllib.request.urlretrieve(url, path, reporthook=ReportHook())
        size = os.path.getsize(path)
        if size < 1_000_000:  # 小于 1MB 说明失败了
            print(f"  文件太小({size}bytes)，可能是GitHub限制，尝试其他源...")
            return False
        print(f"  完成: {size/1024/1024:.1f} MB")
        return True
    except Exception as e:
        print(f"  失败: {e}")
        return False

# 尝试下载
success = False
for url, _ in FONT_URLS:
    if os.path.exists(LOCAL_FONT) and os.path.getsize(LOCAL_FONT) > 5_000_000:
        print(f"字体已存在: {os.path.getsize(LOCAL_FONT)/1024/1024:.1f} MB")
        success = True
        break
    ok = download_with_progress(url, LOCAL_FONT)
    if ok:
        success = True
        break

if not success:
    # 备用：下载 WQY 字体（更小）
    print("尝试备用字体 WQY-microhei...")
    alt_url = "https://github.com/anthflame/font-mirror/raw/main/wqy-microhei.ttc"
    alt_path = LOCAL_FONT.replace(".otf", ".ttc")
    try:
        urllib.request.urlretrieve(alt_url, alt_path)
        if os.path.getsize(alt_path) > 1_000_000:
            print(f"备用字体下载成功: {os.path.getsize(alt_path)/1024/1024:.1f} MB")
            success = True
    except:
        pass

if not success:
    print("字体下载失败！继续使用其他方案...")
    sys.exit(1)

print(f"\n字体就绪: {LOCAL_FONT} ({os.path.getsize(LOCAL_FONT)/1024/1024:.1f} MB)")
