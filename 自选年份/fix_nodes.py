"""修复 network_nodes.json：从原始 CSV 读取正确坐标并重建"""
import os, json, pickle

OUT_DIR = r'E:\xicha gis 智能定位\自选年份\network_output'
NODES_CSV = r'E:\xicha gis 智能定位\projects\15min-urban-accessibility\osm_data\nanshan_network_nodes.csv'

import pandas as pd
df = pd.read_csv(NODES_CSV, encoding='utf-8')
print(f"CSV nodes: {len(df)}, columns: {list(df.columns)}")

# Check column names
print("Sample row:", df.iloc[0].to_dict())

# Build corrected nodes list
nodes_corrected = []
for _, row in df.iterrows():
    nodes_corrected.append({
        'node_id': int(row.iloc[0]),
        'lon': float(row.iloc[1]),
        'lat': float(row.iloc[2]),
    })

print(f"Corrected nodes: {len(nodes_corrected)}")
print(f"Sample: {nodes_corrected[0]}")

# Save corrected nodes
nodes_path = os.path.join(OUT_DIR, 'network_nodes.json')
with open(nodes_path, 'w', encoding='utf-8') as f:
    json.dump(nodes_corrected, f, ensure_ascii=False, indent=2)
print(f"Saved: {nodes_path}")

# Also reload the graph and add lon/lat attrs
graph_path = os.path.join(OUT_DIR, 'network_graph.pkl')
with open(graph_path, 'rb') as f:
    G = pickle.load(f)
print(f"Graph nodes: {G.number_of_nodes()}")

for node in nodes_corrected:
    nid = node['node_id']
    if nid in G:
        G.nodes[nid]['lon'] = node['lon']
        G.nodes[nid]['lat'] = node['lat']

# Save updated graph
with open(graph_path, 'wb') as f:
    pickle.dump(G, f)
print("Graph updated with lon/lat attributes")

# Verify
import requests
r = requests.post('http://localhost:8765/snap', json={'lon': 113.938, 'lat': 22.530})
print('SNAP test:', r.json())
