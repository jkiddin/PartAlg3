import subprocess
import os
import platform
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import re

def normalize_path(path):
    """Normalize file paths to use the correct OS-specific separator."""
    return os.path.normpath(path)

def run_cpp_program(input_file, output_file):
    compile_cmd = ['g++', 'Pseudo-knots-corr5-01-19.cpp', '-o', 'pseudo_knots']
    subprocess.run(compile_cmd, check=True)

    run_cmd = ['./pseudo_knots', input_file, output_file] if platform.system() != 'Windows' else ['pseudo_knots', input_file, output_file]
    subprocess.run(run_cmd, check=True)

def extract_blocks_with_types(output_file):
    blocks = []
    block_types = []
    current_block = []

    type_mapping = {
        "The block is a recursive PK": "Recursive PK",
        "this block represents a regular-region": "Regular",
        "this block represents a pseudoknot": "Non-recursive PK",
    }

    with open(output_file, 'r') as file:
        block_started = False
        for line in file:
            if "New Block" in line:
                if current_block:
                    blocks.append(current_block)
                    if len(block_types) < len(blocks):
                        block_types.append("Unknown")
                    current_block = []
                block_started = True
            elif block_started and re.search(r'\(\d+,\d+\)', line):
                matches = re.findall(r'\((\d+),(\d+)\)', line)
                for match in matches:
                    v1, v2 = int(match[0]), int(match[1])
                    current_block.append((v1, v2))
            elif any(phrase in line for phrase in type_mapping.keys()):
                for phrase, label in type_mapping.items():
                    if phrase in line:
                        block_types.append(label)
                        break
            elif "Summary information" in line:
                if current_block:
                    blocks.append(current_block)
                    if len(block_types) < len(blocks):
                        block_types.append("Unknown")
                break

    return blocks, block_types

def read_adjacency_matrix(input_file):
    with open(input_file, 'r') as file:
        matrix = []
        for line in file:
            row = list(map(int, line.strip().split()))
            matrix.append(row)
    return matrix

def add_edges_from_matrix(G, matrix):
    for i in range(len(matrix)):
        for j in range(len(matrix[i])):
            weight = matrix[i][j]
            if weight > 0 and i != j:
                for _ in range(weight):
                    G.add_edge(i, j, weight=weight)

def draw_combined_graph(matrix, blocks, block_types, G):
    pos = nx.spring_layout(G)

    num_blocks = len(blocks)
    cmap = plt.colormaps['tab20']
    block_colors = [cmap(i / num_blocks) for i in range(num_blocks)]

    edge_colors = {}
    for i, edges in enumerate(blocks):
        block_color = block_colors[i]
        G.add_edges_from(edges)

        for edge in edges:
            edge_colors[edge] = block_color

    plt.figure(figsize=(12, 12))
    plt.title("Graph with Colored Blocks and Weights", fontsize=16)

    nx.draw_networkx_nodes(G, pos, node_size=700, node_color="skyblue")

    for edge, color in edge_colors.items():
        nx.draw_networkx_edges(G, pos, edgelist=[edge], edge_color=[color], width=2)

    nx.draw_networkx_labels(G, pos, font_size=12, font_color="black")

    edge_labels = {(u, v): G[u][v][0]['weight'] for u, v in G.edges()}
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=10, font_color="red")

    legend_handles = []
    for i, block_type in enumerate(block_types):
        handle = plt.Line2D([], [], color=block_colors[i], label=block_type, linewidth=2)
        legend_handles.append(handle)

    plt.legend(
        handles=legend_handles, 
        title="Block Types", 
        loc="center left", 
        bbox_to_anchor=(1.00, 0.5), 
        fontsize=10
    )

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    input_file = input("Enter the input file path (or leave blank to use the current directory): ")
    output_file = input("Enter the output file path (or leave blank to use the current directory): ")

    if not input_file:
        input_file = normalize_path(os.path.join(os.getcwd(), "matrix.txt"))
    else:
        input_file = normalize_path(input_file)

    if not output_file:
        output_file = normalize_path(os.path.join(os.getcwd(), "matrix_out.txt"))
    else:
        output_file = normalize_path(output_file)

    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file not found: {input_file}")

    run_cpp_program(input_file, output_file)

    if not os.path.exists(output_file):
        raise FileNotFoundError(f"Output file not found: {output_file}")

    blocks, block_types = extract_blocks_with_types(output_file)

    matrix = read_adjacency_matrix(input_file)

    G = nx.MultiGraph()
    add_edges_from_matrix(G, matrix)

    draw_combined_graph(matrix, blocks, block_types, G)
