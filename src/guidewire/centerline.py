"""Ordered skeleton extraction and arc-length sampling."""
import cv2
import networkx as nx
import numpy as np
from skimage.morphology import skeletonize


def centerline(mask):
    skeleton = skeletonize(mask != 0)
    nodes = set(map(tuple, np.argwhere(skeleton)))
    graph = nx.Graph()
    graph.add_nodes_from(nodes)
    for y, x in nodes:
        for dy, dx in ((0, 1), (1, -1), (1, 0), (1, 1)):
            other = (y+dy, x+dx)
            if other not in nodes:
                continue
            # Avoid artificial triangular junctions around digital corners.
            if dy and dx and ((y+dy, x) in nodes or (y, x+dx) in nodes):
                continue
            graph.add_edge((y, x), other, weight=float(np.hypot(dy, dx)))
    graph = graph.subgraph(max(nx.connected_components(graph), key=len)).copy()
    # Small skeleton loops around speckles can absorb an otherwise valid tip
    # when short spurs are pruned. Cut only these tiny loops at their weakest
    # mask support; larger loops / physical crossings remain ambiguous.
    support = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5)
    for cycle in nx.cycle_basis(graph):
        if len(cycle) <= 32:
            edges = list(zip(cycle, cycle[1:]+cycle[:1]))
            edge = min(edges, key=lambda pair: (min(support[pair[0]], support[pair[1]]), sorted(pair)))
            if graph.has_edge(*edge):
                graph.remove_edge(*edge)
    # Remove short terminal spurs, retaining meaningful branches for detection.
    for _ in range(3):
        remove = set()
        for end in [n for n, degree in graph.degree if degree == 1]:
            trail, length, previous, current = [], 0., None, end
            while True:
                trail.append(current)
                nxt = [n for n in graph[current] if n != previous]
                if not nxt or (current != end and graph.degree[current] != 2):
                    break
                following = nxt[0]
                length += graph[current][following]["weight"]
                previous, current = current, following
            if length < 20 and graph.degree[current] > 2:
                remove.update(trail[:-1])
        if not remove:
            break
        graph.remove_nodes_from(remove)
    ends = [n for n, degree in graph.degree if degree == 1]
    if len(ends) < 2:
        raise ValueError("Centerline has no unambiguous free endpoints")
    # Current setup has the free catheter tip above the U-shaped bend.
    start = min(ends)
    distances, paths = nx.single_source_dijkstra(graph, start, weight="weight")
    end = max(ends, key=lambda n: distances.get(n, -1))
    path = paths[end]
    stop = "component_endpoint"
    for i, node in enumerate(path):
        if graph.degree[node] > 2 and i > 20:
            # Tiny loops / remnants can have degree 3 without being a physical
            # catheter junction. Require three substantial surviving arms.
            without = nx.subgraph_view(graph, filter_node=lambda n: n != node)
            arms = [part for part in nx.connected_components(without) if len(part) >= 20]
            if len(arms) >= 3:
                path = path[:i+1]
                stop = "branch_junction"
                break
    xy = np.array([(x, y) for y, x in path], dtype=float)
    if len(xy) < 50:
        raise ValueError("Centerline too short after branch rejection")
    return xy, stop


def resample(xy, step):
    arc = np.r_[0, np.cumsum(np.linalg.norm(np.diff(xy, axis=0), axis=1))]
    samples = np.arange(0, arc[-1], step)
    return np.column_stack([np.interp(samples, arc, xy[:, i]) for i in range(2)]), samples
