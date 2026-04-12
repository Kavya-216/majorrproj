import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

class Evaluator:
    def __init__(self):
        pass
        
    def dcg_at_k(self, r, k):
        r = np.asarray(r, dtype=float)[:k]
        if r.size:
            return np.sum(r / np.log2(np.arange(2, r.size + 2)))
        return 0.

    def ndcg_at_k(self, r, k):
        dcg_max = self.dcg_at_k(sorted(r, reverse=True), k)
        if not dcg_max:
            return 0.
        return self.dcg_at_k(r, k) / dcg_max

    def precision_at_k(self, r, k):
        r = np.asarray(r, dtype=float)[:k]
        return np.mean(r)

    def calculate_ild(self, recommended_item_vectors):
        """
        Calculates Intra-List Diversity (ILD).
        Average dissimilarity (1 - cosine similarity) between all pairs of recommended items.
        """
        if len(recommended_item_vectors) < 2:
            return 0.0
            
        sim_matrix = cosine_similarity(recommended_item_vectors)
        # We want average of off-diagonal elements
        n = sim_matrix.shape[0]
        sum_sim = np.sum(sim_matrix) - n # Subtract diagonal (1s)
        avg_sim = sum_sim / (n * (n - 1))
        
        return 1.0 - avg_sim

    def calculate_homogeneity_score(self, recommended_item_vectors, user_history_vector):
        """
        Calculates Homogeneity Score.
        Average similarity of recommendations to user history.
        """
        if len(recommended_item_vectors) == 0 or user_history_vector is None:
            return 0.0
            
        # Reshape user vector if needed
        if user_history_vector.ndim == 1:
            user_history_vector = user_history_vector.reshape(1, -1)
            
        sims = cosine_similarity(recommended_item_vectors, user_history_vector)
        return np.mean(sims)

    def evaluate_session(self, recommendations, ground_truth_clicks, item_vectors, user_history_vector, k=10):
        """
        Evaluates a single session of recommendations.
        
        Args:
            recommendations (list): List of recommended item IDs (or indices).
            ground_truth_clicks (list): Binary list indicating if the item at that rank was clicked.
            item_vectors (list/array): Feature vectors corresponding to the recommendations.
            user_history_vector (array): User's history vector.
            k (int): Cutoff for metrics.
            
        Returns:
            dict: Dictionary of metrics.
        """
        ndcg = self.ndcg_at_k(ground_truth_clicks, k)
        precision = self.precision_at_k(ground_truth_clicks, k)
        ild = self.calculate_ild(item_vectors[:k])
        homogeneity = self.calculate_homogeneity_score(item_vectors[:k], user_history_vector)
        
        return {
            'NDCG@10': ndcg,
            'Precision@10': precision,
            'ILD': ild,
            'Homogeneity': homogeneity
        }
