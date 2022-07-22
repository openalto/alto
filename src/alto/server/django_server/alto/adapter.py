

def calculate_path_vector(pairs, properties):
    paths = {}
    link_map = { 'L1': { 'bandwidth': 100, 'latency': 5} }
    for src, dst in pairs:
        if src not in paths:
            paths[src] = {}
        paths[src][dst] = ['L1']
    return paths, link_map
