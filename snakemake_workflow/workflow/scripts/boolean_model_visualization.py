import re
import sys
import subprocess

# Funzione per estrarre nodi e connessioni dal file .bnd
def parse_bnd_file(file_path):
    nodes = set()
    edges = []

    with open(file_path, "r") as file:
        content = file.readlines()

    current_node = None
    for line in content:
        line = line.strip()
        if line.startswith("node"):
            current_node = line.split()[1]  # Nome del nodo
            nodes.add(current_node)
        elif "logic =" in line and current_node:
            logic_expression = line.split("=")[1].strip("; ")
            # Estrarre nodi e tipo di connessione
            dependencies = re.findall(r'\b[A-Za-z0-9_]+\b', logic_expression)
            for dep in dependencies:
                # Determina se la connessione è un'inibizione o attivazione
                if dep == current_node:  # Identifica i loop
                    edges.append((dep, current_node, "loop"))
                elif f"!{dep}" in logic_expression or "!" in logic_expression.split(dep)[0]:
                    edges.append((dep, current_node, "inhibition"))
                else:
                    edges.append((dep, current_node, "activation"))
    
    return nodes, edges

if __name__ == "__main__":
    # Verifica che il numero di argomenti sia corretto
    if len(sys.argv) != 2:
        print("Utilizzo: python boolean_model_visualization.py <file.bnd>")
        sys.exit(1)

    bnd_file_path = sys.argv[1]
    dot_file_path = bnd_file_path.replace(".bnd", ".dot")

    # Estrarre i nodi e le connessioni
    nodes, edges = parse_bnd_file(bnd_file_path)

    # Creare il file .dot per Graphviz
    with open(dot_file_path, "w") as dot_file:
        dot_file.write("digraph BooleanNetwork {\n")
        for node in nodes:
            dot_file.write(f'    "{node}" [shape=ellipse, style=filled, fillcolor=lightgrey];\n')  # Rappresentazione come ellissi
        for src, dst, edge_type in edges:
            if edge_type == "activation":
                dot_file.write(f'    "{src}" -> "{dst}" [color=green, penwidth=2.0];\n')  # Connessione verde
            elif edge_type == "inhibition":
                dot_file.write(f'    "{src}" -> "{dst}" [color=red, penwidth=2.0, arrowhead=tee];\n')  # Connessione rossa
            elif edge_type == "loop":
                dot_file.write(f'    "{src}" -> "{dst}" [color=blue, penwidth=2.0, style=dotted];\n')  # Connessione loop
        dot_file.write("}\n")

    print(f"File DOT creato con successo: {dot_file_path}")

    # Generare l'immagine del grafo
    
    png_file_path = dot_file_path.replace(".dot", ".png")
    subprocess.run(["dot", "-Tpng", dot_file_path, "-o", png_file_path])
    print(f"File PNG creato con successo: {png_file_path}")
