import numpy as np
import re
import sys

class Operator:
    def __init__(self, node_1, node_2, operator):
        self.node_1 = node_1
        self.node_2 = node_2
        self.operator = operator

    def __repr__(self):
        if self.node_2 is None:
            return f"({self.operator}{self.node_1})"
        else:
            return f"({self.node_1} {self.operator} {self.node_2})"
    def export(self):
        if self.node_2 is None:
            return f"({self.operator} {self.node_1.export()})"
        else:
            return f"({self.node_1.export()} {self.operator} {self.node_2.export()})"
    def get_children(self):
        if self.node_2 is None:
            return [self.node_1]
        else:
            return [self.node_1, self.node_2]
    def get_all_children(self, allowed_category=None):
        children = [self.node_1, self.node_2]
        if (allowed_category is not None):
            children = [child for child in children if any(isinstance(child, c) for c in allowed_category)]
        children = [child for child in children if child is not None]
        children += self.node_1.get_all_children(allowed_category)
        if (self.node_2 is not None):
            children += self.node_2.get_all_children(allowed_category)
        return children
    def mutate_operator(self):
        if (self.node_2 is None):
            raise Exception("Cannot mutate unary operator")
        self.operator = np.random.choice(list(set(['&', '|', '+', '-', '*', '/'])-set([self.operator])))
    def replace_child(self, new_child):
        if (self.node_2 is None):
            self.node_1 = new_child
        else:
            if (np.random.choice([True, False])):
                self.node_1 = new_child
            else:
                self.node_2 = new_child

class TernaryOperator:
    def __init__(self, node_1, node_2, node_3):
        self.node_1 = node_1
        self.node_2 = node_2
        self.node_3 = node_3

    def __repr__(self):
        return f"({self.node_1} ? {self.node_2} : {self.node_3})"
    def export(self):
        return f"({self.node_1.export()} ? {self.node_2.export()} : {self.node_3.export()})"
    def get_children(self):
        return [self.node_1, self.node_2, self.node_3]
    def get_all_children(self, allowed_category=None):
        children = [self.node_1, self.node_2, self.node_3]
        if (allowed_category is not None):
            children = [child for child in children if isinstance(child, allowed_category)]
        children += self.node_1.get_all_children(allowed_category)
        children += self.node_2.get_all_children(allowed_category)
        children += self.node_3.get_all_children(allowed_category)
        return children
    def replace_child(self, new_child):
        replace = np.random.choice([0,1,2])
        if (replace == 0):
            self.node_1 = new_child
        elif (replace == 1):
            self.node_2 = new_child
        else:
            self.node_3 = new_child

class Node:
    def __init__(self, name):
        self.name = name
        self.logic = None 
        self.up = None 
        self.down = None
        self.value = None
        self.replaced = None
    def __repr__(self):
        if (self.replaced is not None):
            return self.replaced.__repr__()
        return "NODE_" + self.name
    def export(self):
        if (self.replaced is not None):
            return self.replaced.export()
        return self.name
    def get_children(self):
        return []
    def get_all_children(self, allowed_category=None):
        if (self.replaced is not None):
            return self.replaced.get_all_children()
        if (allowed_category is None or any(isinstance(self, c) for c in allowed_category)):
            return [self]
        return []

class Parameter:
    def __init__(self, name):
        self.name = name
        self.value = None
    def __repr__(self):
        return "PARAM_" + self.name
    def export(self):
        return self.name
    def get_children(self):
        return []
    def get_all_children(self, allowed_category=None):
        if (allowed_category is None or any(isinstance(self, c) for c in allowed_category)):
            return [self]
        return []

class Symbol:
    def __init__(self, name):
        self.name = name
    def __repr__(self):
        return "SYMBOL_" + self.name
    def export(self):
        return self.name
    def get_children(self):
        return []
    def get_all_children(self, allowed_category=None):
        if (allowed_category is None or any(isinstance(self, c) for c in allowed_category)):
            return [self]
        return []

class Logic:
    def __repr__(self):
        return "@LOGIC"
    def export(self):
        return "@logic"
    def get_children(self):
        return []
    def get_all_children(self, allowed_category=None):
        if (allowed_category is None or any(isinstance(self, c) for c in allowed_category)):
            return [self]
        return []

class Parser:
    TOKEN_REGEX = r'\s*([&|!\*\+\-\/\?:]|@logic|\$?[A-Za-z_]\w*|\d+(?:\.\d*)?(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?|[()])'
    
    def __init__(self, tokens, nodes, variables):
        tokens = tokens.replace(";", "")
        self.tokens = Parser.tokenize(tokens)
        self.pos = 0
        self.nodes = nodes 
        self.variables = variables

    def tokenize(expression):
        tokens = []
        pos = 0
        while pos < len(expression):
            match = re.match(Parser.TOKEN_REGEX, expression[pos:])
            if not match:
                raise SyntaxError(f"Invalid token starting at: '{expression[pos:]}'")
            token = match.group(1)
            tokens.append(token)
            pos += match.end()
        tokens.append('EOF')
        return tokens

    def get_symbol(self, token):
        if token in self.nodes:
            return self.nodes[token]
        elif token in self.variables:
            return self.variables[token]
        return Symbol(token)

    def current(self):
        return self.tokens[self.pos]

    def eat(self, token):
        if self.current() == token:
            self.pos += 1
        else:
            raise SyntaxError(f"Expected '{token}' but found '{self.current()}'")

    def parse(self):
        node = self.parse_expression()
        if self.current() != 'EOF':
            raise SyntaxError("Extra token at the end")
        return node

    def parse_expression(self):
        return self.parse_conditional()

    def parse_conditional(self):
        condition = self.parse_logical_or()
        if self.current() == '?':
            self.eat('?')
            then_expr = self.parse_expression()
            if self.current() != ':':
                raise SyntaxError("Expected ':' in conditional expression")
            self.eat(':')
            else_expr = self.parse_expression()
            condition = TernaryOperator(condition, then_expr, else_expr)
        return condition

    def parse_logical_or(self):
        node = self.parse_logical_and()
        while self.current() == '|':
            op = self.current()
            self.eat(op)
            right = self.parse_logical_and()
            node = Operator(node, right, op)
        return node

    def parse_logical_and(self):
        node = self.parse_additive()
        while self.current() == '&':
            op = self.current()
            self.eat(op)
            right = self.parse_additive()
            node = Operator(node, right, op)
        return node

    def parse_additive(self):
        node = self.parse_multiplicative()
        while self.current() in ('+', '-'):
            op = self.current()
            self.eat(op)
            right = self.parse_multiplicative()
            node = Operator(node, right, op)
        return node

    def parse_multiplicative(self):
        node = self.parse_unary()
        while self.current() in ('*', '/'):
            op = self.current()
            self.eat(op)
            right = self.parse_unary()
            node = Operator(node, right, op)
        return node

    def parse_unary(self):
        if self.current() == '!':
            op = self.current()
            self.eat(op)
            operand = self.parse_unary()
            # For unary operators, use node_1 for operand, node_2 node_3 as None.
            return Operator(operand, None, op)
        else:
            return self.parse_primary()

    def parse_primary(self):
        token = self.current()
        if token == '(':
            self.eat('(')
            node = self.parse_expression()
            if self.current() != ')':
                raise SyntaxError("Expected ')'")
            self.eat(')')
            return node
        elif re.match(r'\$?[A-Za-z_]\w*', token) or re.match(r'\d+', token):
            self.eat(token)
            return self.get_symbol(token)
        elif token == '@logic':
            self.eat('@logic')
            return Logic()
        else:
            raise SyntaxError(f"Unexpected token: {token}")


class Protocol:
    def __init__(self):
        self.nodes = {}
        self.variables = {}
        self.additional = []

    def to_conjunctive_form(self):
        def recursive_to_conjunctive(node):
            if node is None:
                return node 
            if isinstance(node, Operator):
                if (node.operator=="*" or node.operator=="/"):
                    node.operator = "&"

                if (node.operator=="|" or node.operator=="+"):
                    #A or B => NOT (NOT A and NOT B)
                    # + simplify chains of NOT
                    A = recursive_to_conjunctive(node.node_1)
                    B = recursive_to_conjunctive(node.node_2)
                    new_node = Operator(#NOT
                        Operator( #AND
                            Operator( #NOT A
                                A, None, "!"
                            ),
                            Operator( #NOT B
                                B, None, "!"
                            ),
                            "&"
                        ),
                        None,
                        "!"
                    )
                    return new_node 
                elif (node.operator=="-"):
                    #A - B => A & !B
                    A = recursive_to_conjunctive(node.node_1)
                    B = recursive_to_conjunctive(node.node_2)
                    new_node = Operator( #AND
                        A,
                        Operator(B, None, "!"),
                        "&"
                    )
                    return new_node
                else:
                    node.node_1 = recursive_to_conjunctive(node.node_1)
                    node.node_2 = recursive_to_conjunctive(node.node_2)
                    return node
                
            elif isinstance(node, TernaryOperator):
                #A ? B : C == A & B | !A & C
                A = node.node_1
                B = node.node_2
                C = node.node_3
                new_node = Operator( #OR
                    Operator( #A and B
                        A, B, "&"
                    ),
                    Operator( #!A & C
                        Operator(A, None, "!"),
                        C,
                        "&"
                    ),
                    "|"
                ) 
                return recursive_to_conjunctive(new_node)

            elif isinstance(node, Logic) or isinstance(node, Symbol) or isinstance(node, Parameter) or isinstance(node, Node):
                return node
        def remove_not_chain(node):
            if node is None:
                return node 
            if isinstance(node, Operator):
                node.node_1 = remove_not_chain(node.node_1)
                node.node_2 = remove_not_chain(node.node_2)
                if (node.operator=="!"):
                    if (isinstance(node.node_1, Operator) and node.node_1.operator=="!"):
                        return node.node_1.node_1
                return node 
            elif isinstance(node, TernaryOperator):
                node.node_1 = remove_not_chain(node.node_1)
                node.node_2 = remove_not_chain(node.node_2)
                node.node_3 = remove_not_chain(node.node_3)
                return node 
            else:
                return node
            
        for name, node in self.nodes.items():
            if node.logic:
                node.logic = recursive_to_conjunctive(node.logic)
                node.logic = remove_not_chain(node.logic)
    
        #Goal: logic is flat sequence of ANDs and NOTs. No nexted expressions inside NOT
        # Es A and B and not C ... is allowed. 
        # A and NOT (B and C) is not allowed
        created = dict()
        def recursive_clean(node):
            if isinstance(node, Operator):
                if node.operator=="!":
                    if isinstance(node.node_1, Operator):
                        name = node.node_1.__repr__()
                        if (name in created):
                            new_node = created[name]
                        else:
                            new_node = Node(name)
                            new_node.logic = recursive_clean(node.node_1)
                            created[name] = new_node
                        node.node_1 = new_node
                        return node
                    else:
                        return node
                else:
                    node.node_1 = recursive_clean(node.node_1)
                    node.node_2 = recursive_clean(node.node_2)
                    return node 
            return node 
        for name, node in self.nodes.items():
            if node.logic:
                node.logic = recursive_clean(node.logic)
        #Add new created nodes to self.nodes
        for name, node in created.items():
            if name not in self.nodes:
                self.nodes[name] = node

    def to_graph_matrix(self, shuffle_nodes=False):
        num_nodes = len(self.nodes.keys())
        nodes = list(self.nodes.items())
        if shuffle_nodes:
            np.random.shuffle(nodes)
        nodes_to_index = dict()
        for i, node in enumerate(nodes):
            nodes_to_index[node[1].name] = i
        matrix = np.zeros((num_nodes, num_nodes), dtype=int)

        def add_edge_recursive(node_index, logic, m=1):
            if isinstance(logic, Node):
                matrix[node_index][nodes_to_index[logic.name]] = m
            elif isinstance(logic, Operator):
                if (logic.operator == '&'):
                    add_edge_recursive(node_index, logic.node_1, m)
                    add_edge_recursive(node_index, logic.node_2, m) 
                elif (logic.operator == "!"):
                    add_edge_recursive(node_index, logic.node_1, -m)
                else:
                    print(logic)
                    raise Exception("Graph not in conjunctive simplified form.")

        for name, node in nodes:
            node_index = nodes_to_index[name]
            add_edge_recursive(node_index, node.logic)
        return matrix


    
    def import_from_bnd(self, bnd, cfg):
        #Parse node names
        for line in bnd.readlines():
            if line.startswith("node") or line.startswith("Node"):
                node_name = line.split()[1].replace(" ", "").replace("\n", "")
                self.nodes[node_name] = Node(node_name)
            #Map variables: a variable is in form $TEXT
            for word in line.split():
                match = re.search(r'\$[A-Za-z_]\w*', word)
                if match:
                    matched_value = match.group(0)
                    if matched_value not in self.variables:
                        self.variables[matched_value] = Parameter(matched_value)

        bnd.seek(0)
        current_node = None
        #Parse edges
        for line in bnd.readlines():
            if line.startswith("node") or line.startswith("Node"):
                node_name = line.split()[1].replace(" ", "").replace("\n", "")
                current_node = self.nodes[node_name]
            line = line.replace(" ", "").replace("\n", "").replace("\t","")
            if (line.startswith("logic")):
                current_node.logic = Parser(line.split("=")[1], self.nodes, self.variables).parse()
            elif (line.startswith("rate_up")):
                current_node.up = Parser(line.split("=")[1], self.nodes, self.variables).parse()
            elif (line.startswith("rate_down")):
                current_node.down = Parser(line.split("=")[1], self.nodes, self.variables).parse()
        
        #Parse config
        config_pattern = re.compile(
            r'^\s*(?:(?P<param>\$[A-Za-z_]\w*)|(?P<name>[A-Za-z_]\w*(?:\.istate)))\s*=\s*(?P<value>[^;]+?)\s*;\s*$'
        )           
        for line in cfg.readlines():
            line = line.replace(" ", "").replace("\n", "").replace("\t", "")
            if line.startswith("//") or len(line) == 0:
                continue
            # Remove trailing comment after ';'
            line = re.sub(r'(;)\s*//.*$', r'\1', line)
            match = config_pattern.match(line)
            if match:
                if match.group("param"):
                    # Process $PARAM = value;
                    variable = match.group("param")
                    value = match.group("value")
                    if (variable in self.variables):
                        self.variables[variable].value = value
                elif match.group("name"):
                    # Process NAME(.isstate) = value;
                    name = match.group("name").removesuffix(".istate")
                    value = match.group("value")
                    self.nodes[name].value = value
            else:
                self.additional.append(line)
            
    def export(self):
        export = ""
        for node_name, node in self.nodes.items():
            export += f"node {node_name}\n" + "{\n"
            if (node.logic):
                export += f"\tlogic = {node.logic.export()};\n"
            if (node.up is not None):
                export += f"\trate_up = {node.up.export()};\n"
            if (node.down is not None):
                export += f"\trate_down = {node.down.export()};\n"
            export += "}\n\n"
        return export
    
    def export_cfg(self):
        export = "//Nodes states:\n"
        for node_name, node in self.nodes.items():
            v = node.value
            if v is None:
                v = "0"
            export += f"{node_name}.istate = {v};\n"
        export += "\n//Parameters:\n"
        for variable_name, variable in self.variables.items():
            export += f"{variable_name} = {variable.value};\n"
        export += "\n//Additional variables:\n"
        for line in self.additional:
            export += f"{line}\n"
        return export

    def __repr__(self):
        nodes = " - ".join([f"{node_name}" for node_name, node in self.nodes.items()])
        variables = " - ".join([f"{variable_name}" for variable_name, variable in self.variables.items()])
        expressions = ""
        for node_name, node in self.nodes.items():
            expressions += f"{node_name}:\n"
            expressions += f"\tLogic: {node.logic}\n"
            expressions += f"\tUp: {node.up}\n"
            expressions += f"\tDown: {node.down}\n"
        return f"""Protocol:\n{nodes}\n{variables}\n{expressions}"""

    def make_generic(self):
        remove_nodes = max(0, len(self.nodes.values())-63)
        nodes_to_remove = np.random.choice(list(self.nodes.values()), remove_nodes, replace=False)
        for n in nodes_to_remove:
            del self.nodes[n.name]
            n.replaced = np.random.choice(list(self.nodes.values()), 1, replace=False)[0]
        # 1- Choose input node and set it as input_sub
        # 2- Choose output node and set it as Survival
        # 3- One random node becomes sec_activator
        input_node, output_node, sec_activator, Apoptosis, NonACD = np.random.choice(list(self.nodes.values()), 5, replace=False)
        del self.nodes[input_node.name]
        input_node.name = "input_sub"
        input_node.logic = input_node
        self.nodes["input_sub"] = input_node
        del self.nodes[output_node.name]
        output_node.name = "Survival"
        self.nodes["Survival"] = output_node
        del self.nodes[sec_activator.name]
        sec_activator.name = "sec_activator"
        self.nodes["sec_activator"] = sec_activator

        del self.nodes[NonACD.name]
        NonACD.name = "NonACD"
        self.nodes["NonACD"] = NonACD
        del self.nodes[Apoptosis.name]
        Apoptosis.name = "Apoptosis"
        self.nodes["Apoptosis"] = Apoptosis

        self.additional = [
            "sample_count=1;",
            "max_time=1;",
            "time_tick=.01;",
            "discrete_time=0;",
            "use_physrandgen=FALSE;",
            "seed_pseudorandom=37;",
            "thread_count=1;",
            "statdist_traj_count=1;",
            "statdist_cluster_threshold=0.8;",
            "display_traj=TRUE;"
        ]


    #Randomize one parameter
    def randomize_parameter(self):
        parameter = np.random.choice(list(self.variables.values()))
        parameter.value = np.random.uniform(0, 1)

    #Add something to the logic of a node
    def add_input_to_logic(self, input_node=None):
        nodes_with_logic = list(filter(lambda node: node.logic is not None, self.nodes.values()))
        if (len(nodes_with_logic) == 0):
            return
        while(True):
            candidate_node = np.random.choice(nodes_with_logic)
            if (candidate_node != input_node):
                break 
        if input_node is None:
            input_node = candidate_node
            while(input_node == candidate_node):
                input_node = np.random.choice(list(self.nodes.values()))
        candidate_node.logic = Operator(input_node, candidate_node.logic, np.random.choice(['&', '|', '+', '-', '*', '/']))

    def randomize_node_logic(self):
        nodes_with_logic = list(filter(lambda node: node.logic is not None, self.nodes.values()))
        if (len(nodes_with_logic) == 0):
            return
        candidate_node = np.random.choice(nodes_with_logic)
        logic_length = np.random.randint(3, len(self.nodes)//2)
        inputs = np.random.choice(list(self.nodes.values()), logic_length, replace=False)
        logic = Operator(inputs[0], inputs[1], np.random.choice(['&', '|', '+', '-', '*', '/'])) 
        for i in inputs[2:]:
            logic = Operator(i, logic, np.random.choice(['&', '|', '+', '-', '*', '/']))
            if (np.random.choice([True, False, False, False])):
                logic = Operator(logic, None, '!')
        candidate_node.logic = logic

    def add_new_node(self):
        node_name = f"NODE_{len(self.nodes)}"
        new_node = Node(node_name)
        new_node.up = TernaryOperator(Logic(), Symbol("1"), Symbol("0"))
        new_node.down = TernaryOperator(Logic(), Symbol("0"), Symbol("1"))
        logic_length = np.random.randint(3, len(self.nodes)//2)
        inputs = np.random.choice(list(self.nodes.values()), logic_length, replace=False)
        inputs = [i for i in inputs if i != new_node]
        logic = Operator(inputs[0], inputs[1], np.random.choice(['&', '|', '+', '-', '*', '/'])) 
        for i in inputs[2:]:
            logic = Operator(i, logic, np.random.choice(['&', '|', '+', '-', '*', '/']))
            if (np.random.choice([True, False, False, False])):
                logic = Operator(logic, None, '!')
        new_node.logic = logic 
        add_to_nodes = np.random.randint(1, len(self.nodes)//4)
        new_node.value = np.random.choice(['0', '1'])
        self.nodes[node_name] = new_node
        for _ in range(add_to_nodes):
            self.add_input_to_logic(new_node)
        

    #Extract two random nodes. Switch the logic blocks of them
    def switch_nodes_logic(self):
        nodes_with_logic = list(filter(lambda node: node.logic is not None, self.nodes.values()))
        if (len(nodes_with_logic) < 2):
            return
        node_a, node_b = np.random.choice(nodes_with_logic, 2, replace=False)
        node_a.logic, node_b.logic = node_b.logic, node_a.logic

    #Take one random operator from one random node, replace it with another operator
    def replace_logical_operator(self):
        import sys
        nodes_with_logic = list(filter(lambda node: node.logic is not None, self.nodes.values()))
        if (len(nodes_with_logic) == 0):
            return
        node = np.random.choice(nodes_with_logic)
        operators = node.logic.get_all_children([Operator])
        operators = [o for o in operators if o.node_2 is not None]
        if (len(operators) == 0):
            return
        operator = np.random.choice(operators)
        operator.mutate_operator()

    #Take a random node, take a random node inside its logic, replace it with another node
    def replace_node_inside_logic(self):
        nodes_with_logic = list(filter(lambda node: node.logic is not None, self.nodes.values()))
        if (len(nodes_with_logic) < 2):
            return
        node, new_child = np.random.choice(nodes_with_logic, 2, replace=True)
        base_nodes = node.logic.get_all_children([TernaryOperator, Operator])
        if (len(base_nodes) == 0):
            return
        base_node = np.random.choice(base_nodes)
        base_node.replace_child(new_child)

    #Take a random node, take a part of its logic, negate it
    def negate_subexpression(self):
        nodes_with_logic = list(filter(lambda node: node.logic is not None, self.nodes.values()))
        if (len(nodes_with_logic) == 0):
            return
        node = np.random.choice(nodes_with_logic)
        nodes_with_children = node.logic.get_all_children([Operator, TernaryOperator])
        if (len(nodes_with_children) == 0):
            return
        candidate = np.random.choice(nodes_with_children)
        def negate(node):
            if (isinstance(node, Operator)) and node.operator == '!':
                return node.node_1
            return Operator(node, None, '!')
        if (isinstance(candidate, Operator)):
            if (candidate.node_2 is None or np.random.choice([True, False])):
                candidate.node_1 = negate(candidate.node_1) 
            else:
                candidate.node_2 = negate(candidate.node_2)
        elif (isinstance(candidate, TernaryOperator)):
            replace = np.random.choice([0,1,2])
            if (replace == 0):
                candidate.node_1 = negate(candidate.node_1)
            elif (replace == 1):
                candidate.node_2 = negate(candidate.node_2)
            else:
                candidate.node_3 = negate(candidate.node_3)
        

def save_to_file(protocol, filename):
    with open(f"{filename}.bnd", 'w') as file:
        file.write(protocol.export())
    with open(f"{filename}.cfg", 'w') as file:
        file.write(protocol.export_cfg())

import sys 
import os
def test_zeros(path):
    files = []
    for file in os.listdir(path):
        if file.endswith("_states.csv"):
            files.append(file[:-11])
    print(files)
    for file in files:
        protocol = Protocol()
        protocol.import_from_bnd(open(f"{path}/{file}.bnd", 'r'), open(f"{path}/{file}.cfg", 'r'))
        if len([p for p in protocol.nodes.values() if p.logic is not None]) == 0:
            print(file)
            

if __name__ == "__main__":
    test_zeros(sys.argv[1])
    """if len(sys.argv) != 2:
        print("Usage: python parse.py <path_to_file>")
        sys.exit(1)
    file_path = sys.argv[1]
    from run_simulation import run_simulation
    import os
    try:
        with open(f"{file_path}.bnd", 'r') as bnd_file:
            with open(f"{file_path}.cfg", 'r') as cfg_file:
                protocol = Protocol()
                protocol.import_from_bnd(bnd_file, cfg_file)
                #print(protocol)
                for _ in range(3):
                    protocol.switch_nodes_logic()
                    protocol.replace_logical_operator()
                    protocol.replace_node_inside_logic()
                    protocol.negate_subexpression()
                #protocol.add_input_to_logic()
                #protocol.add_new_node()
                #protocol.randomize_node_logic()
                protocol.randomize_parameter()
                save_to_file(protocol, file_path+"_mutated")
                run_simulation(os.path.dirname(file_path), os.path.basename(file_path)+"_mutated")"""



    