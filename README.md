# Causal-Informed Recommendation System for Mitigating Echo Chambers

This project implements a recommendation engine that moves from reactive prediction to proactive intervention, optimizing for long-term interest diversity using Causal Inference and Reinforcement Learning. It aims to mitigate echo chambers by balancing user engagement with content diversity.

## Project Structure

- **`app.py`**: Streamlit dashboard for interactive visualization of the entire pipeline.
- **`src/data_loader.py`**: Loads and processes the MIND dataset, extracting User (U), Item (I), Action (A), and Outcome (Y) tensors.
- **`src/causal_discovery.py`**: Learns the Structural Causal Model (DAG) using the GES algorithm with tiered constraints.
- **`src/counterfactual_engine.py`**: Estimates the diversity reward using a neural network (simulating counterfactual outcomes).
- **`src/rl_agent.py`**: Implements an Actor-Critic RL agent with a composite reward function (Engagement + Diversity).
- **`src/evaluation.py`**: Calculates metrics like NDCG, Precision, ILD (Intra-List Diversity), and Homogeneity Score.
- **`src/mock_data.py`**: Generates realistic mock data with causal patterns and variance to simulate user behaviors when the full MIND dataset is unavailable.
- **`main.py`**: CLI entry point for the pipeline.

## Setup & Installation

1. **Create a Virtual Environment** (Recommended):
   ```bash
   python -m venv venv
   # Windows
   .\venv\Scripts\activate
   # Linux/Mac
   source venv/bin/activate
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   *Note: For the best graph visualization experience, install [Graphviz](https://graphviz.org/download/) and add it to your system PATH. If not installed, the app will fallback to a NetworkX-based visualization.*

## Running the Application

### Interactive Dashboard (Recommended)
Launch the Streamlit app to visualize the data, causal graph, and training progress:
```bash
streamlit run app.py
```

### Command Line Interface
Run the full pipeline in the terminal:
```bash
python main.py
```

## Project Workflow

The system operates in four main phases:

1.  **Data Loading & Processing**:
    -   Ingests user behavior logs and news metadata.
    -   Constructs feature tensors: User History (U), Item Features (I), Action/Rank (A), and Outcomes (Y_click, Y_diversity).

2.  **Causal Discovery**:
    -   Uses the **GES (Greedy Equivalence Search)** algorithm to learn the causal structure of the data.
    -   Applies **Tiered Constraints** to ensure logical directionality (e.g., User Features cause Clicks, not vice versa).
    -   *Goal*: Identify which features actually drive diversity and engagement.

3.  **Counterfactual Reasoning**:
    -   Trains a neural network to estimate the **Causal Effect** of recommending a specific item to a specific user.
    -   Predicts the *potential* diversity score if an item *were* to be recommended (Counterfactual).

4.  **Reinforcement Learning (RL)**:
    -   Trains an **Actor-Critic** agent.
    -   **Reward Function**: A weighted sum of Engagement (Click) and Diversity (Counterfactual Prediction).
    -   *Goal*: Learn a policy that maximizes this composite reward, breaking the filter bubble.

## Data & Mock Data Generation

The project is configured to automatically generate **mock data** (`data/news.tsv`, `data/behaviors.tsv`) if the MIND dataset is not found.

-   **Why Mock Data?** To allow the system to run immediately without downloading the large MIND dataset.
-   **Diversity & Variance**: The mock data generator creates diverse user preferences and news categories. It specifically introduces variance in subcategories and user history to ensure the data is statistically valid for Causal Discovery.
-   **Real Data**: To use the real [MIND Dataset](https://msnews.github.io/), download and place `news.tsv` and `behaviors.tsv` in the `data/` folder.

## Troubleshooting

-   **Graphviz Error**: If you see a message about "Graphviz binary not found", the app will automatically fallback to a NetworkX visualization. To fix this, install Graphviz on your OS and add it to your PATH.
-   **Singular Matrix Error**: This occurs if the dataset has columns with zero variance or perfect correlation. The current `mock_data.py` is tuned to prevent this.

## Key Features
- **Causal Discovery**: Uses the GES algorithm to discover causal relationships between User features, Item features, and Outcomes (Click, Diversity).
- **Counterfactual Reasoning**: Estimates the potential diversity impact of recommending specific items.
- **Reinforcement Learning**: Optimizes a policy that balances immediate clicks (Engagement) with long-term diversity (Echo Chamber Mitigation).
- **Visualization**: Interactive graphs and training curves via Streamlit.
