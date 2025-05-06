import subprocess
import os
import platform
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import re
import sys
import shutil

def check_compiler_availability():
    """
    Check if g++ compiler is available in the system.
    Returns True if the compiler is available, False otherwise.
    """
    try:
        # Using 'where' on Windows and 'which' on Unix-like systems
        check_cmd = 'where' if platform.system() == 'Windows' else 'which'
        subprocess.run([check_cmd, 'g++'], 
                      check=True, 
                      stdout=subprocess.PIPE, 
                      stderr=subprocess.PIPE)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

def normalize_path(path):
    """
    Normalize file paths to use the correct OS-specific separator.
    For example, on Windows it replaces forward slashes with backslashes,
    and on Unix it does the reverse if needed.
    """
    return os.path.normpath(path)

def run_cpp_program(input_file, output_file):
    """
    Compile and execute the C++ program that performs some processing on
    the input file, generating an output file and a graph file.

    :param input_file: Path to the input adjacency matrix file
    :param output_file: Path to the file where the C++ program writes its analysis
    """
    # Check if g++ compiler is available
    if not check_compiler_availability():
        print("Error: g++ compiler not found in your system PATH.")
        print("Please install MinGW (for Windows) or g++ (for Unix-like systems).")
        print("Windows users: After installation, make sure to add the MinGW bin directory to your PATH.")
        sys.exit(1)

    # Get the executable extension based on the OS
    exe_extension = '.exe' if platform.system() == 'Windows' else ''
    executable = f'pseudo_knots{exe_extension}'
    
    # Compile the C++ source file into an executable
    print(f"Compiling C++ program...")
    compile_cmd = ['g++', 'Pseudo-knots-corr5-01-19.cpp', '-o', executable]
    
    try:
        subprocess.run(compile_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("Compilation successful.")
    except subprocess.CalledProcessError as e:
        print(f"Error compiling C++ program: {e}")
        print(f"Error details: {e.stderr.decode('utf-8')}")
        sys.exit(1)

    # Choose the correct command depending on the OS
    if platform.system() == 'Windows':
        run_cmd = [os.path.join('.', executable), input_file, output_file]
    else:
        run_cmd = [f'./{executable}', input_file, output_file]
    
    # Execute the compiled C++ program with the specified arguments
    print(f"Running C++ program with input file: {input_file}")
    print(f"Output will be written to: {output_file}")
    
    try:
        subprocess.run(run_cmd, check=True)
        print("C++ program executed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error executing C++ program: {e}")
        sys.exit(1)

def extract_blocks_with_types(output_file):
    """
    Parse the output file produced by the C++ program to extract blocks of edges
    (pairs of vertices) and their associated types (e.g., 'Recursive PK', 'Regular', etc.).

    :param output_file: The file that contains the textual output from the C++ program
    :return: A tuple (blocks, block_types) where:
             - blocks is a list of lists; each sub-list contains (v1, v2) pairs.
             - block_types is a parallel list of block type strings.
    """
    blocks = []
    block_types = []
    current_block = []

    # Mapping from specific strings in the output file to human-readable labels.
    type_mapping = {
        "The block is a recursive PK": "Recursive PK",
        "this block represents a regular-region": "Regular",
        "this block represents a pseudoknot": "Non-recursive PK",
    }

    try:
        with open(output_file, 'r') as file:
            block_started = False
            for line in file:
                # Detect start of a new block.
                if "New Block" in line:
                    # If there is an existing block being built, close it out first.
                    if current_block:
                        blocks.append(current_block)
                        # If we didn't detect a type for the previous block, mark it as 'Unknown'.
                        if len(block_types) < len(blocks):
                            block_types.append("Unknown")
                    current_block = []
                    block_started = True

                # Capture the edges (v1, v2) once a block is in progress.
                elif block_started and re.search(r'\(\d+,\d+\)', line):
                    matches = re.findall(r'\((\d+),(\d+)\)', line)
                    for match in matches:
                        v1, v2 = int(match[0]), int(match[1])
                        current_block.append((v1, v2))

                # Check if the line contains any known type keywords and assign the appropriate label.
                elif any(phrase in line for phrase in type_mapping.keys()):
                    for phrase, label in type_mapping.items():
                        if phrase in line:
                            block_types.append(label)
                            break

                # If "Summary information" appears, that means we are done reading blocks.
                elif "Summary information" in line:
                    if current_block:
                        blocks.append(current_block)
                        if len(block_types) < len(blocks):
                            block_types.append("Unknown")
                    break
    except Exception as e:
        print(f"Error reading output file: {e}")
        sys.exit(1)

    return blocks, block_types

def read_adjacency_matrix(input_file):
    """
    Read the adjacency matrix from the provided text file. Each line in the file
    should be a space-separated list of integers.

    :param input_file: Path to the file containing the adjacency matrix
    :return: A 2D list (list of lists) of integers representing the adjacency matrix
    """
    try:
        with open(input_file, 'r') as file:
            matrix = []
            for line in file:
                row = list(map(int, line.strip().split()))
                matrix.append(row)
        return matrix
    except Exception as e:
        print(f"Error reading adjacency matrix: {e}")
        sys.exit(1)

def add_edges_from_matrix(G, matrix):
    """
    Add edges to the provided graph G based on a 2D adjacency matrix.
    If matrix[i][j] > 0, that means there is an edge between node i and node j.
    Multiple edges may be added for a higher weight if using a MultiGraph.

    :param G: A NetworkX MultiGraph (or Graph) object
    :param matrix: A 2D adjacency matrix where matrix[i][j] is the weight
    """
    for i in range(len(matrix)):
        for j in range(len(matrix[i])):
            weight = matrix[i][j]
            # Only add edges if weight is positive, and skip self-loops (i != j).
            if weight > 0 and i != j:
                # If weight is more than 1, we add parallel edges (in a MultiGraph).
                for _ in range(weight):
                    G.add_edge(i, j, weight=weight)

def draw_combined_graph(matrix, blocks, block_types, G):
    """
    Draw a figure containing multiple "blocks" of edges. Each block is offset in
    the 2D plane so that blocks don't overlap. We use NetworkX to layout the edges
    separately and then combine them into one figure.

    :param matrix: The adjacency matrix (not directly used here except for reference)
    :param blocks: A list of edge lists, where each edge is a (v1, v2) tuple
    :param block_types: A parallel list of block types (e.g., 'Recursive PK', 'Regular')
    :param G: The original network (MultiGraph) containing all edges with their weights
    """
    pos = {}
    offset = 1.8  # Used to shift each block in the layout so they don't overlap.

    # Generate a layout for each block and store its positions in 'pos' dict.
    for i, block in enumerate(blocks):
        # spring_layout calculates positions for a graph's nodes in a spring-force way.
        block_pos = nx.spring_layout(nx.Graph(block), seed=i)
        for node in block_pos:
            # Each node is named "node_block_index" to avoid collisions between blocks.
            pos[f"{node}_block_{i}"] = block_pos[node] + np.array([i * offset, 0])

    # Prepare the figure
    plt.figure(figsize=(12, 12))
    plt.title("Graph with Separated Blocks and Weights", fontsize=16)

    # Plot each block separately, offset vertically so they stack on the figure.
    for i, (block, block_type) in enumerate(zip(blocks, block_types)):
        # Renaming original nodes (u, v) as (u_block_i, v_block_i) for clarity.
        block_edges = [(f"{u}_block_{i}", f"{v}_block_{i}") for u, v in block]

        # Create a local graph for just this block.
        G_block = nx.Graph()
        G_block.add_edges_from(block_edges)

        # Offset this entire block further up or down based on the block index (i).
        for node in G_block.nodes:
            pos[node] += np.array([0, i * offset])

        # Draw nodes and edges for this block.
        nx.draw_networkx_nodes(G_block, pos, node_size=700, node_color="skyblue")
        nx.draw_networkx_edges(G_block, pos, edgelist=block_edges, edge_color="black", width=2)

        # Create labels without the "_block_i" suffix, so they display as original node IDs.
        labels = {node: node.split("_")[0] for node in G_block.nodes}
        nx.draw_networkx_labels(G_block, pos, labels=labels, font_size=12, font_color="black")

        # Display edge weights taken from the main graph G.
        edge_labels = {
            (f"{u}_block_{i}", f"{v}_block_{i}"): G[u][v][0]['weight'] for u, v in block
        }
        nx.draw_networkx_edge_labels(G_block, pos, edge_labels=edge_labels, font_size=10, font_color="red")

        # Add block type as a title above the block
        y_pos = max([pos[node][1] for node in G_block.nodes]) + 0.2
        x_pos = sum([pos[node][0] for node in G_block.nodes]) / len(G_block.nodes)
        plt.text(x_pos, y_pos, f"Block Type: {block_type}", 
                horizontalalignment='center', fontsize=12, fontweight='bold')

    # Adjust spacing and show the plotted figure.
    plt.tight_layout()
    plt.savefig("graph_visualization.png")  # Save the figure before showing it
    print("Graph visualization saved as 'graph_visualization.png'")
    plt.show()

if __name__ == "__main__":
    print("=" * 80)
    print("Pseudo-knot Analysis and Visualization Tool")
    print("=" * 80)
    
    # Prompt the user for the file paths. If blank, use defaults in the current working directory.
    input_file = input("Enter the input file (or leave blank if you have a 'matrix.txt' in the current dir): ")
    output_file = input("Enter the output file (or leave blank to use the default): ")

    # If the user did not enter a path, default to 'matrix.txt' in the current directory.
    if not input_file:
        input_file = normalize_path(os.path.join(os.getcwd(), "matrix.txt"))
    else:
        input_file = normalize_path(input_file)

    # Similarly, default to 'matrix_out.txt' if no output file is specified.
    if not output_file:
        output_file = normalize_path(os.path.join(os.getcwd(), "matrix_out.txt"))
    else:
        output_file = normalize_path(output_file)

    # Make sure the input file actually exists before proceeding.
    if not os.path.exists(input_file):
        print(f"Error: Input file not found: {input_file}")
        sys.exit(1)

    # Run the external C++ program to generate output and graph data.
    run_cpp_program(input_file, output_file)

    # Verify that the output file was created.
    if not os.path.exists(output_file):
        print(f"Error: Output file not found: {output_file}")
        sys.exit(1)

    # Extract the blocks (subgraphs) and their types from the output.
    blocks, block_types = extract_blocks_with_types(output_file)
    
    if not blocks:
        print("No blocks were extracted from the output file.")
        sys.exit(1)
    
    print(f"Extracted {len(blocks)} blocks from the output file:")
    for i, (block, block_type) in enumerate(zip(blocks, block_types)):
        print(f"  Block {i+1}: {block_type} with {len(block)} edges")

    # Read the original adjacency matrix.
    matrix = read_adjacency_matrix(input_file)

    # Create a MultiGraph to allow parallel edges in case of multiple weights between two nodes.
    G = nx.MultiGraph()
    add_edges_from_matrix(G, matrix)

    # Visualize each block in a combined layout.
    print("Generating visualization...")
    draw_combined_graph(matrix, blocks, block_types, G)
