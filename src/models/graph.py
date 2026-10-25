from typing import List, Dict, Tuple
import torch

class PhysiologicalGraph:
    """
    Defines the physiological graphs for PhysioNet and WESAD datasets.
    Graph definitions are fixed prior knowledge and explicitly undirected.
    """
    
    # Pre-defined channel lists strictly matching Phase 4 and Phase 5 processing order
    PHYSIONET_CHANNELS = ["HR", "NISysABP", "NIDiasABP", "NIMAP", "Temp"]
    
    WESAD_CHANNELS = [
        "chest_ACC_0", "chest_ACC_1", "chest_ACC_2", "chest_ECG", "chest_EDA",
        "chest_EMG", "chest_Resp", "chest_Temp", "wrist_ACC_0", "wrist_ACC_1",
        "wrist_ACC_2", "wrist_BVP", "wrist_EDA", "wrist_TEMP"
    ]

    @staticmethod
    def get_physionet_edges() -> List[Tuple[str, str]]:
        """
        Returns the undirected physiological edges for PhysioNet.
        HR-Temp is exploratory.
        """
        return [
            ("NISysABP", "NIDiasABP"),
            ("NISysABP", "NIMAP"),
            ("NIDiasABP", "NIMAP"),
            ("HR", "Temp")  # Exploratory edge
        ]
        
    @staticmethod
    def get_wesad_edges() -> List[Tuple[str, str]]:
        """
        Returns the undirected physiological edges for WESAD.
        Maintains cross-device relationships.
        """
        return [
            ("chest_ECG", "wrist_BVP"),
            ("chest_EDA", "wrist_EDA"),
            ("chest_ACC_0", "wrist_ACC_0"),
            ("chest_ACC_1", "wrist_ACC_1"),
            ("chest_ACC_2", "wrist_ACC_2")
        ]

    @classmethod
    def build_edge_index(cls, dataset_name: str, add_self_loops: bool = True) -> torch.Tensor:
        """
        Constructs the PyTorch Geometric / adjacency edge_index tensor for a given dataset.
        Format: (2, num_edges), mapping source nodes to target nodes.
        Edges are undirected, meaning for each pair (u, v), both u->v and v->u are created.
        """
        dataset_name = dataset_name.lower()
        if dataset_name == "physionet":
            channels = cls.PHYSIONET_CHANNELS
            edges = cls.get_physionet_edges()
        elif dataset_name == "wesad":
            channels = cls.WESAD_CHANNELS
            edges = cls.get_wesad_edges()
        else:
            raise ValueError(f"Unknown dataset name: {dataset_name}")
            
        ch_to_idx = {ch: idx for idx, ch in enumerate(channels)}
        
        edge_list = []
        for src, dst in edges:
            u = ch_to_idx[src]
            v = ch_to_idx[dst]
            
            # Add bidirectional edges explicitly to simulate undirected graph
            edge_list.append((u, v))
            edge_list.append((v, u))
            
        if add_self_loops:
            for i in range(len(channels)):
                edge_list.append((i, i))
                
        # Remove duplicates just in case
        edge_list = list(set(edge_list))
        
        # Format for PyTorch Geometric (2, E)
        edge_index = torch.tensor(edge_list, dtype=torch.long).t().contiguous()
        return edge_index
