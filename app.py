import streamlit as st
import pandas as pd
import numpy as np
import torch
import matplotlib.pyplot as plt
import os
import io
from src.data_loader import MINDDataLoader
from src.causal_discovery import CausalDiscoveryEngine
from src.counterfactual_engine import CounterfactualEngine
from src.rl_agent import RLAgent, MockEnvironment
from src.evaluation import Evaluator
from src.mock_data import create_mock_mind_data

# Set page config
st.set_page_config(page_title="Causal-Informed Recommendation System", layout="wide")

st.title("Causal-Informed Recommendation System for Mitigating Echo Chambers")
st.markdown("""
This dashboard visualizes the pipeline of the recommendation system, from data loading to evaluation.
The goal is to move from reactive prediction to proactive intervention for diversity.
""")

# Sidebar for controls
st.sidebar.header("Configuration")
sample_size = st.sidebar.slider("Causal Dataset Sample Size", 1000, 10000, 5000)
cf_epochs = st.sidebar.slider("Counterfactual Training Epochs", 1, 10, 3)
rl_episodes = st.sidebar.slider("RL Training Episodes", 5, 50, 10)

# 1. Data Loading
st.header("1. Data Loading & Processing")
DATA_PATH = 'data'

@st.cache_data
def load_and_process_data():
    create_mock_mind_data(DATA_PATH)
    loader = MINDDataLoader(DATA_PATH)
    loader.load_data()
    loader.preprocess_item_features()
    loader.preprocess_user_features()
    return loader

with st.spinner("Loading and processing data..."):
    loader = load_and_process_data()
    st.success("Data loaded successfully!")

# Generate Causal Dataset
@st.cache_data
def get_causal_dataset(sample_size):
    return loader.generate_causal_dataset(sample_size=sample_size)

causal_df = get_causal_dataset(sample_size)
st.subheader("Causal Dataset Preview")
st.dataframe(causal_df.head())

# 2. Causal Discovery
st.header("2. Causal Discovery")
st.markdown("Learning the Structural Causal Model (DAG) from the data.")

if st.button("Run Causal Discovery"):
    discovery = CausalDiscoveryEngine(causal_df)
    try:
        with st.spinner("Running GES Algorithm..."):
            graph = discovery.learn_structure()
            st.success("Structure learned!")
            
            # Visualization
            st.subheader("Adjacency Matrix")
            st.write(discovery.graph.graph)
            
            # Try to generate image
            try:
                from causallearn.utils.GraphUtils import GraphUtils
                pyd = GraphUtils.to_pydot(discovery.graph)
                png_str = pyd.create_png()
                st.image(png_str, caption="Learned Causal Graph")
            except Exception as e:
                st.info(f"Graphviz binary not found. Using NetworkX for visualization instead.")
                try:
                    import networkx as nx
                    
                    # Create NetworkX graph from adjacency matrix
                    adj_mat = discovery.graph.graph
                    
                    # Get proper labels from the dataframe columns
                    labels = discovery.data.columns.tolist()
                    
                    G = nx.DiGraph()
                    
                    # Add nodes
                    for label in labels:
                        G.add_node(label)
                        
                    # Add edges
                    # causal-learn: 
                    # 1 at [i,j] and -1 at [j,i] => i -> j
                    # -1 at [i,j] and -1 at [j,i] => i -- j (undirected)
                    
                    rows, cols = adj_mat.shape
                    for i in range(rows):
                        for j in range(cols):
                            if adj_mat[i, j] == 1 and adj_mat[j, i] == -1:
                                G.add_edge(labels[i], labels[j])
                            elif adj_mat[i, j] == -1 and adj_mat[j, i] == -1:
                                if i < j: # Avoid duplicate
                                    G.add_edge(labels[i], labels[j], style='dotted')
                    
                    fig, ax = plt.subplots(figsize=(10, 6))
                    pos = nx.spring_layout(G, seed=42)
                    nx.draw(G, pos, with_labels=True, node_color='lightblue', 
                            node_size=2000, font_size=10, font_weight='bold', 
                            arrows=True, ax=ax, edge_color='gray')
                    st.pyplot(fig)
                    st.success("Causal Graph visualized successfully.")
                    
                except Exception as ex:
                    st.error(f"NetworkX visualization also failed: {ex}")
                
    except Exception as e:
        st.error(f"Causal discovery failed: {e}")

# 3. Counterfactual Engine
st.header("3. Counterfactual Engine Training")
st.markdown("Training the estimator to predict diversity outcomes.")

if st.button("Train Counterfactual Engine"):
    USER_DIM = 2
    ITEM_DIM = 2 # Reverted to 2 as I_SubCategory is back
    cf_engine = CounterfactualEngine(USER_DIM, ITEM_DIM)
    
    # Prepare data
    u_data = causal_df[['U_AvgCategory', 'U_ClickCount']].values
    i_data = causal_df[['I_Category', 'I_SubCategory']].values
    y_data = causal_df['Y_Diversity'].values.reshape(-1, 1)
    
    dataset = []
    batch_size = 64
    for i in range(0, len(u_data), batch_size):
        batch = {
            'U': torch.FloatTensor(u_data[i:i+batch_size]),
            'I': torch.FloatTensor(i_data[i:i+batch_size]),
            'Y_diversity': torch.FloatTensor(y_data[i:i+batch_size])
        }
        dataset.append(batch)
    
    # Custom training loop to capture loss for plotting
    optimizer = torch.optim.Adam(cf_engine.parameters(), lr=0.001)
    criterion = torch.nn.MSELoss()
    
    loss_history = []
    progress_bar = st.progress(0)
    
    for epoch in range(cf_epochs):
        total_loss = 0
        for batch in dataset:
            u = batch['U']
            i = batch['I']
            y_true = batch['Y_diversity']
            
            optimizer.zero_grad()
            y_pred = cf_engine(u, i)
            loss = criterion(y_pred, y_true)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        
        loss_history.append(total_loss)
        progress_bar.progress((epoch + 1) / cf_epochs)
    
    st.success("Training Complete!")
    
    # Plot Loss
    fig, ax = plt.subplots()
    ax.plot(range(1, cf_epochs + 1), loss_history, marker='o')
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Total Loss")
    ax.set_title("Counterfactual Engine Training Loss")
    st.pyplot(fig)
    
    # Store engine in session state for next step
    st.session_state['cf_engine'] = cf_engine

# 4. RL Agent Training
st.header("4. RL Agent Training")
st.markdown("Training the Actor-Critic agent to optimize for Engagement + Diversity.")

if 'cf_engine' in st.session_state:
    if st.button("Train RL Agent"):
        cf_engine = st.session_state['cf_engine']
        STATE_DIM = 3 # User(2) + Div(1)
        ACTION_DIM = 10
        
        agent = RLAgent(STATE_DIM, ACTION_DIM, cf_engine, w=0.7)
        env = MockEnvironment(num_candidates=ACTION_DIM)
        
        reward_history = []
        loss_history_rl = []
        progress_bar_rl = st.progress(0)
        
        ITEM_DIM = 2 # Reverted to 2
        USER_DIM = 2
        
        for ep in range(rl_episodes):
            state = env.reset()
            state = state[:STATE_DIM]
            
            done = False
            total_reward = 0
            
            rewards = []
            log_probs = []
            state_values = []
            
            while not done:
                action_idx, log_prob = agent.select_action(state)
                _, value = agent.model(torch.FloatTensor(state).unsqueeze(0))
                
                mock_item_vec = np.random.rand(ITEM_DIM)
                mock_user_vec = state[:USER_DIM]
                
                next_state_full, click, done = env.step(action_idx)
                next_state = next_state_full[:STATE_DIM]
                
                reward = agent.calculate_reward(click, mock_user_vec, mock_item_vec)
                
                rewards.append(reward)
                log_probs.append(log_prob)
                state_values.append(value)
                
                state = next_state
                total_reward += reward
            
            loss = agent.update(rewards, log_probs, state_values)
            reward_history.append(total_reward)
            loss_history_rl.append(loss)
            
            progress_bar_rl.progress((ep + 1) / rl_episodes)
            
        st.success("RL Training Complete!")
        
        # Plot Rewards
        col1, col2 = st.columns(2)
        
        with col1:
            fig1, ax1 = plt.subplots()
            ax1.plot(range(1, rl_episodes + 1), reward_history, color='green')
            ax1.set_xlabel("Episode")
            ax1.set_ylabel("Total Reward")
            ax1.set_title("RL Agent Cumulative Reward")
            st.pyplot(fig1)
            
        with col2:
            fig2, ax2 = plt.subplots()
            ax2.plot(range(1, rl_episodes + 1), loss_history_rl, color='red')
            ax2.set_xlabel("Episode")
            ax2.set_ylabel("Loss")
            ax2.set_title("RL Agent Loss")
            st.pyplot(fig2)
            
        # 5. Evaluation
        st.header("5. Evaluation")
        evaluator = Evaluator()
        
        # Mock evaluation session
        recs = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        clicks = [1, 0, 1, 0, 0, 0, 0, 0, 0, 0]
        item_vecs = np.random.rand(10, 2) # Reverted to 2
        user_hist = np.random.rand(2) # Reverted to 2
        
        metrics = evaluator.evaluate_session(recs, clicks, item_vecs, user_hist)
        
        st.subheader("Performance Metrics")
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("NDCG@10", f"{metrics['NDCG@10']:.4f}")
        col_m2.metric("Precision@10", f"{metrics['Precision@10']:.4f}")
        col_m3.metric("ILD (Diversity)", f"{metrics['ILD']:.4f}")
        col_m4.metric("Homogeneity", f"{metrics['Homogeneity']:.4f}")

else:
    st.info("Please train the Counterfactual Engine first to enable RL Agent training.")
