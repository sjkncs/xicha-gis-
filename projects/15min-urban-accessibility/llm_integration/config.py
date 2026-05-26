"""
=======================================================================
LLM 配置文件
=======================================================================
支持多种大模型服务商的配置
=======================================================================
"""
import json
import os
import os.path
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional, Dict, Any


@dataclass
class LLMConfig:
    """
    大模型配置
    
    支持的提供商：
    - OPENAI: OpenAI GPT-4V / GPT-4o (官方 API)
    - ANTHROPIC: Anthropic Claude (官方 API)
    - DASHSCOPE: 阿里云通义千问 (dashscope)
    - SILICONFLOW: SiliconFlow (聚合 API, 支持多种模型)
    - DEEPSEEK: DeepSeek (官方 API)
    - LOCAL: 本地模型 (Ollama / LLaVA)
    """
    
    provider: str = "siliconflow"  # 默认使用 SiliconFlow (免费额度)
    api_key: str = ""
    model: str = "Qwen/Qwen2.5-VL-7B-Instruct"  # 多模态模型
    base_url: Optional[str] = "https://api.siliconflow.cn/v1"
    temperature: float = 0.3
    max_tokens: int = 2000
    timeout: int = 120  # 秒
    max_image_size: tuple = (1024, 1024)  # (width, height)
    cache_dir: Optional[Path] = None
    cache_ttl: int = 86400 * 7  # 缓存 7 天
    image_quality: int = 85  # JPEG 质量
    
    # 高级选项
    extra_headers: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        """后处理初始化"""
        # 处理 Path
        if self.cache_dir is None:
            self.cache_dir = Path(__file__).parent / '.cache'
        else:
            self.cache_dir = Path(self.cache_dir)
        
        # 确保缓存目录存在
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 兼容旧的字符串 provider
        if isinstance(self.provider, str):
            from .llm_client import LLMProvider
            try:
                self.provider = LLMProvider(self.provider.lower()).value
            except ValueError:
                self.provider = LLMProvider.SILICONFLOW.value
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于序列化）"""
        d = asdict(self)
        d['cache_dir'] = str(d['cache_dir'])
        d['max_image_size'] = list(d['max_image_size'])
        return d
    
    def save(self, path: Optional[str] = None):
        """保存配置到文件"""
        if path is None:
            path = Path(__file__).parent / 'config.json'
        else:
            path = Path(path)
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"✅ 配置已保存至: {path}")
    
    @classmethod
    def load(cls, path: Optional[str] = None) -> 'LLMConfig':
        """从文件加载配置"""
        if path is None:
            path = Path(__file__).parent / 'config.json'
        else:
            path = Path(path)
        
        if not path.exists():
            print(f"⚠ 配置文件不存在: {path}")
            print("将使用默认配置（SiliconFlow）")
            return cls()
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 处理 Path 和 tuple
        if 'cache_dir' in data:
            data['cache_dir'] = Path(data['cache_dir'])
        if 'max_image_size' in data:
            data['max_image_size'] = tuple(data['max_image_size'])
        
        return cls(**data)


# =======================================================================
# 预设配置
# =======================================================================

PRESETS = {
    # SiliconFlow（推荐，免费额度充足）
    "siliconflow": LLMConfig(
        provider="siliconflow",
        api_key="",  # 请填入您的 API Key
        model="Qwen/Qwen2.5-VL-7B-Instruct",
        base_url="https://api.siliconflow.cn/v1",
        temperature=0.3,
        max_tokens=2000,
    ),
    
    # 阿里云通义千问
    "dashscope": LLMConfig(
        provider="dashscope",
        api_key="",  # 请填入您的 API Key
        model="qwen-vl-plus",
        base_url="https://dashscope.aliyuncs.com/api/v1",
        temperature=0.3,
        max_tokens=2000,
    ),
    
    # OpenAI (需要 VPN)
    "openai": LLMConfig(
        provider="openai",
        api_key="",  # 请填入您的 API Key
        model="gpt-4o",
        base_url="https://api.openai.com/v1",
        temperature=0.3,
        max_tokens=2000,
    ),
    
    # DeepSeek
    "deepseek": LLMConfig(
        provider="deepseek",
        api_key="",  # 请填入您的 API Key
        model="deepseek-chat",
        base_url="https://api.deepseek.com/v1",
        temperature=0.3,
        max_tokens=2000,
    ),
    
    # 本地 Ollama
    "local": LLMConfig(
        provider="local",
        api_key="",  # 本地模型通常不需要 API Key
        model="llava:7b",  # 或其他已安装的模型
        base_url="http://localhost:11434/v1",
        temperature=0.3,
        max_tokens=2000,
    ),
}


def get_config_from_env() -> LLMConfig:
    """
    从环境变量读取配置（优先级最高）
    
    支持的环境变量：
    - OPENAI_API_KEY
    - DASHSCOPE_API_KEY
    - SILICONFLOW_API_KEY
    - DEEPSEEK_API_KEY
    - ANTHROPIC_API_KEY
    - LLM_PROVIDER (可选: openai, dashscope, siliconflow, deepseek, local)
    - LLM_MODEL (可选)
    """
    # 检查环境变量中的 API Key
    api_key = (
        os.environ.get('OPENAI_API_KEY') or
        os.environ.get('DASHSCOPE_API_KEY') or
        os.environ.get('SILICONFLOW_API_KEY') or
        os.environ.get('DEEPSEEK_API_KEY') or
        os.environ.get('ANTHROPIC_API_KEY')
    )
    
    if not api_key:
        # 如果没有环境变量，尝试加载配置文件
        config_path = Path(__file__).parent / 'config.json'
        if config_path.exists():
            return LLMConfig.load(config_path)
        else:
            print("⚠ 未找到 API Key 和配置文件，将使用 SiliconFlow 默认配置")
            return PRESETS['siliconflow']
    
    # 根据环境变量确定提供商
    provider_map = {
        'OPENAI_API_KEY': 'openai',
        'DASHSCOPE_API_KEY': 'dashscope',
        'SILICONFLOW_API_KEY': 'siliconflow',
        'DEEPSEEK_API_KEY': 'deepseek',
        'ANTHROPIC_API_KEY': 'anthropic',
    }
    
    # 找出是哪个环境变量
    env_var = None
    for var, prov in provider_map.items():
        if os.environ.get(var):
            env_var = var
            provider = prov
            break
    
    # 获取模型（如果有指定）
    model = os.environ.get('LLM_MODEL')
    custom_provider = os.environ.get('LLM_PROVIDER', '').lower()
    
    if custom_provider and custom_provider in PRESETS:
        preset = PRESETS[custom_provider]
        return LLMConfig(
            provider=preset.provider,
            api_key=api_key,
            model=model or preset.model,
            base_url=preset.base_url,
        )
    elif provider in PRESETS:
        preset = PRESETS[provider]
        return LLMConfig(
            provider=preset.provider,
            api_key=api_key,
            model=model or preset.model,
            base_url=preset.base_url,
        )
    else:
        return PRESETS['siliconflow']


def create_config_wizard() -> LLMConfig:
    """
    交互式配置向导（无需 API Key 的默认值）
    
    返回预设配置，用户可后续填入 API Key
    """
    print("=" * 50)
    print("LLM 配置向导")
    print("=" * 50)
    
    print("\n请选择大模型服务商:")
    print("  1. SiliconFlow (推荐 - 免费额度充足)")
    print("  2. 阿里云通义千问")
    print("  3. OpenAI GPT-4 (需要 VPN)")
    print("  4. DeepSeek")
    print("  5. 本地 Ollama")
    
    choice = input("\n请输入选项 (1-5) [默认 1]: ").strip() or "1"
    
    providers = {
        "1": "siliconflow",
        "2": "dashscope",
        "3": "openai",
        "4": "deepseek",
        "5": "local",
    }
    
    provider = providers.get(choice, "siliconflow")
    preset = PRESETS[provider]
    
    print(f"\n已选择: {preset.base_url}")
    print(f"默认模型: {preset.model}")
    print("\n如需修改 API Key，请编辑 config.json 或设置环境变量")
    
    return preset


# =======================================================================
# 快捷函数
# =======================================================================

def save_api_key(provider: str, api_key: str, save_to_file: bool = True):
    """
    保存 API Key
    
    Args:
        provider: 提供商名称
        api_key: API Key
        save_to_file: 是否保存到配置文件
    """
    # 写入环境变量（仅当前会话）
    env_vars = {
        "siliconflow": "SILICONFLOW_API_KEY",
        "dashscope": "DASHSCOPE_API_KEY",
        "openai": "OPENAI_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
    }
    
    if provider.lower() in env_vars:
        os.environ[env_vars[provider.lower()]] = api_key
        print(f"✅ 已设置环境变量: {env_vars[provider.lower()]}")
    
    if save_to_file:
        config = LLMConfig.load()
        config.api_key = api_key
        config.provider = provider
        config.save()
