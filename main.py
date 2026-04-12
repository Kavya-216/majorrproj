import os
import pandas as pd
import numpy as np
import torch
from src.data_loader import MINDDataLoader
from src.causal_discovery import CausalDiscoveryEngine
from src.counterfactual_engine import CounterfactualEngine
from src.rl_agent import RLAgent, MockEnvironment
from src.evaluation import Evaluator
from src.mock_data import create_mock_mind_data

def main():
    # 1. Setup Environment & Data
    DATA_PATH = 'data'
    create_mock_mind_data(DATA_PATH)
    
    loader = MINDDataLoader(DATA_PATH)
    loader.load_data()
    loader.preprocess_item_features()
    loader.preprocess_user_features()
    
    # Generate Causal Dataset
    causal_df = loader.generate_causal_dataset(sample_size=5000)
    print("Causal Dataset Head:")
    print(causal_df.head())
    
    # 2. Causal Discovery
    print("\n--- Phase 2: Causal Discovery ---")
    discovery = CausalDiscoveryEngine(causal_df)
    # Note: Hill-Climbing might take time or require specific library versions.
    # We wrap it in try-except to allow flow to continue if library issues occur.
    try:
        graph = discovery.learn_structure()
        discovery.visualize()
    except Exception as e:
        print(f"Causal discovery skipped or failed: {e}")
        print("Proceeding with assumed structure.")

    # 3. Counterfactual Engine
    print("\n--- Phase 3: Counterfactual Engine ---")
    # Dimensions based on our simple preprocessing
    # User: Avg Category (1 dim) + Click Count (1 dim) = 2? 
    # Actually in data_loader we used simple features.
    # Let's check what we feed into the engine.
    # In the RL loop, we need vectors.
    
    # For simplicity in this main loop, we define dimensions:
    USER_DIM = 2 # Example: AvgCategory, ClickCount
    ITEM_DIM = 2 # CategoryCode, SubCategoryCode
    
    cf_engine = CounterfactualEngine(USER_DIM, ITEM_DIM)
    
    # Prepare training data for CF Engine
    # We need tensors from causal_df
    # U: [U_AvgCategory, U_ClickCount]
    # I: [I_Category, I_SubCategory]
    # Y: Y_Diversity
    
    u_data = causal_df[['U_AvgCategory', 'U_ClickCount']].values
    i_data = causal_df[['I_Category', 'I_SubCategory']].values
    y_data = causal_df['Y_Diversity'].values.reshape(-1, 1)
    
    # Create simple dataloader
    dataset = []
    batch_size = 64
    for i in range(0, len(u_data), batch_size):
        batch = {
            'U': torch.FloatTensor(u_data[i:i+batch_size]),
            'I': torch.FloatTensor(i_data[i:i+batch_size]),
            'Y_diversity': torch.FloatTensor(y_data[i:i+batch_size])
        }
        dataset.append(batch)
        
    cf_engine.train_model(dataset, epochs=3)
    
    # 4. Reinforcement Learning
    print("\n--- Phase 4: RL Agent Training ---")
    # State dim: User Vector (2) + Current Diversity (1) = 3
    STATE_DIM = USER_DIM + 1 
    ACTION_DIM = 10 # Assuming we select from 10 candidates (simplified)
    
    agent = RLAgent(STATE_DIM, ACTION_DIM, cf_engine, w=0.7)
    env = MockEnvironment(num_candidates=ACTION_DIM)
    
    # Training Loop
    episodes = 10
    for ep in range(episodes):
        state = env.reset()
        # Adjust state dimension to match agent expectation if needed
        # MockEnv returns 11 dims, we need 3. Let's fix MockEnv or slice here.
        state = state[:STATE_DIM] 
        
        done = False
        total_reward = 0
        
        rewards = []
        log_probs = []
        state_values = []
        
        while not done:
            action_idx, log_prob = agent.select_action(state)
            _, value = agent.model(torch.FloatTensor(state).unsqueeze(0))
            
            # Simulate environment step
            # In real scenario, we get the item vector for the selected action
            # Here we mock it
            mock_item_vec = np.random.rand(ITEM_DIM)
            mock_user_vec = state[:USER_DIM]
            
            next_state_full, click, done = env.step(action_idx)
            next_state = next_state_full[:STATE_DIM]
            
            # Calculate Reward
            reward = agent.calculate_reward(click, mock_user_vec, mock_item_vec)
            
            rewards.append(reward)
            log_probs.append(log_prob)
            state_values.append(value)
            
            state = next_state
            total_reward += reward
            
        loss = agent.update(rewards, log_probs, state_values)
        print(f"Episode {ep+1}: Total Reward = {total_reward:.4f}, Loss = {loss:.4f}")

    # 5. Evaluation
    print("\n--- Phase 5: Evaluation ---")
    evaluator = Evaluator()
    
    # Mock evaluation session
    recs = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] # Top 10 items
    clicks = [1, 0, 1, 0, 0, 0, 0, 0, 0, 0] # Ground truth
    item_vecs = np.random.rand(10, ITEM_DIM)
    user_hist = np.random.rand(ITEM_DIM)
    
    metrics = evaluator.evaluate_session(recs, clicks, item_vecs, user_hist)
    print("Evaluation Metrics:", metrics)
    
    print("\nProject Run Complete.")

if __name__ == "__main__":
    main()
