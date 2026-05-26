"""
=======================================================================
LLM 集成示例 - 15分钟城市研究案例
=======================================================================
展示如何在研究流程中集成多模态大模型辅助分析
=======================================================================
"""
import os
import sys
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # 非交互式后端
import pandas as pd
import numpy as np
import geopandas as gpd
import osmnx as ox
import networkx as nx
import folium
from pathlib import Path
from datetime import datetime

# 尝试导入 LLM 集成模块
try:
    from llm_integration import (
        LLMConfig, LLMProvider, create_llm_client,
        MapAnalyzer, StatsInterpreter, LISAMapAnalyzer,
        AccessibilityInterpreter, ChartAssistant, CodeReviewer,
        quick_analyze, build_prompt
    )
    LLM_AVAILABLE = True
except ImportError as e:
    LLM_AVAILABLE = False
    print(f"⚠ LLM 模块未完全安装，部分功能不可用: {e}")
    print("请确保安装了: pip install openai dashscope Pillow")


# =======================================================================
# 配置
# =======================================================================

def get_llm_config():
    """
    获取 LLM 配置
    
    优先顺序：
    1. 环境变量
    2. 配置文件 (config.json)
    3. 默认值（SiliconFlow 免费额度）
    """
    # 环境变量方式
    api_key = os.environ.get('DASHSCOPE_API_KEY') or \
              os.environ.get('OPENAI_API_KEY') or \
              os.environ.get('SILICONFLOW_API_KEY')
    
    # 如果没有环境变量，尝试从配置文件读取
    config_path = Path(__file__).parent / 'config.json'
    if not api_key and config_path.exists():
        import json
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            api_key = config_data.get('api_key')
    
    # SiliconFlow 默认配置（免费额度充足）
    return LLMConfig(
        provider=LLMProvider.SILICONFLOW,
        api_key=api_key or 'your-api-key-here',  # 占位符
        model='Qwen/Qwen2.5-VL-7B-Instruct',  # 多模态模型
        base_url='https://api.siliconflow.cn/v1',
        temperature=0.3,  # 低随机性，结果更稳定
        max_tokens=2000,
        cache_dir=Path(__file__).parent / '.cache',
        max_image_size=(1024, 1024),  # 限制图片大小以节省 tokens
    )


# =======================================================================
# 研究流程集成
# =======================================================================

class GISResearchAssistant:
    """
    GIS 研究助手 - 将 LLM 分析集成到研究流程的各个环节
    """
    
    def __init__(self, config: LLMConfig = None):
        self.config = config or get_llm_config()
        if LLM_AVAILABLE:
            self.llm_client = create_llm_client(self.config)
            self.map_analyzer = MapAnalyzer(self.llm_client)
            self.stats_interpreter = StatsInterpreter(self.llm_client)
            self.lisa_analyzer = LISAMapAnalyzer(self.llm_client)
            self.accessibility_interpreter = AccessibilityInterpreter(self.llm_client)
            self.chart_assistant = ChartAssistant(self.llm_client)
            self.code_reviewer = CodeReviewer(self.llm_client)
        else:
            self.llm_client = None
        self.results_log = []
    
    def log_result(self, task: str, result: str):
        """记录分析结果"""
        self.results_log.append({
            'timestamp': datetime.now().isoformat(),
            'task': task,
            'result': result[:200] + '...' if len(result) > 200 else result
        })
    
    # ===================================================================
    # 1. 数据准备阶段
    # ===================================================================
    
    def validate_osm_data(self, place_name: str) -> str:
        """
        验证 OSM 数据下载质量
        在下载数据后立即检查
        """
        if not LLM_AVAILABLE:
            return "[LLM未安装] 无法执行分析"
        
        print(f"正在验证 {place_name} 的 OSM 数据...")
        
        # 生成数据质量报告图
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        
        # 下载数据
        try:
            G = ox.graph_from_place(place_name, network_type='walk')
            gdf_nodes = ox.graph_to_gdfs(G, nodes=True, edges=False)
            gdf_edges = ox.graph_to_gdfs(G, nodes=False, edges=True)
            
            # 数据质量指标
            n_nodes = len(G.nodes)
            n_edges = len(G.edges)
            connectivity = nx.average_node_connectivity(G) if n_nodes > 1 else 0
            
            # 可视化
            ax = axes[0]
            gdf_nodes.plot(ax=ax, markersize=1, alpha=0.5)
            ax.set_title(f'道路网络: {place_name}\n{n_nodes}节点, {n_edges}边', fontsize=10)
            
            ax = axes[1]
            degree_values = [d for n, d in G.degree()]
            ax.hist(degree_values, bins=30, edgecolor='black', alpha=0.7)
            ax.set_xlabel('节点度数')
            ax.set_ylabel('频数')
            ax.set_title(f'度分布 | 平均度={np.mean(degree_values):.1f} | 平均连通性={connectivity:.2f}')
            
            plt.tight_layout()
            plt.savefig('osm_data_quality_check.png', dpi=150, bbox_inches='tight')
            plt.close()
            
            # LLM 分析
            result = self.code_reviewer.review_spatial_analysis_code(
                code_snippet=f"""
# OSMnx 数据下载
G = ox.graph_from_place('{place_name}', network_type='walk')
n_nodes = {n_nodes}
n_edges = {n_edges}
avg_connectivity = {connectivity:.4f}
avg_degree = {np.mean(degree_values):.2f}
""",
                analysis_goal=f"验证 {place_name} OSM 步行网络数据质量"
            )
            
            self.log_result('osm_data_validation', result.content)
            return result.content
            
        except Exception as e:
            return f"OSM 数据下载失败: {e}"
    
    # ===================================================================
    # 2. 可达性分析阶段
    # ===================================================================
    
    def analyze_accessibility_results(
        self,
        accessibility_map: str,
        metrics_summary: dict,
        study_area: str = "",
    ) -> str:
        """
        分析可达性计算结果
        输入：可达性热力图 + 统计摘要
        """
        if not LLM_AVAILABLE:
            return "[LLM未安装] 无法执行分析"
        
        print(f"正在分析 {study_area} 的可达性结果...")
        
        # 生成综合报告图
        fig, axes = plt.subplots(2, 2, figsize=(14, 12))
        
        metrics = list(metrics_summary.keys())
        values = list(metrics_summary.values())
        
        # 1. 可达性分布直方图
        ax = axes[0, 0]
        ax.hist(values, bins=30, edgecolor='black', alpha=0.7, color='steelblue')
        ax.axvline(np.mean(values), color='red', linestyle='--', label=f'均值={np.mean(values):.3f}')
        ax.axvline(np.median(values), color='orange', linestyle='--', label=f'中位数={np.median(values):.3f}')
        ax.set_xlabel('可达性指数')
        ax.set_ylabel('频数')
        ax.set_title('可达性指数分布')
        ax.legend()
        
        # 2. 统计摘要表
        ax = axes[0, 1]
        ax.axis('off')
        table_data = [
            ['指标', '值'],
            ['均值', f'{np.mean(values):.4f}'],
            ['中位数', f'{np.median(values):.4f}'],
            ['标准差', f'{np.std(values):.4f}'],
            ['最小值', f'{np.min(values):.4f}'],
            ['最大值', f'{np.max(values):.4f}'],
            ['Gini系数', f'{self._calc_gini(values):.4f}'],
        ]
        table = ax.table(cellText=table_data, loc='center', cellLoc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(11)
        table.scale(1.2, 1.8)
        ax.set_title('可达性统计摘要', pad=20)
        
        # 3. 分位数分布
        ax = axes[1, 0]
        quantiles = np.percentile(values, [10, 25, 50, 75, 90])
        ax.bar(['10%', '25%', '50%', '75%', '90%'], quantiles, color='teal', edgecolor='black')
        ax.set_ylabel('可达性指数')
        ax.set_title('可达性分位数分布')
        for i, v in enumerate(quantiles):
            ax.text(i, v + 0.01, f'{v:.3f}', ha='center', fontsize=9)
        
        # 4. 低可达性区域识别
        ax = axes[1, 1]
        low_threshold = np.percentile(values, 20)
        low_count = sum(1 for v in values if v < low_threshold)
        ax.pie(
            [low_count, len(values) - low_count],
            labels=[f'低可达性\n(<{low_threshold:.3f})', '其他'],
            autopct='%1.1f%%',
            colors=['coral', 'lightgreen'],
            explode=[0.1, 0]
        )
        ax.set_title(f'低可达性区域占比\n(低于20%分位数)')
        
        plt.tight_layout()
        plt.savefig('accessibility_analysis_report.png', dpi=150, bbox_inches='tight')
        plt.close()
        
        # LLM 分析
        result = self.accessibility_interpreter.interpret_accessibility_metrics(
            results_fig='accessibility_analysis_report.png',
            avg_accessibility=np.mean(values),
            median_accessibility=np.median(values),
            gini=self._calc_gini(values),
            vulnerable_groups={'低收入社区': np.percentile(values, 10), '老年人口': np.percentile(values, 15)},
            study_area=study_area,
        )
        
        self.log_result('accessibility_analysis', result.content)
        return result.content
    
    def _calc_gini(self, values):
        """计算 Gini 系数"""
        sorted_values = np.sort(values)
        n = len(sorted_values)
        cumsum = np.cumsum(sorted_values)
        return (2 * np.sum((np.arange(1, n + 1)) * sorted_values)) / (n * cumsum[-1]) - (n + 1) / n
    
    # ===================================================================
    # 3. 空间自相关分析阶段
    # ===================================================================
    
    def interpret_spatial_autocorrelation(
        self,
        morans_scatter_fig,
        lisa_cluster_fig,
        morans_i: float,
        p_value: float,
        study_area: str = "",
    ) -> str:
        """
        解读空间自相关分析
        输入：Moran 散点图 + LISA 聚类图
        """
        if not LLM_AVAILABLE:
            return "[LLM未安装] 无法执行分析"
        
        print(f"正在解读 {study_area} 的空间自相关结果...")
        
        # LLM 分析 Moran 散点图
        morans_result = self.stats_interpreter.interpret_morans_i(
            stat_fig=morans_scatter_fig,
            morans_i_value=morans_i,
            p_value=p_value,
            z_score=(morans_i - 0) / (1 / np.sqrt(len([morans_i]))),  # 简化计算
            variable_name="步行可达性",
            study_area=study_area,
        )
        
        # LLM 分析 LISA 聚类图
        lisa_result = self.lisa_analyzer.interpret_lisa_cluster_map(
            lisa_map_fig=lisa_cluster_fig,
            quadrant_stats=None,  # 可以传入实际统计数据
            study_area=study_area,
        )
        
        combined_result = f"""=== 空间自相关综合分析 ===

【全局空间自相关 (Moran's I)】
{morans_result.content}

【局部空间聚集 (LISA)】
{lisa_result.content}

【综合解读】
基于以上分析，{study_area} 的步行可达性呈现{"显著的空间聚集模式" if morans_i > 0 and p_value < 0.05 else "无显著空间自相关"}。
{"HH聚集区应优先考虑设施优化，LL聚集区需要重点关注空间剥夺问题。" if morans_i > 0 and p_value < 0.05 else ""}
"""
        
        self.log_result('spatial_autocorrelation', combined_result)
        return combined_result
    
    # ===================================================================
    # 4. 代码优化建议
    # ===================================================================
    
    def optimize_research_code(self, code: str, goal: str = "") -> str:
        """请求代码优化建议"""
        if not LLM_AVAILABLE:
            return "[LLM未安装] 无法执行分析"
        
        result = self.code_reviewer.suggest_optimization(
            slow_code_snippet=code,
            bottleneck_description=goal,
        )
        
        self.log_result('code_optimization', result.content)
        return result.content
    
    # ===================================================================
    # 5. 图表生成与描述
    # ===================================================================
    
    def generate_figure_description(
        self,
        figure_path: str,
        figure_type: str,
        context: str = "",
    ) -> str:
        """为图表生成学术描述"""
        if not LLM_AVAILABLE:
            return "[LLM未安装] 无法执行分析"
        
        result = self.chart_assistant.describe_figure_for_paper(
            figure=figure_path,
            figure_type=figure_type,
            context=context,
        )
        
        self.log_result('figure_description', result.content)
        return result.content
    
    # ===================================================================
    # 6. 批量分析
    # ===================================================================
    
    def batch_analyze_maps(
        self,
        map_paths: list,
        labels: list,
        analysis_type: str = "可达性对比",
    ) -> str:
        """批量分析多张地图"""
        if not LLM_AVAILABLE:
            return "[LLM未安装] 无法执行分析"
        
        result = self.map_analyzer.compare_multiple_maps(
            map_screenshots=map_paths,
            labels=labels,
            comparison_focus=analysis_type,
        )
        
        self.log_result(f'batch_map_{analysis_type}', result.content)
        return result.content
    
    # ===================================================================
    # 报告导出
    # ===================================================================
    
    def export_analysis_report(self, output_path: str = None):
        """导出分析报告"""
        if output_path is None:
            output_path = f'llm_analysis_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.md'
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# LLM 辅助分析报告\n\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")
            
            for i, item in enumerate(self.results_log, 1):
                f.write(f"## {i}. {item['task']}\n\n")
                f.write(f"时间: {item['timestamp']}\n\n")
                f.write(f"结果:\n\n{item['result']}\n\n")
                f.write("---\n\n")
        
        print(f"✅ 报告已保存至: {output_path}")
        return output_path


# =======================================================================
# 快速使用示例
# =======================================================================

def quick_demo():
    """快速演示"""
    print("=" * 60)
    print("15分钟城市研究 - LLM 辅助分析系统")
    print("=" * 60)
    
    # 1. 初始化
    config = get_llm_config()
    assistant = GISResearchAssistant(config)
    
    # 2. 检查 API 连接
    if LLM_AVAILABLE:
        test_result = quick_analyze(
            config=config,
            image_path=None,
            prompt="请回复'连接测试成功'以确认 API 正常工作",
            analysis_type="accessibility",
        )
        print(f"\n连接测试: {test_result.content[:50]}...")
    
    # 3. 使用示例
    print("\n可用分析功能:")
    print("  1. validate_osm_data()      - 验证 OSM 数据质量")
    print("  2. analyze_accessibility() - 分析可达性结果")
    print("  3. interpret_spatial...() - 解读空间自相关")
    print("  4. generate_figure...()    - 生成图表描述")
    print("  5. optimize_research...()   - 代码优化建议")
    print("\n详细使用请参考 README.md")
    
    return assistant


# =======================================================================
# 主函数
# =======================================================================

if __name__ == '__main__':
    assistant = quick_demo()
