import pickle, json
from pathlib import Path

data_dir = Path('e:/xicha gis 智能定位/自选年份/network_output')
G = pickle.load(open(data_dir / 'network_graph.pkl', 'rb'))
import networkx as _nx
all_components = [G.subgraph(c) for c in _nx.connected_components(G)]
all_components.sort(key=lambda s: s.number_of_nodes(), reverse=True)
largest = all_components[0]
largest_nodes = set(largest.nodes())

nodes = json.load(open(data_dir / 'network_nodes.json', 'r', encoding='utf-8'))
NODE_COORDS = {n['node_id']: (n['lon'], n['lat']) for n in nodes}

lons = [NODE_COORDS[n][0] for n in largest_nodes if n in NODE_COORDS]
lats = [NODE_COORDS[n][1] for n in largest_nodes if n in NODE_COORDS]
print(f'Largest component bounds:')
print(f'  Lon: {min(lons):.4f} to {max(lons):.4f}')
print(f'  Lat: {min(lats):.4f} to {max(lats):.4f}')

def extract_coords(feat):
    coords = feat['geometry']['coordinates']
    gtype = feat['geometry']['type']
    result = []
    if gtype == 'LineString':
        return coords
    elif gtype == 'MultiLineString':
        for line in coords:
            result.extend(line)
        return result
    elif gtype == 'Polygon':
        for ring in coords:
            result.extend(ring)
        return result
    return result

roads = json.load(open('e:/xicha gis 智能定位/自选年份/city_twin_output/roads_data.json', 'r', encoding='utf-8'))
all_lons = []
all_lats = []
for feat in roads['features']:
    for c in extract_coords(feat):
        if isinstance(c, list) and len(c) >= 2:
            all_lons.append(c[0])
            all_lats.append(c[1])
print(f'\nRoads bounds ({len(roads["features"])} features):')
print(f'  Lon: {min(all_lons):.4f} to {max(all_lons):.4f}')
print(f'  Lat: {min(all_lats):.4f} to {max(all_lats):.4f}')

buildings = json.load(open('e:/xicha gis 智能定位/自选年份/city_twin_output/base_core_data.json', 'r', encoding='utf-8'))
b_lons = []
b_lats = []
for feat in buildings['features']:
    for c in extract_coords(feat):
        if isinstance(c, list) and len(c) >= 2:
            b_lons.append(c[0])
            b_lats.append(c[1])
print(f'\nBuildings bounds ({len(buildings["features"])} features):')
print(f'  Lon: {min(b_lons):.4f} to {max(b_lons):.4f}')
print(f'  Lat: {min(b_lats):.4f} to {max(b_lats):.4f}')

# Check overlap
overlap_lon = max(min(lons), min(all_lons)) <= min(max(lons), max(all_lons))
overlap_lat = max(min(lats), min(all_lats)) <= min(max(lats), max(all_lats))
print(f'\nOverlap: lon={overlap_lon}, lat={overlap_lat}')

# How many network nodes are in roads bounding box
road_min_lon, road_max_lon = min(all_lons), max(all_lons)
road_min_lat, road_max_lat = min(all_lats), max(all_lats)
nodes_in_road_bounds = sum(1 for n in largest_nodes if n in NODE_COORDS and 
    road_min_lon <= NODE_COORDS[n][0] <= road_max_lon and
    road_min_lat <= NODE_COORDS[n][1] <= road_max_lat)
print(f'\nLargest component nodes within roads bounds: {nodes_in_road_bounds}')
