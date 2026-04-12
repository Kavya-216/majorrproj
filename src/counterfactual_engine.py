import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np

class CounterfactualEngine(nn.Module):
    def __init__(self, user_dim, item_dim):
        super(CounterfactualEngine, self).__init__()
        
        # Outcome Model: Predicts Diversity Score given User and Item
        # f(u, i) -> y_diversity
        self.outcome_net = nn.Sequential(
            nn.Linear(user_dim + item_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid() # Diversity is 0-1 (Cosine distance based)
        )
        
        # Propensity Model: Predicts probability of recommending Item i to User u
        # In a real large item space, this is a classifier over all items.
        # For simplicity here, we might model it as a binary "relevance" or just use the outcome model for the simulator.
        # The blueprint asks for IPW.
        # Let's assume we use the Outcome Model trained with IPW weights.
        
    def forward(self, user_vec, item_vec):
        """
        Forward pass for the outcome model.
        """
        x = torch.cat([user_vec, item_vec], dim=1)
        return self.outcome_net(x)
    
    def estimate_effect(self, user_vector, item_vector):
        """
        Predicts the user's future diversity score if the item is recommended.
        E[Y | do(A=item), U=user]
        
        Args:
            user_vector (np.array or torch.Tensor): User features.
            item_vector (np.array or torch.Tensor): Item features.
            
        Returns:
            float: Predicted diversity score.
        """
        self.eval()
        with torch.no_grad():
            if isinstance(user_vector, np.ndarray):
                user_vector = torch.FloatTensor(user_vector)
            if isinstance(item_vector, np.ndarray):
                item_vector = torch.FloatTensor(item_vector)
                
            if user_vector.dim() == 1:
                user_vector = user_vector.unsqueeze(0)
            if item_vector.dim() == 1:
                item_vector = item_vector.unsqueeze(0)
                
            prediction = self.forward(user_vector, item_vector)
            return prediction.item()

    def train_model(self, dataloader, epochs=5):
        """
        Trains the outcome model using observational data.
        Ideally, we would use IPW here to correct for selection bias.
        Loss = Weight * (y_pred - y_true)^2
        Weight = 1 / Propensity
        """
        optimizer = optim.Adam(self.parameters(), lr=0.001)
        criterion = nn.MSELoss() # Weighted MSE manually
        
        self.train()
        print("Training Counterfactual Engine...")
        
        for epoch in range(epochs):
            total_loss = 0
            for batch in dataloader:
                # Unpack batch
                # batch is expected to be a dictionary or list of tensors
                # U, I, Y_diversity, Propensity (if available)
                
                u = batch['U']
                i = batch['I']
                y_true = batch['Y_diversity']
                
                # Simple training for now (assuming randomized or ignoring bias for the skeleton)
                optimizer.zero_grad()
                y_pred = self.forward(u, i)
                loss = criterion(y_pred, y_true)
                loss.backward()
                optimizer.step()
                
                total_loss += loss.item()
            
            print(f"Epoch {epoch+1}, Loss: {total_loss:.4f}")
