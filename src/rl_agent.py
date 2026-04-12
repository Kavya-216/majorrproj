import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import numpy as np

class ActorCritic(nn.Module):
    def __init__(self, state_dim, action_dim, hidden_dim=128):
        super(ActorCritic, self).__init__()
        
        # Actor: Outputs logits for actions (probabilities)
        self.actor = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, action_dim),
            nn.Softmax(dim=-1)
        )
        
        # Critic: Outputs value of the state
        self.critic = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1)
        )
        
    def forward(self, state):
        probs = self.actor(state)
        value = self.critic(state)
        return probs, value

class RLAgent:
    def __init__(self, state_dim, action_dim, counterfactual_engine, w=0.7):
        self.model = ActorCritic(state_dim, action_dim)
        self.optimizer = optim.Adam(self.model.parameters(), lr=0.001)
        self.cf_engine = counterfactual_engine
        self.w = w # Weight for engagement vs diversity
        
    def select_action(self, state):
        """
        Selects an action based on the current policy.
        """
        state = torch.FloatTensor(state).unsqueeze(0)
        probs, _ = self.model(state)
        
        # Sample action
        dist = torch.distributions.Categorical(probs)
        action = dist.sample()
        
        return action.item(), dist.log_prob(action)
    
    def calculate_reward(self, click_signal, user_vec, item_vec):
        """
        Composite Reward Function.
        r = w * r_engagement + (1-w) * r_diversity
        """
        # r_engagement: Binary click (1 or 0)
        r_engagement = click_signal
        
        # r_diversity: Predicted by Counterfactual Engine
        r_diversity = self.cf_engine.estimate_effect(user_vec, item_vec)
        
        reward = self.w * r_engagement + (1 - self.w) * r_diversity
        return reward

    def update(self, rewards, log_probs, state_values, gamma=0.99):
        """
        Updates the policy using Actor-Critic loss.
        """
        # Calculate returns
        returns = []
        R = 0
        for r in reversed(rewards):
            R = r + gamma * R
            returns.insert(0, R)
            
        returns = torch.tensor(returns)
        if len(returns) > 1:
            returns = (returns - returns.mean()) / (returns.std() + 1e-9) # Normalize
        else:
            returns = returns - returns.mean() # Center only
        
        policy_losses = []
        value_losses = []
        
        for log_prob, value, R in zip(log_probs, state_values, returns):
            advantage = R - value.item()
            
            # Actor loss
            policy_losses.append(-log_prob * advantage)
            
            # Critic loss
            value_losses.append(F.smooth_l1_loss(value, torch.tensor([[R]])))
            
        loss = torch.stack(policy_losses).sum() + torch.stack(value_losses).sum()
        
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        
        return loss.item()

# Mock Environment for Training Loop
class MockEnvironment:
    def __init__(self, num_candidates=10):
        self.num_candidates = num_candidates
        
    def reset(self):
        # Return random state: User Vector + Current Diversity
        # Assuming User Vector dim=10, Diversity dim=1
        return np.random.rand(11)
    
    def step(self, action):
        # Simulate click (random for now)
        click = np.random.choice([0, 1], p=[0.8, 0.2])
        
        # Next state
        next_state = np.random.rand(11)
        done = np.random.choice([True, False], p=[0.1, 0.9])
        
        return next_state, click, done
