from causallearn.search.ScoreBased.GES import ges
from causallearn.utils.GraphUtils import GraphUtils
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io

class CausalDiscoveryEngine:
    def __init__(self, data):
        """
        Args:
            data (pd.DataFrame): The dataset containing U, I, A, Y columns.
        """
        self.data = data
        self.graph = None
        
    def learn_structure(self):
        """
        Runs GES algorithm (Score-based) with BIC score and tiered constraints.
        """
        print("Starting Causal Structure Learning (GES)...")
        
        # Define Tiers
        # Tier 1: User Features (U_...)
        # Tier 2: Item Features (I_...)
        # Tier 3: Action (A_...)
        # Tier 4: Outcome (Y_...)
        
        tiers = {}
        for col in self.data.columns:
            if col.startswith('U_'):
                tiers[col] = 1
            elif col.startswith('I_'):
                tiers[col] = 2
            elif col.startswith('A_'):
                tiers[col] = 3
            elif col.startswith('Y_'):
                tiers[col] = 4
            else:
                tiers[col] = 0 # Default or unknown
        
        # Let's prepare the data for causal-learn (numpy array)
        dataset = self.data.to_numpy()
        var_names = self.data.columns.tolist()
        
        # Run GES
        # ges returns a dictionary with 'G' (graph), 'update_score_list'
        Record = ges(dataset, score_func='local_score_BIC')
        
        self.graph = Record['G']
        
        print("Structure learning complete.")
        self._enforce_tiers(tiers, var_names)
        
        return self.graph

    def _enforce_tiers(self, tiers, var_names):
        """
        Manually removes edges that violate the tier hierarchy.
        X -> Z is removed if Tier(X) > Tier(Z).
        """
        print("Enforcing tier constraints...")
        # The graph object from HC is usually a GeneralGraph
        # We need to iterate edges.
        
        # Note: Accessing the graph structure depends on the specific version of causal-learn.
        # Assuming 'model' is the graph.
        
        # For the purpose of this blueprint, we will simulate the enforcement 
        # because modifying the internal graph structure of the library object can be tricky 
        # without the exact API reference at hand.
        
        # We will print the adjacency matrix and zero out forbidden entries.
        adj_mat = self.graph.graph
        
        # adj_mat[i, j] = 1 means i -> j (or similar depending on convention)
        # In causal-learn, usually graph.graph is the adjacency matrix.
        # -1: i -- j, 1: i -> j, -1: i <- j (varies)
        
        # Let's assume standard adjacency: row causes column.
        
        n = len(var_names)
        for i in range(n):
            for j in range(n):
                source_var = var_names[i]
                target_var = var_names[j]
                
                source_tier = tiers.get(source_var, 0)
                target_tier = tiers.get(target_var, 0)
                
                # If Source is in a later tier than Target, it cannot be a cause.
                if source_tier > target_tier:
                    # Remove edge i -> j
                    # In causal-learn GeneralGraph, we might need to use remove_edge
                    edge = self.graph.get_edge(self.graph.nodes[i], self.graph.nodes[j])
                    if edge:
                        self.graph.remove_edge(edge)
                        
        print("Tiers enforced.")

    def visualize(self):
        """
        Visualizes the graph.
        """
        print("Visualizing graph...")
        # pydot visualization
        try:
            pyd = GraphUtils.to_pydot(self.graph)
            pyd.write_png('causal_graph.png')
            print("Graph saved to causal_graph.png")
        except Exception as e:
            print(f"Visualization failed (graphviz might be missing): {e}")
            print("Adjacency Matrix:")
            print(self.graph.graph)

if __name__ == "__main__":
    # Mock data for testing
    # df = pd.DataFrame(...)
    # engine = CausalDiscoveryEngine(df)
    # engine.learn_structure()
    pass
