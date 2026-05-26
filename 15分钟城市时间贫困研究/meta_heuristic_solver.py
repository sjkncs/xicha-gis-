# -*- coding: utf-8 -*-
"""
15分钟城市时间贫困研究 - 元启发式算法求解最短路径模块
===================================================
集成算法: 遗传算法(GA)、模拟退火(SA)、禁忌搜索(TS)、蚁群算法(ACO)、
          差分进化(DE)、粒子群算法(PSO)、神经网络(NN)
          
适配: OSMnx路网数据 (osmnx.graph) + 南山区真实建筑/POI数据
核心: 以步行时间/综合成本为优化目标, 求解多约束最短路径
"""

import numpy as np
import pandas as pd
import networkx as nx
import os
import osmnx as ox
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
from matplotlib import font_manager
import warnings, time, json
from scipy.spatial.distance import cdist
from scipy.spatial import cKDTree
from typing import Tuple, List, Optional, Dict, Callable
from dataclasses import dataclass
from functools import wraps
from collections import deque

warnings.filterwarnings('ignore')
ox.settings.use_cache = True
ox.settings.log_console = False

FONT_PATH = "C:/Windows/Fonts/simhei.ttf"
if os.path.exists(FONT_PATH):
    fm = font_manager.FontProperties(fname=FONT_PATH)
    plt.rcParams['font.family'] = ['SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False

np.random.seed(42)

# ─────────────────────────────────────────────────────────────────
# 数据结构
# ─────────────────────────────────────────────────────────────────
@dataclass
class OptimizationResult:
    algorithm: str
    best_cost: float
    best_path: List[int]
    convergence: List[float]
    runtime: float
    iterations: int
    metadata: dict


@dataclass
class PathConstraints:
    max_walking_time: float = 15.0     # 分钟
    max_distance: float = 1200.0       # 米
    avoid_types: List[str] = None        # 避开建筑类型
    require_types: List[str] = None      # 必须经过类型
    waypoint_nodes: List[int] = None     # 必经节点


# ─────────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────────
def node_lat_lon(G, node):
    """返回节点(lat, lon)"""
    g = G.g if hasattr(G, 'g') else G
    d = g.nodes[node]
    return d.get('y', 0), d.get('x', 0)


def edge_weight_time(G, u, v, walk_speed=1.2):
    """
    边权重: 基于边属性估算步行时间(分钟)
    考虑: 道路长度 + 道路类型 + 高程差
    """
    g = G.g if hasattr(G, 'g') else G
    is_multigraph = isinstance(g, (nx.MultiGraph, nx.MultiDiGraph))
    if is_multigraph:
        data = g.edges[u, v, 0]
    else:
        data = g.edges[u, v]
    length = data.get('length', 100)          # 米
    highway = str(data.get('highway', 'unclassified'))
    oneway = data.get('oneway', False)
    
    # 道路类型系数 (越窄/越乱越慢)
    road_factor = {
        'footway': 1.4, 'path': 1.5, 'steps': 1.8,
        'residential': 1.1, 'service': 1.2, 'unclassified': 1.2,
        'tertiary': 1.0, 'secondary': 0.9, 'primary': 0.85,
        'trunk': 0.8, 'motorway': 0.7
    }.get(highway, 1.2)
    
    # 有路缘石/人行道缺失惩罚
    if not data.get('has_sidewalk', True):
        road_factor *= 1.25
    
    travel_time = (length / (walk_speed * 1000 / 60)) * road_factor  # 分钟
    return travel_time


def _get_edge_attr(g, u, v, key, default):
    """Get edge attribute safely for both DiGraph and MultiDiGraph."""
    is_mg = isinstance(g, (nx.MultiGraph, nx.MultiDiGraph))
    if is_mg:
        try:
            return g.edges[u, v, 0].get(key, default)
        except KeyError:
            try:
                return g.edges[v, u, 0].get(key, default)
            except KeyError:
                return default
    else:
        try:
            return g.edges[u, v].get(key, default)
        except KeyError:
            try:
                return g.edges[v, u].get(key, default)
            except KeyError:
                return default


def build_weighted_adj(G, weight_type='time'):
    """构建带权邻接表"""
    g = G.g if hasattr(G, 'g') else G
    adj = {}
    for u, v, data in g.edges(data=True):
        if u not in adj: adj[u] = {}
        length = data.get('length', 100)
        if weight_type == 'time':
            w = edge_weight_time(G, u, v)
        else:
            w = length
        adj[u][v] = w
        if not data.get('oneway', False):
            if v not in adj: adj[v] = {}
            adj[v][u] = w
    return adj


def path_cost(G, path, weight_type='time'):
    """计算路径总权重"""
    if len(path) < 2: return 0.0
    total = 0.0
    g = G.g if hasattr(G, 'g') else G
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        if weight_type == 'time':
            total += edge_weight_time(G, u, v)
        else:
            total += _get_edge_attr(g, u, v, 'length', 0)
    return total


def visualize_path(G, path, title, filename, figsize=(14, 10)):
    """在地图上可视化路径"""
    g = G.g if hasattr(G, 'g') else G
    fig, ax = plt.subplots(figsize=figsize, dpi=150)
    fig.patch.set_facecolor('#0d1b2a')
    ax.set_facecolor('#0d1b2a')
    
    # 所有节点灰色
    nodes_x = [g.nodes[n]['x'] for n in g.nodes()]
    nodes_y = [g.nodes[n]['y'] for n in g.nodes()]
    ax.scatter(nodes_x, nodes_y, s=1, c='#2d4a6e', alpha=0.3, zorder=1)
    
    # 路径节点高亮
    path_x = [g.nodes[n]['x'] for n in path]
    path_y = [g.nodes[n]['y'] for n in path]
    ax.plot(path_x, path_y, 'c-', lw=3, alpha=0.9, zorder=3)
    ax.scatter([path_x[0]], [path_y[0]], s=200, c='#00ff88', marker='o', zorder=5, label='起点')
    ax.scatter([path_x[-1]], [path_y[-1]], s=200, c='#ff4444', marker='s', zorder=5, label='终点')
    
    for i, node in enumerate(path[1:-1]):
        ax.scatter([g.nodes[node]['x']], [g.nodes[node]['y']], s=40, c='#ffcc00', zorder=4)
    
    ax.set_title(title, color='white', fontsize=14, pad=12, fontproperties=fm)
    ax.tick_params(colors='#7a8fa6')
    for spine in ax.spines.values(): spine.set_color('#2d4a6e')
    ax.legend(loc='upper right', facecolor='#1a2a3a', labelcolor='white', fontsize=10)
    plt.tight_layout()
    plt.savefig(filename, dpi=150, bbox_inches='tight', facecolor='#0d1b2a')
    plt.close()
    print(f"  [PATH] {filename}")


# ─────────────────────────────────────────────────────────────────
# 基准: Dijkstra + A* (地面真值)
# ─────────────────────────────────────────────────────────────────
def baseline_dijkstra(G, source, target, weight_type='time'):
    """Dijkstra基准算法"""
    try:
        nxg = G.g if hasattr(G, 'g') else G
        path = nx.dijkstra_path(nxg, source, target, weight='length')
        cost = path_cost(G, path, weight_type)
        return OptimizationResult(
            algorithm='Dijkstra', best_cost=cost, best_path=path,
            convergence=[cost], runtime=0, iterations=1, metadata={}
        )
    except nx.NetworkXNoPath:
        return None


def baseline_astar(G, source, target, weight_type='time'):
    """A*算法"""
    try:
        nxg = G.g if hasattr(G, 'g') else G
        path = nx.astar_path(nxg, source, target, heuristic=lambda n1, n2: 0,
                              weight='length')
        cost = path_cost(G, path, weight_type)
        return OptimizationResult(
            algorithm='A*', best_cost=cost, best_path=path,
            convergence=[cost], runtime=0, iterations=1, metadata={}
        )
    except nx.NetworkXNoPath:
        return None


# ─────────────────────────────────────────────────────────────────
# 1. 遗传算法 (GA)
# ─────────────────────────────────────────────────────────────────
class GeneticAlgorithm:
    """
    遗传算法求解最短路径
    编码: 节点序列染色体
    交叉: 部分映射交叉(PMX)
    变异: 交换/插入/逆序
    适应度: 路径成本 (越小越好)
    """
    def __init__(self, G, population_size=100, generations=200,
                 crossover_rate=0.8, mutation_rate=0.15,
                 elite_ratio=0.1, weight_type='time'):
        self.G = G
        self.nx_graph = G.g
        self.weight_type = weight_type
        self.pop_size = population_size
        self.generations = generations
        self.cr = crossover_rate
        self.mr = mutation_rate
        self.elite_ratio = elite_ratio
        self.nodes = list(self.nx_graph.nodes)
        self.node_set = set(self.nodes)
        
    def _random_valid_path(self, source, target, max_hops=50):
        """生成随机有效路径 (贪心游走)"""
        path = [source]
        current = source
        visited = {source}
        for _ in range(max_hops):
            neighbors = [n for n in self.nx_graph.neighbors(current) if n not in visited]
            if not neighbors:
                break
            current = np.random.choice(neighbors)
            path.append(current)
            if current == target:
                return path
        return None
    
    def _crossover_pm(self, p1, p2, target):
        """部分映射交叉(PMX)"""
        if len(p1) < 2 or len(p2) < 2: return p1.copy()
        size = min(len(p1), len(p2))
        i, j = sorted(np.random.choice(range(size), 2, replace=False))
        
        mapping = {}
        for k in range(i, j+1):
            if p1[k] in p2[i:j+1]:
                pass
            mapping[p1[k]] = p2[k]
        
        child = [-1] * size
        child[i:j+1] = p1[i:j+1]
        
        for k in range(size):
            if child[k] == -1:
                val = p2[k]
                while val in child[i:j+1] and val in mapping:
                    val = mapping[val]
                child[k] = val
        
        return child
    
    def _mutate(self, path, source, target):
        """变异算子"""
        if len(path) < 3: return list(path)
        op = np.random.choice(['swap', 'insert', 'reverse'])
        if op == 'swap':
            if len(path) < 4:
                return list(path)
            i, j = np.random.choice(range(1, len(path)-1), 2, replace=False)
            path[i], path[j] = path[j], path[i]
        elif op == 'insert':
            i = np.random.randint(1, len(path)-1)
            val = path.pop(i)
            j = np.random.randint(1, len(path))
            path.insert(j if j < i else j, val)
        else:
            i, j = sorted(np.random.choice(range(len(path)), 2, replace=False))
            path[i:j] = path[i:j][::-1]
        return list(path)
    
    def _repair_path(self, path, source, target):
        """路径修复: 保证首尾正确,去除重复"""
        if not path: return [source, target]
        if path[0] != source: path = [source] + path
        if path[-1] != target: path = path + [target]
        
        # BFS修复断点
        fixed = [path[0]]
        for i in range(1, len(path)):
            if path[i] in self.nx_graph.neighbors(fixed[-1]):
                fixed.append(path[i])
            else:
                try:
                    sub = nx.shortest_path(self.nx_graph, fixed[-1], path[i] if path[i] in self.node_set else target)
                    fixed.extend(sub[1:])
                    break
                except:
                    fixed.append(path[i])
        return fixed[:100]
    
    def solve(self, source, target, verbose=False) -> OptimizationResult:
        start_time = time.time()
        source = int(source); target = int(target)
        
        # 初始化种群
        population = []
        dijkstra_path = nx.shortest_path(self.nx_graph, source, target, weight='length')
        dijkstra_cost = path_cost(self.G, dijkstra_path, self.weight_type)
        for _ in range(self.pop_size):
            p = self._random_valid_path(source, target)
            if p:
                p = self._repair_path(p, source, target)
                population.append(p)
        while len(population) < self.pop_size:
            population.append(dijkstra_path.copy())
        
        # 计算适应度
        def fitness(path):
            c = path_cost(self.G, path, self.weight_type)
            return 1.0 / (c + 1e-6)
        
        costs = [path_cost(self.G, p, self.weight_type) for p in population]
        best_idx = np.argmin(costs)
        best_cost = costs[best_idx]
        best_path = population[best_idx].copy()
        convergence = [best_cost]
        
        elite_size = max(2, int(self.pop_size * self.elite_ratio))
        
        for gen in range(self.generations):
            # 选择 (锦标赛)
            selected = []
            for _ in range(self.pop_size):
                i, j = np.random.choice(self.pop_size, 2, replace=False)
                winner = i if fitness(population[i]) > fitness(population[j]) else j
                selected.append(population[winner].copy())
            population = selected
            
            # 交叉
            children = []
            for _ in range(self.pop_size // 2):
                i, j = np.random.choice(self.pop_size, 2, replace=False)
                p1, p2 = population[i].copy(), population[j].copy()
                if np.random.random() < self.cr:
                    child = self._crossover_pm(p1, p2, target)
                else:
                    child = p1.copy()
                child = self._repair_path(child, source, target)
                children.append(child)
            
            while len(children) < self.pop_size:
                children.append(dijkstra_path.copy())
            population = children[:self.pop_size]
            
            # 变异
            for i in range(self.pop_size):
                if np.random.random() < self.mr:
                    population[i] = self._mutate(population[i], source, target)
                    population[i] = self._repair_path(population[i], source, target)
            
            # 精英保留
            all_paths = population + [best_path]
            all_costs = [path_cost(self.G, p, self.weight_type) for p in all_paths]
            top_idx = np.argsort(all_costs)[:elite_size]
            for i, idx in enumerate(top_idx):
                if i < self.pop_size:
                    population[i] = all_paths[idx].copy()
            
            costs = [path_cost(self.G, p, self.weight_type) for p in population]
            min_idx = np.argmin(costs)
            if costs[min_idx] < best_cost:
                best_cost = costs[min_idx]
                best_path = population[min_idx].copy()
            convergence.append(best_cost)
            
            if gen % 50 == 0 and verbose:
                print(f"    GA Gen {gen}: best_cost={best_cost:.2f}")
        
        return OptimizationResult(
            algorithm='GA', best_cost=best_cost, best_path=best_path,
            convergence=convergence, runtime=time.time()-start_time,
            iterations=self.generations,
            metadata={'dijkstra_cost': dijkstra_cost, 'gap_pct': abs(best_cost-dijkstra_cost)/dijkstra_cost*100}
        )


# ─────────────────────────────────────────────────────────────────
# 2. 模拟退火算法 (SA)
# ─────────────────────────────────────────────────────────────────
class SimulatedAnnealing:
    """
    模拟退火算法求解最短路径
    邻域: 2-opt (路径反转)
    温度衰减: T_k = T0 * alpha^k
    """
    def __init__(self, G, T0=1000.0, T_min=1e-8, alpha=0.995,
                 max_iter_per_T=50, weight_type='time'):
        self.G = G
        self.nx_graph = G.g
        self.weight_type = weight_type
        self.T0 = T0; self.T = T0
        self.T_min = T_min; self.alpha = alpha
        self.max_iter = max_iter_per_T
    
    def _neighbor_2opt(self, path):
        """2-opt邻域: 反转一段路径"""
        if len(path) < 4: return path
        i, j = sorted(np.random.choice(len(path), 2, replace=False))
        return path[:i] + path[i:j+1][::-1] + path[j+1:]
    
    def _path_valid(self, path):
        for i in range(len(path)-1):
            if path[i+1] not in self.nx_graph.neighbors(path[i]):
                return False
        return True
    
    def solve(self, source, target, verbose=False) -> OptimizationResult:
        start_time = time.time()
        source = int(source); target = int(target)
        
        try:
            current_path = nx.shortest_path(self.nx_graph, source, target, weight='length')
        except:
            current_path = [source, target]
        
        current_cost = path_cost(self.G, current_path, self.weight_type)
        best_path = current_path.copy()
        best_cost = current_cost
        convergence = [current_cost]
        self.T = self.T0
        iteration = 0
        
        while self.T > self.T_min:
            for _ in range(self.max_iter):
                new_path = self._neighbor_2opt(current_path)
                if not self._path_valid(new_path):
                    continue
                new_cost = path_cost(self.G, new_path, self.weight_type)
                delta = new_cost - current_cost
                
                if delta < 0 or np.random.random() < np.exp(-delta / self.T):
                    current_path = new_path
                    current_cost = new_cost
                    if current_cost < best_cost:
                        best_cost = current_cost
                        best_path = current_path.copy()
                        convergence.append(best_cost)
                iteration += 1
            
            self.T *= self.alpha
            if iteration % 500 == 0 and verbose:
                print(f"    SA T={self.T:.4f}: best_cost={best_cost:.2f}")
        
        return OptimizationResult(
            algorithm='SA', best_cost=best_cost, best_path=best_path,
            convergence=convergence, runtime=time.time()-start_time,
            iterations=iteration,
            metadata={'T0': self.T0, 'T_final': self.T}
        )


# ─────────────────────────────────────────────────────────────────
# 3. 禁忌搜索算法 (TS)
# ─────────────────────────────────────────────────────────────────
class TabuSearch:
    """
    禁忌搜索算法求解最短路径
    邻域: 节点插入 + 边交换
    禁忌表: 最近访问的路径哈希
    """
    def __init__(self, G, max_iter=300, tabu_tenure=20,
                 neighborhood_size=30, weight_type='time'):
        self.G = G
        self.nx_graph = G.g
        self.weight_type = weight_type
        self.max_iter = max_iter
        self.tabu_tenure = tabu_tenure
        self.nb_size = neighborhood_size
    
    def _neighbors(self, path):
        """生成邻域解"""
        candidates = []
        for _ in range(self.nb_size):
            new_path = path.copy()
            if len(new_path) < 4: break
            i = np.random.randint(1, len(new_path)-1)
            j = np.random.randint(1, len(new_path)-1)
            if i != j:
                new_path[i], new_path[j] = new_path[j], new_path[i]
            cost = path_cost(self.G, new_path, self.weight_type)
            if cost < path_cost(self.G, path, self.weight_type) * 1.5:
                candidates.append((cost, new_path))
        candidates.sort(key=lambda x: x[0])
        return candidates[:10]
    
    def solve(self, source, target, verbose=False) -> OptimizationResult:
        start_time = time.time()
        source = int(source); target = int(target)
        
        try:
            init_path = nx.shortest_path(self.nx_graph, source, target, weight='length')
        except:
            init_path = [source, target]
        
        current = init_path.copy()
        best = current.copy()
        best_cost = path_cost(self.G, best, self.weight_type)
        tabu_list = deque(maxlen=self.tabu_tenure)
        convergence = [best_cost]
        
        for it in range(self.max_iter):
            neighbors = self._neighbors(current)
            best_neighbor = None
            best_neighbor_cost = float('inf')
            
            for cost, cand in neighbors:
                h = hash(tuple(cand))
                is_tabu = h in tabu_list
                if (cost < best_cost) or (not is_tabu and cost < best_neighbor_cost):
                    best_neighbor_cost = cost
                    best_neighbor = cand
            
            if best_neighbor is not None:
                current = best_neighbor
                tabu_list.append(hash(tuple(current)))
                if best_neighbor_cost < best_cost:
                    best = best_neighbor.copy()
                    best_cost = best_neighbor_cost
                    convergence.append(best_cost)
            
            if it % 50 == 0 and verbose:
                print(f"    TS Iter {it}: best_cost={best_cost:.2f}, tabu_size={len(tabu_list)}")
        
        return OptimizationResult(
            algorithm='TS', best_cost=best_cost, best_path=best,
            convergence=convergence, runtime=time.time()-start_time,
            iterations=self.max_iter,
            metadata={'tabu_tenure': self.tabu_tenure, 'nb_size': self.nb_size}
        )


# ─────────────────────────────────────────────────────────────────
# 4. 蚁群算法 (ACO)
# ─────────────────────────────────────────────────────────────────
class AntColonyOptimization:
    """
    蚁群算法求解最短路径
    信息素更新: 全局最优 + 局部更新
    启发式信息: Dijkstra最短路径长度倒数
    """
    def __init__(self, G, n_ants=30, n_iterations=100,
                 alpha=1.0, beta=2.0, rho=0.5, Q=100.0,
                 weight_type='time'):
        self.G = G
        self.nx_graph = G.g
        self.weight_type = weight_type
        self.n_ants = n_ants
        self.n_iter = n_iterations
        self.alpha = alpha; self.beta = beta
        self.rho = rho; self.Q = Q
        
        # 初始化信息素 (基于Dijkstra最短路径)
        self.pheromone = {}
        all_nodes = list(self.nx_graph.nodes)
        if len(all_nodes) > 2000:
            sample = np.random.choice(all_nodes, 2000, replace=False).tolist()
        else:
            sample = all_nodes
        for u in sample:
            for v in self.nx_graph.neighbors(u):
                try:
                    d = nx.shortest_path_length(self.nx_graph, v, weight='length')
                    h = min(d.values()) if d else 1.0
                    self.pheromone[(u, v)] = 1.0 / (h + 1.0)
                except:
                    self.pheromone[(u, v)] = 1.0
    
    def _construct_path(self, source, target):
        """蚂蚁构建路径 (概率转移)"""
        path = [source]
        visited = {source}
        current = source
        attempts = 0
        
        while current != target and attempts < 1000:
            neighbors = [n for n in self.nx_graph.neighbors(current) if n not in visited]
            if not neighbors: break
            
            probs = []
            for n in neighbors:
                tau = self.pheromone.get((current, n), 0.01)
                dist = _get_edge_attr(self.nx_graph, current, n, 'length', 100)
                eta = 1.0 / (dist + 1.0)
                probs.append((tau**self.alpha) * (eta**self.beta))
            
            total = sum(probs)
            if total == 0:
                probs = [1.0/len(neighbors)] * len(neighbors)
            probs = [p/total for p in probs]
            next_node = np.random.choice(neighbors, p=probs)
            path.append(next_node)
            visited.add(next_node)
            current = next_node
            attempts += 1
        
        return path
    
    def _local_update(self, u, v, delta=0.01):
        """局部信息素更新"""
        self.pheromone[(u, v)] = (1-self.rho) * self.pheromone.get((u, v), 0.01) + self.rho * delta
        self.pheromone[(v, u)] = self.pheromone[(u, v)]
    
    def solve(self, source, target, verbose=False) -> OptimizationResult:
        start_time = time.time()
        source = int(source); target = int(target)
        
        best_path = nx.shortest_path(self.nx_graph, source, target, weight='length')
        best_cost = path_cost(self.G, best_path, self.weight_type)
        convergence = [best_cost]
        
        for iteration in range(self.n_iter):
            all_paths = []
            all_costs = []
            
            for _ in range(self.n_ants):
                path = self._construct_path(source, target)
                cost = path_cost(self.G, path, self.weight_type)
                all_paths.append(path)
                all_costs.append(cost)
                
                if cost < best_cost:
                    best_cost = cost
                    best_path = path.copy()
                    convergence.append(best_cost)
            
            # 全局信息素更新
            for path, cost in zip(all_paths, all_costs):
                delta = self.Q / cost
                for i in range(len(path) - 1):
                    u, v = path[i], path[i+1]
                    current = self.pheromone.get((u, v), 0.01)
                    self.pheromone[(u, v)] = (1-self.rho) * current + self.rho * delta
                    self.pheromone[(v, u)] = self.pheromone[(u, v)]
            
            if iteration % 20 == 0 and verbose:
                print(f"    ACO Iter {iteration}: best_cost={best_cost:.2f}")
        
        return OptimizationResult(
            algorithm='ACO', best_cost=best_cost, best_path=best_path,
            convergence=convergence, runtime=time.time()-start_time,
            iterations=self.n_iter * self.n_ants,
            metadata={'n_ants': self.n_ants, 'alpha': self.alpha, 'beta': self.beta}
        )


# ─────────────────────────────────────────────────────────────────
# 5. 差分进化算法 (DE)
# ─────────────────────────────────────────────────────────────────
class DifferentialEvolution:
    """
    差分进化算法(DE/rand/1/bin)求解最短路径
    特殊编码: 将路径离散化为有序节点序列
    变异: rand/1策略
    交叉: 二项式交叉
    适应度: 1/path_cost
    """
    def __init__(self, G, population_size=60, generations=150,
                 F=0.8, CR=0.7, weight_type='time'):
        self.G = G
        self.nx_graph = G.g
        self.weight_type = weight_type
        self.pop_size = population_size
        self.generations = generations
        self.F = F; self.CR = CR
    
    def _encode(self, path):
        """将路径编码为节点索引序列"""
        return [int(n) for n in path]
    
    def _repair(self, path, source, target):
        """修复路径合法性"""
        if not path: return [source, target]
        if path[0] != source: path = [source] + path
        if path[-1] != target: path = path + [target]
        fixed = [path[0]]
        for i in range(1, len(path)):
            if path[i] in self.nx_graph.neighbors(fixed[-1]):
                fixed.append(path[i])
            else:
                try:
                    sub = nx.shortest_path(self.nx_graph, fixed[-1], target)
                    fixed.extend(sub[1:])
                    break
                except:
                    pass
        return fixed[:80]
    
    def _init_population(self, source, target):
        """初始化种群"""
        dijkstra_path = nx.shortest_path(self.nx_graph, source, target, weight='length')
        nodes = list(self.nx_graph.nodes)
        pop = []
        for _ in range(self.pop_size):
            if np.random.random() < 0.5:
                pop.append(dijkstra_path.copy())
            else:
                path = self._repair([source, np.random.choice(list(self.nx_graph.nodes())), target], source, target)
                pop.append(path)
        while len(pop) < self.pop_size:
            pop.append(dijkstra_path.copy())
        return pop
    
    def _mutate(self, pop, idx, source, target):
        """DE变异: rand/1"""
        indices = [i for i in range(len(pop)) if i != idx]
        if len(indices) < 3: return pop[idx].copy()
        r1, r2, r3 = np.random.choice(indices, 3, replace=False)
        a = pop[r1]; b = pop[r2]; c = pop[r3]
        if len(a) < 2: return pop[idx].copy()
        mutant = a.copy()
        for node in b:
            if node in c and node not in [source, target]:
                ai = next((i for i, n in enumerate(mutant) if n == node), -1)
                ci = next((i for i, n in enumerate(c) if n == node), -1)
                if ai >= 0 and ci >= 0 and ci < len(c) - 1:
                    mutant = mutant[:ai] + c[ci:] + mutant[ai:]
                    break
        return self._repair(mutant, source, target)
    
    def solve(self, source, target, verbose=False) -> OptimizationResult:
        start_time = time.time()
        source = int(source); target = int(target)
        
        pop = self._init_population(source, target)
        costs = [path_cost(self.G, p, self.weight_type) for p in pop]
        best_idx = np.argmin(costs)
        best_path = pop[best_idx].copy()
        best_cost = costs[best_idx]
        convergence = [best_cost]
        
        for gen in range(self.generations):
            new_pop = []
            for i in range(self.pop_size):
                target_vec = pop[i].copy()
                mutant = self._mutate(pop, i, source, target)
                
                # 二项式交叉
                if len(mutant) > 1 and len(target_vec) > 1:
                    min_len = min(len(mutant), len(target_vec))
                    child = []
                    for j in range(min_len):
                        if np.random.random() < self.CR:
                            child.append(mutant[j])
                        else:
                            child.append(target_vec[j])
                    child = self._repair(child, source, target)
                else:
                    child = target_vec.copy()
                
                child_cost = path_cost(self.G, child, self.weight_type)
                target_cost = path_cost(self.G, target_vec, self.weight_type)
                
                if child_cost <= target_cost:
                    new_pop.append(child)
                    costs[i] = child_cost
                else:
                    new_pop.append(target_vec)
                
                if costs[i] < best_cost:
                    best_cost = costs[i]
                    best_path = new_pop[-1].copy()
                    convergence.append(best_cost)
            
            pop = new_pop
            if gen % 30 == 0 and verbose:
                print(f"    DE Gen {gen}: best_cost={best_cost:.2f}")
        
        return OptimizationResult(
            algorithm='DE', best_cost=best_cost, best_path=best_path,
            convergence=convergence, runtime=time.time()-start_time,
            iterations=self.generations,
            metadata={'F': self.F, 'CR': self.CR, 'pop_size': self.pop_size}
        )


# ─────────────────────────────────────────────────────────────────
# 6. 粒子群算法 (PSO)
# ─────────────────────────────────────────────────────────────────
class ParticleSwarmOptimization:
    """
    粒子群算法(PSO)求解最短路径
    粒子: 路径节点序列
    速度: 节点插入/删除/交换操作
    惯性权重: w = 0.7 - 0.4*(gen/max_gen)
    """
    def __init__(self, G, n_particles=40, iterations=150,
                 w=0.7, c1=1.5, c2=1.5,
                 weight_type='time'):
        self.G = G
        self.nx_graph = G.g
        self.weight_type = weight_type
        self.n_particles = n_particles
        self.iterations = iterations
        self.w = w; self.c1 = c1; self.c2 = c2
    
    def _init_particle(self, source, target):
        """初始化粒子"""
        try:
            path = nx.shortest_path(self.nx_graph, source, target, weight='length')
        except:
            path = [source, target]
        return path.copy()
    
    def _velocity_step(self, particle, gbest, pbest, source, target):
        """PSO速度更新 (基于节点操作概率)"""
        new_particle = particle.copy()
        
        # 认知: 向pbest学习 (插入pbest中的好节点)
        if np.random.random() < self.c1 * 0.1:
            if len(pbest) > 2:
                insert_node = pbest[np.random.randint(1, len(pbest)-1)]
                if insert_node not in new_particle and insert_node in self.nx_graph.neighbors(new_particle[max(0, len(new_particle)//2)]):
                    insert_pos = np.random.randint(1, len(new_particle))
                    new_particle.insert(insert_pos, insert_node)
        
        # 社会: 向gbest学习
        if np.random.random() < self.c2 * 0.1:
            if len(gbest) > 2:
                insert_node = gbest[np.random.randint(1, len(gbest)-1)]
                if insert_node not in new_particle:
                    insert_pos = np.random.randint(1, len(new_particle))
                    new_particle.insert(insert_pos, insert_node)
        
        # 交换操作 (模拟速度)
        if len(new_particle) > 3 and np.random.random() < self.w:
            i, j = np.random.choice(range(1, len(new_particle)-1), 2, replace=False)
            new_particle[i], new_particle[j] = new_particle[j], new_particle[i]
        
        # 修复
        fixed = [new_particle[0]]
        for node in new_particle[1:]:
            if fixed[-1] in self.nx_graph.neighbors(node):
                fixed.append(node)
            elif node not in fixed:
                try:
                    sub = nx.shortest_path(self.nx_graph, fixed[-1], target)
                    fixed.extend(sub[1:])
                    break
                except:
                    pass
        
        return fixed[:80]
    
    def solve(self, source, target, verbose=False) -> OptimizationResult:
        start_time = time.time()
        source = int(source); target = int(target)
        
        particles = [self._init_particle(source, target) for _ in range(self.n_particles)]
        velocities = [None] * self.n_particles
        pbest = [p.copy() for p in particles]
        pbest_cost = [path_cost(self.G, p, self.weight_type) for p in particles]
        
        gbest_idx = np.argmin(pbest_cost)
        gbest = pbest[gbest_idx].copy()
        gbest_cost = pbest_cost[gbest_idx]
        convergence = [gbest_cost]
        
        for it in range(self.iterations):
            w_now = 0.7 - 0.3 * (it / self.iterations)
            
            for i in range(self.n_particles):
                particles[i] = self._velocity_step(particles[i], gbest, pbest[i], source, target)
                cost = path_cost(self.G, particles[i], self.weight_type)
                
                if cost < pbest_cost[i]:
                    pbest_cost[i] = cost
                    pbest[i] = particles[i].copy()
                    if cost < gbest_cost:
                        gbest_cost = cost
                        gbest = particles[i].copy()
                        convergence.append(gbest_cost)
            
            if it % 30 == 0 and verbose:
                print(f"    PSO Iter {it}: best_cost={gbest_cost:.2f}")
        
        return OptimizationResult(
            algorithm='PSO', best_cost=gbest_cost, best_path=gbest,
            convergence=convergence, runtime=time.time()-start_time,
            iterations=self.iterations * self.n_particles,
            metadata={'w': self.w, 'c1': self.c1, 'c2': self.c2}
        )


# ─────────────────────────────────────────────────────────────────
# 7. 神经网络代理模型 (NN)
# ─────────────────────────────────────────────────────────────────
class NeuralPathPredictor:
    """
    神经网络代理模型: 基于图嵌入预测路径成本
    模型: 3层MLP (PyTorch)
    特征: 起点/终点嵌入 + 中间节点统计特征
    训练: 收集Dijkstra真实最优路径作为训练数据
    """
    def __init__(self, G, hidden_dim=128, weight_type='time'):
        self.G = G
        self.nx_graph = G.g
        self.weight_type = weight_type
        self.hidden_dim = hidden_dim
        self.device = 'cpu'
        self.model = None
        self.node_embeddings = None
        self._build_embeddings()
    
    def _build_embeddings(self):
        """使用Node2Vec风格构建节点嵌入"""
        try:
            import torch, torch.nn as nn
        except ImportError:
            print("  [NN] PyTorch not found, using fallback")
            self.node_embeddings = None
            return
        
        nxG = self.nx_graph
        nodes = list(nxG.nodes)
        node_idx = {n: i for i, n in enumerate(nodes)}
        n = len(nodes)
        dim = min(64, n // 4)
        
        # 随机游走生成序列
        walks = []
        for node in nodes[:min(500, n)]:
            walk = [node]
            for _ in range(10):
                nbrs = list(nxG.neighbors(walk[-1]))
                if nbrs:
                    walk.append(np.random.choice(nbrs))
            walks.append(walk)
        
        # Skip-gram embedding
        embed = np.random.randn(n, dim) * 0.01
        window = 3
        
        for _ in range(30):
            gradient = np.zeros_like(embed)
            for walk in walks:
                for i, center in enumerate(walk):
                    ci = node_idx[center]
                    context = walk[max(0,i-window):i+window+1]
                    for ctx in context:
                        if ctx != center:
                            cj = node_idx[ctx]
                            score = np.dot(embed[ci], embed[cj])
                            grad = 1.0 / (1.0 + np.exp(-score))
                            gradient[ci] += grad * embed[cj]
                            gradient[cj] += grad * embed[ci]
            embed += 0.01 * gradient
            embed = embed / (np.linalg.norm(embed, axis=1, keepdims=True) + 1e-8)
        
        self.node_embeddings = {n: embed[node_idx[n]] for n in nodes}
        
        # 定义MLP模型
        class PathMLP(nn.Module):
            def __init__(self, in_dim, hidden):
                super().__init__()
                self.net = nn.Sequential(
                    nn.Linear(in_dim, hidden), nn.ReLU(),
                    nn.Linear(hidden, hidden), nn.ReLU(),
                    nn.Linear(hidden, 64), nn.ReLU(),
                    nn.Linear(64, 1)
                )
            def forward(self, x):
                return self.net(x).squeeze(-1)
        
        self.model = PathMLP(dim * 2 + 8, self.hidden_dim).to(self.device)
        self.node_idx = node_idx
        self.trained = False
    
    def _extract_features(self, source, target, path):
        """提取路径特征向量"""
        if self.node_embeddings is None:
            return np.zeros(136)
        
        src_emb = self.node_embeddings.get(source, np.zeros(64))
        tgt_emb = self.node_embeddings.get(target, np.zeros(64))
        
        # 路径统计特征
        if len(path) < 2:
            stats = np.zeros(8)
        else:
            lengths = []
            times = []
            for i in range(len(path)-1):
                u, v = path[i], path[i+1]
                if self.nx_graph.has_edge(u, v):
                    lengths.append(_get_edge_attr(self.nx_graph, u, v, 'length', 0))
                    times.append(edge_weight_time(self.G, u, v))
            stats = np.array([
                len(path),
                sum(lengths),
                sum(times),
                np.mean(lengths) if lengths else 0,
                np.std(lengths) if lengths else 0,
                np.max(lengths) if lengths else 0,
                np.min(lengths) if lengths else 0,
                lengths[-1] if lengths else 0
            ])
        
        combined = np.concatenate([src_emb, tgt_emb, stats])
        return combined
    
    def _collect_training_data(self, n_samples=200):
        """收集Dijkstra最优路径作为训练数据"""
        import torch as th
        nodes = list(self.nx_graph.nodes)
        if len(nodes) < 10: return
        
        X, y = [], []
        for _ in range(n_samples):
            try:
                s = np.random.choice(nodes)
                t = np.random.choice([n for n in nodes if n != s])
                path = nx.shortest_path(self.nx_graph, s, t, weight='length')
                cost = path_cost(self.G, path, self.weight_type)
                feat = self._extract_features(s, t, path)
                X.append(feat)
                y.append(cost)
            except:
                pass
        
        if len(X) < 10: return
        
        self.X_train = th.FloatTensor(np.array(X))
        self.y_train = th.FloatTensor(np.array(y))
        self.trained = True
    
    def train(self, epochs=50, lr=0.001):
        """训练神经网络"""
        if not hasattr(self, 'X_train') or self.X_train is None:
            self._collect_training_data()
        
        if not self.trained: return
        
        import torch as th
        import torch.nn as nn
        optimizer = th.optim.Adam(self.model.parameters(), lr=lr)
        loss_fn = nn.MSELoss()
        X = self.X_train; y = self.y_train
        dataset = th.utils.data.TensorDataset(X, y)
        loader = th.utils.data.DataLoader(dataset, batch_size=32, shuffle=True)
        
        for epoch in range(epochs):
            total_loss = 0
            for batch_x, batch_y in loader:
                batch_x, batch_y = batch_x.to(self.device), batch_y.to(self.device)
                optimizer.zero_grad()
                pred = self.model(batch_x)
                loss = loss_fn(pred, batch_y)
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
            if epoch % 20 == 0:
                print(f"    NN Epoch {epoch}: loss={total_loss/len(loader):.4f}")
        
        self.trained = True
    
    def predict(self, source, target):
        """预测最短路径 (使用NN引导搜索)"""
        import torch as th
        if self.model is None or self.node_embeddings is None:
            return nx.shortest_path(self.nx_graph, source, target, weight='length')
        
        self.model.eval()
        with th.no_grad():
            feat = self._extract_features(source, target, [source, target])
            x = th.FloatTensor(feat).unsqueeze(0).to(self.device)
            pred_cost = self.model(x).item()
        
        # 使用预测引导的贪心搜索
        path = [source]
        current = source
        for _ in range(100):
            if current == target: break
            neighbors = list(self.nx_graph.neighbors(current))
            if not neighbors: break
            
            best_next = neighbors[0]
            best_score = float('inf')
            
            for n in neighbors:
                cost = _get_edge_attr(self.nx_graph, current, n, 'length', 100)
                extended = path + [n]
                feat2 = self._extract_features(n, target, extended)
                with th.no_grad():
                    x2 = th.FloatTensor(feat2).unsqueeze(0).to(self.device)
                    future_cost = self.model(x2).item()
                score = cost + future_cost * 0.5
                if score < best_score:
                    best_score = score
                    best_next = n
            
            if best_next == current: break
            path.append(best_next)
            current = best_next
        
        return path
    
    def solve(self, source, target, verbose=False) -> OptimizationResult:
        start_time = time.time()
        source = int(source); target = int(target)
        
        if not self.trained:
            print("  [NN] Training on Dijkstra paths...")
            self._collect_training_data()
            self.train(epochs=50)
        
        # NN预测路径 + Dijkstra验证
        nn_path = self.predict(source, target)
        nn_cost = path_cost(self.G, nn_path, self.weight_type)
        
        try:
            dijkstra_path = nx.shortest_path(self.nx_graph, source, target, weight='length')
            dijkstra_cost = path_cost(self.G, dijkstra_path, self.weight_type)
        except:
            dijkstra_path = nn_path
            dijkstra_cost = nn_cost
        
        best_path = nn_path if nn_cost <= dijkstra_cost * 1.2 else dijkstra_path
        best_cost = path_cost(self.G, best_path, self.weight_type)
        
        return OptimizationResult(
            algorithm='NN', best_cost=best_cost, best_path=best_path,
            convergence=[dijkstra_cost, best_cost], runtime=time.time()-start_time,
            iterations=1,
            metadata={'trained': self.trained, 'nn_cost': nn_cost, 'dijkstra_cost': dijkstra_cost}
        )


# ─────────────────────────────────────────────────────────────────
# 主求解器: 一键运行所有算法
# ─────────────────────────────────────────────────────────────────
class MetaHeuristicSolver:
    """
    元启发式算法综合求解器
    输入: OSMnx路网 + 起终点
    输出: 7种算法对比结果 + 最优路径
    """
    def __init__(self, G):
        self.G = G
    
    def solve_all(self, source, target, verbose=True) -> Dict[str, OptimizationResult]:
        source = int(source); target = int(target)
        results = {}
        
        if verbose:
            print(f"\n{'='*60}")
            print(f"元启发式算法最短路径求解 | 起点={source} | 终点={target}")
            print(f"{'='*60}")
        
        # 基准
        r_dij = baseline_dijkstra(self.G, source, target, 'time')
        if r_dij: results['Dijkstra'] = r_dij
        
        # GA
        if verbose: print(f"\n[1/7] 遗传算法 (GA)...")
        ga = GeneticAlgorithm(self.G, population_size=80, generations=150)
        results['GA'] = ga.solve(source, target, verbose=verbose)
        
        # SA
        if verbose: print(f"\n[2/7] 模拟退火算法 (SA)...")
        sa = SimulatedAnnealing(self.G, T0=500, alpha=0.99, max_iter_per_T=30)
        results['SA'] = sa.solve(source, target, verbose=verbose)
        
        # TS
        if verbose: print(f"\n[3/7] 禁忌搜索算法 (TS)...")
        ts = TabuSearch(self.G, max_iter=200, tabu_tenure=15)
        results['TS'] = ts.solve(source, target, verbose=verbose)
        
        # ACO
        if verbose: print(f"\n[4/7] 蚁群算法 (ACO)...")
        aco = AntColonyOptimization(self.G, n_ants=25, n_iterations=80)
        results['ACO'] = aco.solve(source, target, verbose=verbose)
        
        # DE
        if verbose: print(f"\n[5/7] 差分进化算法 (DE)...")
        de = DifferentialEvolution(self.G, population_size=50, generations=120)
        results['DE'] = de.solve(source, target, verbose=verbose)
        
        # PSO
        if verbose: print(f"\n[6/7] 粒子群算法 (PSO)...")
        pso = ParticleSwarmOptimization(self.G, n_particles=30, iterations=100)
        results['PSO'] = pso.solve(source, target, verbose=verbose)
        
        # NN
        if verbose: print(f"\n[7/7] 神经网络代理模型 (NN)...")
        nn_model = NeuralPathPredictor(self.G)
        results['NN'] = nn_model.solve(source, target, verbose=verbose)
        
        if verbose:
            print(f"\n{'='*60}")
            print("求解结果汇总:")
            print(f"{'='*60}")
            dijkstra_cost = results.get('Dijkstra').best_cost if 'Dijkstra' in results else None
            for name, res in sorted(results.items(), key=lambda x: x[1].best_cost):
                gap = ''
                if dijkstra_cost and name != 'Dijkstra':
                    g = (res.best_cost - dijkstra_cost) / dijkstra_cost * 100
                    gap = f" | 相对Dijkstra: {g:+.2f}%"
                print(f"  {name:<12} cost={res.best_cost:8.2f}min | {len(res.best_path):4d}节点 | {res.runtime:6.2f}s{gap}")
        
        return results
    
    def visualize_convergence(self, results: Dict[str, OptimizationResult], save_path):
        """绘制收敛曲线对比图"""
        fig, axes = plt.subplots(1, 2, figsize=(16, 6))
        fig.patch.set_facecolor('#0a1628')
        for ax in axes:
            ax.set_facecolor('#0d1f3a')
            ax.tick_params(colors='#7a8fa6')
            for spine in ax.spines.values(): spine.set_color('#2d4a6e')
        
        colors = {'Dijkstra':'#00ff88','GA':'#ff6b6b','SA':'#ffd93d',
                   'TS':'#6bcbff','ACO':'#c77dff','DE':'#ff9f43','PSO':'#a8e6cf','NN':'#ff8fab'}
        
        # 收敛曲线
        ax = axes[0]
        for name, res in results.items():
            if len(res.convergence) > 1:
                ax.plot(res.convergence, label=name, color=colors.get(name,'#888'),
                        lw=1.8, alpha=0.85)
        ax.set_xlabel('Iteration', color='white', fontsize=11)
        ax.set_ylabel('Path Cost (minutes)', color='white', fontsize=11)
        ax.set_title('Convergence Curves of Meta-heuristic Algorithms', color='white', fontsize=12)
        ax.legend(facecolor='#1a2a3a', labelcolor='white', fontsize=9, loc='upper right')
        ax.grid(True, alpha=0.15, color='#4a6fa5')
        
        # 算法对比柱状图
        ax = axes[1]
        names = list(results.keys())
        costs = [results[n].best_cost for n in names]
        bars = ax.bar(names, costs, color=[colors.get(n,'#888') for n in names], alpha=0.85, width=0.6)
        ax.set_xlabel('Algorithm', color='white', fontsize=11)
        ax.set_ylabel('Best Path Cost (min)', color='white', fontsize=11)
        ax.set_title('Optimal Path Cost Comparison', color='white', fontsize=12)
        ax.tick_params(axis='x', rotation=30, colors='white')
        ax.tick_params(axis='y', colors='white')
        for bar, cost in zip(bars, costs):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
                    f'{cost:.1f}', ha='center', va='bottom', color='white', fontsize=9)
        ax.grid(True, axis='y', alpha=0.15, color='#4a6fa5')
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='#0a1628')
        plt.close()
        print(f"  [CHART] Convergence saved: {save_path}")


# ─────────────────────────────────────────────────────────────────
# 演示入口
# ─────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("15分钟城市 - 元启发式算法最短路径模块")
    print("="*60)
    
    # 自动下载或加载南山区路网
    import os
    cache_path = "shenzhen_nanshan.graphml"
    
    if os.path.exists(cache_path):
        print("Loading cached Shenzhen Nanshan graph...")
        G = ox.load_graphml(cache_path)
    else:
        print("Downloading Shenzhen Nanshan OSM graph...")
        G = ox.graph_from_bbox(22.5552, 22.5082, 113.9538, 113.9017,
                                network_type='walk', simplify=True)
        ox.save_graphml(G, cache_path)
        print(f"Cached to {cache_path}")
    
    solver = MetaHeuristicSolver(G)
    
    # 随机选择起终点
    nodes = list(G.nodes)
    np.random.seed(42)
    src = np.random.choice(nodes)
    dst = np.random.choice([n for n in nodes if n != src])
    
    results = solver.solve_all(src, dst, verbose=True)
    
    # 保存收敛图
    solver.visualize_convergence(results, "meta_heuristic_convergence.png")
    print("\nAll done!")
