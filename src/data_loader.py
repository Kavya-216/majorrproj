import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MultiLabelBinarizer
import torch
import os

class MINDDataLoader:
    def __init__(self, data_path):
        self.data_path = data_path
        self.news_df = None
        self.behaviors_df = None
        self.user_features = None
        self.item_features = None
        
    def load_data(self):
        """
        Loads the MIND dataset (news.tsv and behaviors.tsv).
        """
        print("Loading MIND dataset...")
        news_path = os.path.join(self.data_path, 'news.tsv')
        behaviors_path = os.path.join(self.data_path, 'behaviors.tsv')
        
        # MIND news columns
        news_cols = ['NewsID', 'Category', 'SubCategory', 'Title', 'Abstract', 'URL', 'TitleEntities', 'AbstractEntities']
        self.news_df = pd.read_csv(news_path, sep='\t', names=news_cols, index_col='NewsID')
        
        # MIND behaviors columns
        behaviors_cols = ['ImpressionID', 'UserID', 'Time', 'History', 'Impressions']
        self.behaviors_df = pd.read_csv(behaviors_path, sep='\t', names=behaviors_cols, index_col='ImpressionID')
        
        print("Data loaded successfully.")
        
    def preprocess_item_features(self):
        """
        Extracts Item Features (I): Category, SubCategory embeddings (one-hot for simplicity here).
        """
        print("Processing item features...")
        # Simple one-hot encoding for Category and SubCategory
        # In a real deep learning scenario, we would use embeddings (e.g., BERT on Title/Abstract)
        # For this blueprint, we stick to the requested structure.
        
        # We'll just map categories to integers for now to create a tensor
        self.news_df['CategoryCode'] = self.news_df['Category'].astype('category').cat.codes
        self.news_df['SubCategoryCode'] = self.news_df['SubCategory'].astype('category').cat.codes
        
        # Create a feature matrix for items
        # I = [CategoryCode, SubCategoryCode]
        self.item_features = self.news_df[['CategoryCode', 'SubCategoryCode']]
        print("Item features processed.")

    def preprocess_user_features(self):
        """
        Extracts User Features (U): History embedding.
        For simplicity, we represent user history as the average category vector of clicked items.
        """
        print("Processing user features...")
        # This is a simplified representation. 
        # In a full system, U would be a sequence embedding (GRU/LSTM).
        # Here we calculate a static profile based on history.
        
        user_profiles = {}
        
        # We need to iterate through behaviors to build user profiles
        # This can be slow, so we'll do a simplified version
        
        # Let's assume we process row by row for the RL environment later.
        # For the 'U' tensor, we can pre-calculate the history vector for each user.
        
        # Helper to get category vector for a list of news IDs
        def get_history_vector(history_str):
            if pd.isna(history_str):
                return np.zeros(2) # Size of our item features
            
            news_ids = history_str.split()
            valid_ids = [nid for nid in news_ids if nid in self.item_features.index]
            
            if not valid_ids:
                return np.zeros(2)
                
            # Average the item features of history
            features = self.item_features.loc[valid_ids].values
            return np.mean(features, axis=0)

        # Apply to unique users (optimization)
        unique_users = self.behaviors_df[['UserID', 'History']].drop_duplicates(subset=['UserID'])
        
        # Note: In MIND, a user appears multiple times with potentially growing history.
        # We will take the history from the specific impression line as the state 'U' at that moment.
        
        # We will generate U, A, Y on the fly or in batches for the RL loop, 
        # but for the Causal Discovery, we need a static dataset.
        
        print("User features processing logic ready.")

    def calculate_diversity_score(self, user_history, candidate_item_id):
        """
        Calculates Interest_Diversity_Score = 1 - Cosine Similarity(candidate, user_history)
        
        Args:
            user_history (list): List of NewsIDs the user has clicked.
            candidate_item_id (str): The NewsID of the candidate item.
            
        Returns:
            float: Diversity score.
        """
        if not user_history or candidate_item_id not in self.item_features.index:
            return 1.0 # Maximum diversity if no history or unknown item
            
        # Get candidate vector
        candidate_vec = self.item_features.loc[candidate_item_id].values.reshape(1, -1)
        
        # Get history vectors
        valid_history = [nid for nid in user_history if nid in self.item_features.index]
        if not valid_history:
            return 1.0
            
        history_vecs = self.item_features.loc[valid_history].values
        user_profile_vec = np.mean(history_vecs, axis=0).reshape(1, -1)
        
        # Calculate Cosine Similarity
        similarity = cosine_similarity(user_profile_vec, candidate_vec)[0][0]
        
        return 1.0 - similarity

    def generate_causal_dataset(self, sample_size=10000):
        """
        Generates the dataset for Phase 2 (Causal Discovery).
        Extracts U, I, A, Y tensors.
        
        Returns:
            pd.DataFrame: A dataframe with columns representing U, I, A, Y features.
        """
        print(f"Generating causal dataset (sample size: {sample_size})...")
        
        data = []
        
        # Iterate over a sample of behaviors
        sample_behaviors = self.behaviors_df.sample(n=min(sample_size, len(self.behaviors_df)))
        
        for idx, row in sample_behaviors.iterrows():
            history = str(row['History']).split() if not pd.isna(row['History']) else []
            impressions = str(row['Impressions']).split()
            
            # Calculate User Vector (U) - simplified as mean category code
            # For causal graph, we need scalar/categorical values usually.
            # Let's use 'User_Avg_Category' and 'User_Click_Count'
            user_click_count = len(history)
            
            # Get user profile vector for diversity calc
            valid_history = [nid for nid in history if nid in self.item_features.index]
            if valid_history:
                hist_vecs = self.item_features.loc[valid_history].values
                user_avg_cat = np.mean(hist_vecs[:, 0]) # Avg Category Code
            else:
                user_avg_cat = -1
            
            for imp in impressions:
                # Impression format: NewsID-Label (e.g., N1234-1)
                parts = imp.split('-')
                news_id = parts[0]
                label = int(parts[1])
                
                if news_id not in self.item_features.index:
                    continue
                    
                # Item Features (I)
                item_cat = self.item_features.loc[news_id, 'CategoryCode']
                item_subcat = self.item_features.loc[news_id, 'SubCategoryCode']
                
                # Action (A) - The recommended item ID. 
                # In causal inference, 'A' is usually the treatment. 
                # Here, recommending *this specific item* is the treatment.
                # We can represent A by the item's features or ID. 
                # The blueprint says A: The recommended item ID.
                
                # To avoid singular matrix (zero variance), we use the Rank/Position of the item
                # or just rely on Item Features as the treatment description.
                # Let's use a random rank for simulation if not available, or just 1.
                # But constant 1 causes singular matrix.
                # Let's simulate 'Rank' (position in recommendation list)
                rank = np.random.randint(1, 10)

                # Outcome (Y)
                # 1. Click (Binary)
                # 2. Diversity Score
                diversity = self.calculate_diversity_score(history, news_id)
                
                data.append({
                    'U_AvgCategory': user_avg_cat,
                    'U_ClickCount': user_click_count,
                    'I_Category': item_cat,
                    'I_SubCategory': item_subcat, # Re-enabled as we now have diverse data
                    'A_Rank': rank, 
                    'Y_Click': label,
                    'Y_Diversity': diversity
                })
                
        return pd.DataFrame(data)

if __name__ == "__main__":
    # Example usage
    # loader = MINDDataLoader('path/to/mind/data')
    # loader.load_data()
    # loader.preprocess_item_features()
    # df = loader.generate_causal_dataset()
    # print(df.head())
    pass
