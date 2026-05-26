"""
=======================================================================
LLM 客户端 - 多模态大模型集成核心模块
=======================================================================
支持 OpenAI GPT-4V、Claude Vision、通义千问 VL、DeepSeek-VL 等多模态模型
专为 GIS 空间分析场景设计
=======================================================================
"""
import base64
import io
import json
import os
import time
import traceback
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, BinaryIO, Callable, Dict, List, Optional, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# =======================================================================
# 枚举和配置
# =======================================================================

class LLMProvider(Enum):
    """支持的大模型提供商"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DASHSCOPE = "dashscope"      # 通义千问
    DEEPSEEK = "deepseek"
    SILICONFLOW = "siliconflow"  # SiliconFlow API (支持多种模型)
    ZHIPU = "zhipu"             # 智谱 GLM-4V
    LOCAL = "local"              # 本地模型 (如 LLaVA, Ollama)


class AnalysisType(Enum):
    """GIS 分析类型"""
    MAP_VISUALIZATION = "map_visualization"
    STATS_RESULT = "stats_result"
    POI_QUALITY = "poi_quality"
    ACCESSIBILITY = "accessibility"
    SPATIAL_AUTOCORRELATION = "spatial_autocorrelation"
    LISA_CLUSTER = "lisa_cluster"
    TIME_SERIES = "time_series"
    EQUITY_ANALYSIS = "equity_analysis"
    CODE_REVIEW = "code_review"
    CHART_GENERATION = "chart_generation"


@dataclass
class LLMConfig:
    """
    大模型配置类
    
    示例配置（用户需根据实际情况填写）：
    
    # OpenAI GPT-4V
    config = LLMConfig(
        provider=LLMProvider.OPENAI,
        api_key="sk-...",
        model="gpt-4o"
    )
    
    # 阿里通义千问 VL
    config = LLMConfig(
        provider=LLMProvider.DASHSCOPE,
        api_key="sk-...",
        model="qwen-vl-plus"
    )
    
    # SiliconFlow (中转 API)
    config = LLMConfig(
        provider=LLMProvider.SILICONFLOW,
        api_key="sk-...",
        base_url="https://api.siliconflow.cn/v1",
        model="Qwen/Qwen2-VL-72B-Instruct"
    )
    
    # 本地 Ollama
    config = LLMConfig(
        provider=LLMProvider.LOCAL,
        base_url="http://localhost:11434/v1",
        model="llava"
    )
    """
    provider: LLMProvider = LLMProvider.OPENAI
    api_key: str = ""
    model: str = "gpt-4o"
    base_url: str = "https://api.openai.com/v1"
    max_tokens: int = 4096
    temperature: float = 0.3
    timeout: int = 120
    max_retries: int = 3
    retry_delay: float = 2.0
    
    # 图像处理
    image_max_width: int = 1920
    image_quality: str = "auto"  # "low", "high", "auto"
    
    # 缓存
    cache_dir: str = ""
    enable_cache: bool = True
    
    def __post_init__(self):
        if self.cache_dir is None:
            self.cache_dir = ""
        if not self.cache_dir:
            # 默认缓存目录
            try:
                import os
                base = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究'
                self.cache_dir = os.path.join(base, '.llm_cache')
            except:
                self.cache_dir = '.llm_cache'
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d['provider'] = self.provider.value
        return d


@dataclass
class AnalysisResult:
    """分析结果"""
    request_id: str
    analysis_type: AnalysisType
    model_used: str
    content: str
    confidence: float = 0.0
    processing_time: float = 0.0
    tokens_used: int = 0
    image_tokens: int = 0
    cached: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def save_json(self, filepath: str):
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
    
    @property
    def success(self) -> bool:
        return self.error is None and bool(self.content)


# =======================================================================
# 图片处理工具
# =======================================================================

class ImageProcessor:
    """图像处理工具"""
    
    @staticmethod
    def fig_to_base64(fig: plt.Figure, fmt: str = 'png', dpi: int = 150) -> str:
        """将 matplotlib 图表转为 base64"""
        buf = io.BytesIO()
        fig.savefig(buf, format=fmt, dpi=dpi, bbox_inches='tight', 
                    facecolor='white', edgecolor='none')
        buf.seek(0)
        img_bytes = buf.getvalue()
        buf.close()
        plt.close(fig)
        return base64.b64encode(img_bytes).decode('utf-8')
    
    @staticmethod
    def file_to_base64(filepath: str) -> str:
        """将图片文件转为 base64"""
        with open(filepath, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    
    @staticmethod
    def resize_image_if_needed(img_bytes: bytes, max_width: int) -> bytes:
        """如果图片太大则缩小"""
        try:
            from PIL import Image
            import io as pil_io
            
            img = Image.open(pil_io.BytesIO(img_bytes))
            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.LANCZOS)
                out = pil_io.BytesIO()
                img.save(out, format=img.format or 'PNG')
                return out.getvalue()
            return img_bytes
        except ImportError:
            return img_bytes
    
    @staticmethod
    def html_to_base64_screenshot(html_path: str, width: int = 1920) -> Optional[str]:
        """将 HTML 文件截图转为 base64（需要 selenium）"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            import time
            
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument(f'--window-size={width},1080')
            
            driver = webdriver.Chrome(options=options)
            driver.get(f'file://{html_path}')
            time.sleep(2)
            
            png = driver.find_element('tag name', 'body').screenshot_as_png
            driver.quit()
            
            return base64.b64encode(png).decode('utf-8')
        except ImportError:
            return None


# =======================================================================
# 缓存管理
# =======================================================================

class CacheManager:
    """LLM 响应缓存"""
    
    def __init__(self, cache_dir: str, max_age_hours: int = 168):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_age = max_age_hours * 3600
    
    def _make_key(self, prompt: str, image_hashes: List[str]) -> str:
        """生成缓存 key"""
        import hashlib
        content = prompt + '|' + '|'.join(sorted(image_hashes))
        return hashlib.sha256(content.encode()).hexdigest()[:32]
    
    def get(self, prompt: str, image_hashes: List[str]) -> Optional[Dict]:
        """获取缓存"""
        key = self._make_key(prompt, image_hashes)
        cache_file = self.cache_dir / f'{key}.json'
        
        if not cache_file.exists():
            return None
        
        # 检查过期
        age = time.time() - cache_file.stat().st_mtime
        if age > self.max_age:
            cache_file.unlink()
            return None
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return None
    
    def set(self, prompt: str, image_hashes: List[str], data: Dict):
        """设置缓存"""
        key = self._make_key(prompt, image_hashes)
        cache_file = self.cache_dir / f'{key}.json'
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
        except:
            pass


# =======================================================================
# 抽象基类
# =======================================================================

class BaseLLMClient(ABC):
    """大模型客户端基类"""
    
    @abstractmethod
    def analyze_image(
        self,
        image_source: Union[str, bytes, plt.Figure],
        prompt: str,
        analysis_type: AnalysisType = AnalysisType.MAP_VISUALIZATION,
    ) -> AnalysisResult:
        """分析图片"""
        pass
    
    @abstractmethod
    def analyze_multiple_images(
        self,
        image_sources: List[Union[str, bytes, plt.Figure]],
        prompt: str,
        analysis_type: AnalysisType = AnalysisType.STATS_RESULT,
    ) -> AnalysisResult:
        """分析多张图片（对比分析）"""
        pass
    
    @abstractmethod
    def generate_text(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: Optional[int] = None,
    ) -> AnalysisResult:
        """纯文本生成"""
        pass
    
    def _prepare_image(self, image_source: Union[str, bytes, plt.Figure]) -> str:
        """准备图片为 base64 字符串"""
        if isinstance(image_source, plt.Figure):
            return ImageProcessor.fig_to_base64(image_source)
        elif isinstance(image_source, bytes):
            return base64.b64encode(image_source).decode('utf-8')
        elif isinstance(image_source, str):
            if os.path.exists(image_source):
                return ImageProcessor.file_to_base64(image_source)
            elif image_source.startswith('data:'):
                return image_source.split(',', 1)[1]
            else:
                return image_source
        else:
            raise ValueError(f"Unsupported image source type: {type(image_source)}")


# =======================================================================
# OpenAI GPT-4V / GPT-4o 客户端
# =======================================================================

class OpenAIClient(BaseLLMClient):
    """OpenAI 多模态客户端"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = None
        self._init_client()
    
    def _init_client(self):
        try:
            from openai import OpenAI
            self.client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout,
                max_retries=self.config.max_retries,
            )
        except ImportError:
            raise ImportError(
                "请安装 OpenAI SDK: pip install openai\n"
                "如果使用中转 API，请设置 base_url"
            )
    
    def analyze_image(
        self,
        image_source: Union[str, bytes, plt.Figure],
        prompt: str,
        analysis_type: AnalysisType = AnalysisType.MAP_VISUALIZATION,
    ) -> AnalysisResult:
        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        
        try:
            img_b64 = self._prepare_image(image_source)
            
            messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{img_b64}",
                            "detail": self.config.image_quality
                        }
                    }
                ]
            }]
            
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )
            
            content = response.choices[0].message.content
            usage = response.usage
            
            return AnalysisResult(
                request_id=request_id,
                analysis_type=analysis_type,
                model_used=f"openai/{self.config.model}",
                content=content or "",
                processing_time=time.time() - start_time,
                tokens_used=usage.total_tokens if usage else 0,
                image_tokens=usage.prompt_tokens - (usage.completion_tokens or 0) if usage else 0,
                metadata={"model": self.config.model}
            )
            
        except Exception as e:
            return AnalysisResult(
                request_id=request_id,
                analysis_type=analysis_type,
                model_used=f"openai/{self.config.model}",
                content="",
                processing_time=time.time() - start_time,
                error=f"{type(e).__name__}: {str(e)}"
            )
    
    def analyze_multiple_images(
        self,
        image_sources: List[Union[str, bytes, plt.Figure]],
        prompt: str,
        analysis_type: AnalysisType = AnalysisType.STATS_RESULT,
    ) -> AnalysisResult:
        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        
        try:
            content = [{"type": "text", "text": prompt}]
            
            for src in image_sources:
                img_b64 = self._prepare_image(src)
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{img_b64}",
                        "detail": self.config.image_quality
                    }
                })
            
            messages = [{"role": "user", "content": content}]
            
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )
            
            return AnalysisResult(
                request_id=request_id,
                analysis_type=analysis_type,
                model_used=f"openai/{self.config.model}",
                content=response.choices[0].message.content or "",
                processing_time=time.time() - start_time,
                metadata={"images_count": len(image_sources)}
            )
            
        except Exception as e:
            return AnalysisResult(
                request_id=request_id,
                analysis_type=analysis_type,
                model_used=f"openai/{self.config.model}",
                content="",
                processing_time=time.time() - start_time,
                error=str(e)
            )
    
    def generate_text(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: Optional[int] = None,
    ) -> AnalysisResult:
        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                max_tokens=max_tokens or self.config.max_tokens,
                temperature=self.config.temperature,
            )
            
            return AnalysisResult(
                request_id=request_id,
                analysis_type=AnalysisType.CODE_REVIEW,
                model_used=f"openai/{self.config.model}",
                content=response.choices[0].message.content or "",
                processing_time=time.time() - start_time,
            )
            
        except Exception as e:
            return AnalysisResult(
                request_id=request_id,
                analysis_type=AnalysisType.CODE_REVIEW,
                model_used=f"openai/{self.config.model}",
                content="",
                processing_time=time.time() - start_time,
                error=str(e)
            )


# =======================================================================
# 通义千问 VL 客户端
# =======================================================================

class DashScopeClient(BaseLLMClient):
    """阿里通义千问 VL 客户端"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = None
        self._init_client()
    
    def _init_client(self):
        try:
            import dashscope
            from dashscope import MultiModalConversation
            dashscope.api_key = self.config.api_key
            self._ds = dashscope
        except ImportError:
            raise ImportError("请安装 dashscope: pip install dashscope")
    
    def analyze_image(
        self,
        image_source: Union[str, bytes, plt.Figure],
        prompt: str,
        analysis_type: AnalysisType = AnalysisType.MAP_VISUALIZATION,
    ) -> AnalysisResult:
        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        
        try:
            img_b64 = self._prepare_image(image_source)
            
            messages = [{
                "role": "user",
                "content": [
                    {"text": prompt},
                    {"image": f"data:image/png;base64,{img_b64}"}
                ]
            }]
            
            from dashscope import MultiModalConversation
            response = MultiModalConversation.call(
                model=self.config.model,
                messages=messages,
            )
            
            if response.status_code == 200:
                content = response.output.choices[0].message.content
            else:
                content = ""
            
            return AnalysisResult(
                request_id=request_id,
                analysis_type=analysis_type,
                model_used=f"dashscope/{self.config.model}",
                content=content or "",
                processing_time=time.time() - start_time,
            )
            
        except Exception as e:
            return AnalysisResult(
                request_id=request_id,
                analysis_type=analysis_type,
                model_used=f"dashscope/{self.config.model}",
                content="",
                processing_time=time.time() - start_time,
                error=str(e)
            )
    
    def analyze_multiple_images(self, image_sources, prompt, analysis_type):
        return self._multi_image_error(analysis_type)
    
    def generate_text(self, prompt, system_prompt="", max_tokens=None):
        return self._text_error()
    
    def _multi_image_error(self, analysis_type):
        return AnalysisResult(
            request_id=str(uuid.uuid4())[:8],
            analysis_type=analysis_type,
            model_used="dashscope",
            content="",
            error="Multiple image analysis not yet supported for DashScope"
        )
    
    def _text_error(self):
        return AnalysisResult(
            request_id=str(uuid.uuid4())[:8],
            analysis_type=AnalysisType.CODE_REVIEW,
            model_used="dashscope",
            content="",
            error="Text-only generation not yet supported for DashScope"
        )


# =======================================================================
# SiliconFlow API 客户端 (支持多种模型)
# =======================================================================

class SiliconFlowClient(OpenAIClient):
    """
    SiliconFlow API 客户端
    SiliconFlow 是一个中转 API，支持多种模型：
    - Qwen/Qwen2-VL-72B-Instruct
    - Qwen/Qwen2.5-VL-72B-Instruct
    - deepseek-ai/deepseek-vl2
    - THUDM/glm-4v
    - 更多模型请参考 https://siliconflow.cn
    """
    
    def __init__(self, config: LLMConfig):
        config.provider = LLMProvider.SILICONFLOW
        config.base_url = config.base_url or "https://api.siliconflow.cn/v1"
        super().__init__(config)


# =======================================================================
# 本地模型客户端 (Ollama / LLaVA)
# =======================================================================

class LocalLLMClient(BaseLLMClient):
    """本地大模型客户端（Ollama）"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = None
        self._init_client()
    
    def _init_client(self):
        try:
            from openai import OpenAI
            self.client = OpenAI(
                api_key="ollama",  # Ollama 不需要真实 key
                base_url=self.config.base_url or "http://localhost:11434/v1",
            )
        except ImportError:
            raise ImportError("请安装 OpenAI SDK: pip install openai")
    
    def analyze_image(
        self,
        image_source: Union[str, bytes, plt.Figure],
        prompt: str,
        analysis_type: AnalysisType = AnalysisType.MAP_VISUALIZATION,
    ) -> AnalysisResult:
        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        
        try:
            img_b64 = self._prepare_image(image_source)
            
            messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_b64}"}
                    }
                ]
            }]
            
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )
            
            return AnalysisResult(
                request_id=request_id,
                analysis_type=analysis_type,
                model_used=f"local/{self.config.model}",
                content=response.choices[0].message.content or "",
                processing_time=time.time() - start_time,
            )
            
        except Exception as e:
            return AnalysisResult(
                request_id=request_id,
                analysis_type=analysis_type,
                model_used=f"local/{self.config.model}",
                content="",
                processing_time=time.time() - start_time,
                error=str(e)
            )
    
    def analyze_multiple_images(self, image_sources, prompt, analysis_type):
        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        
        try:
            content = [{"type": "text", "text": prompt}]
            for src in image_sources:
                img_b64 = self._prepare_image(src)
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{img_b64}"}
                })
            
            messages = [{"role": "user", "content": content}]
            
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )
            
            return AnalysisResult(
                request_id=request_id,
                analysis_type=analysis_type,
                model_used=f"local/{self.config.model}",
                content=response.choices[0].message.content or "",
                processing_time=time.time() - start_time,
            )
            
        except Exception as e:
            return AnalysisResult(
                request_id=request_id,
                analysis_type=analysis_type,
                model_used=f"local/{self.config.model}",
                content="",
                processing_time=time.time() - start_time,
                error=str(e)
            )
    
    def generate_text(self, prompt, system_prompt="", max_tokens=None):
        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                max_tokens=max_tokens or self.config.max_tokens,
                temperature=self.config.temperature,
            )
            
            return AnalysisResult(
                request_id=request_id,
                analysis_type=AnalysisType.CODE_REVIEW,
                model_used=f"local/{self.config.model}",
                content=response.choices[0].message.content or "",
                processing_time=time.time() - start_time,
            )
            
        except Exception as e:
            return AnalysisResult(
                request_id=request_id,
                analysis_type=AnalysisType.CODE_REVIEW,
                model_used=f"local/{self.config.model}",
                content="",
                processing_time=time.time() - start_time,
                error=str(e)
            )


# =======================================================================
# 统一客户端工厂
# =======================================================================

def create_llm_client(config: LLMConfig) -> BaseLLMClient:
    """创建 LLM 客户端"""
    provider_map = {
        LLMProvider.OPENAI: OpenAIClient,
        LLMProvider.SILICONFLOW: SiliconFlowClient,
        LLMProvider.LOCAL: LocalLLMClient,
        LLMProvider.DASHSCOPE: DashScopeClient,
    }
    
    client_class = provider_map.get(config.provider)
    if client_class is None:
        raise ValueError(f"不支持的提供商: {config.provider}")
    
    return client_class(config)


# =======================================================================
# 快捷函数
# =======================================================================

def quick_analyze(
    image_source: Union[str, plt.Figure],
    prompt: str,
    config: Optional[LLMConfig] = None,
    provider: LLMProvider = LLMProvider.SILICONFLOW,
    api_key: str = "",
    model: str = "Qwen/Qwen2-VL-72B-Instruct",
) -> AnalysisResult:
    """
    快速图片分析（一行代码）
    
    示例：
    >>> result = quick_analyze(
    ...     fig,  # matplotlib 图表
    ...     "描述这张 GIS 空间分布图的特征",
    ...     provider=LLMProvider.SILICONFLOW,
    ...     api_key="sk-your-key"
    ... )
    >>> print(result.content)
    """
    if config is None:
        config = LLMConfig(
            provider=provider,
            api_key=api_key,
            model=model,
        )
    
    client = create_llm_client(config)
    return client.analyze_image(image_source, prompt)
