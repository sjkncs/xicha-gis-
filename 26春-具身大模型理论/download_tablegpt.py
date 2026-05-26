"""
TableGPT2-7B 模型下载脚本
使用 ModelScope（魔搭社区）作为下载源，国内访问速度最快
无需配置 HF_TOKEN，避免 HuggingFace 限速问题
"""

from modelscope import snapshot_download
import os

def main():
    print("=" * 60)
    print("开始从 ModelScope（魔搭社区）下载 TableGPT2-7B 模型")
    print("=" * 60)
    
    # 设置下载目录为当前工作目录下的 TableGPT2-7B 文件夹
    cache_dir = os.path.join(os.getcwd(), "TableGPT2-7B")
    
    print(f"下载目标路径：{cache_dir}")
    print("模型大小约 15.2GB，请耐心等待...")
    print()
    
    try:
        model_path = snapshot_download(
            model_id="tablegpt/TableGPT2-7B",
            cache_dir=cache_dir
        )
        
        print()
        print("=" * 60)
        print("✅ 模型下载完成！")
        print("=" * 60)
        print(f"模型路径：{model_path}")
        print()
        print("下一步操作：")
        print("1. 使用 llama.cpp 将模型转换为 GGUF 格式")
        print("2. 创建 Modelfile 文件")
        print("3. 导入到 Ollama: ollama create tablegpt2-7b -f Modelfile")
        print("=" * 60)
        
    except Exception as e:
        print()
        print("=" * 60)
        print("❌ 下载失败")
        print("=" * 60)
        print(f"错误信息：{e}")
        print()
        print("建议：")
        print("1. 检查网络连接")
        print("2. 确保磁盘有足够空间（至少 20GB）")
        print("3. 如持续失败，可尝试使用 hf-mirror 镜像")
        raise

if __name__ == "__main__":
    main()
