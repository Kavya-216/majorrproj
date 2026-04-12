import pandas as pd
import numpy as np
import os

def create_mock_mind_data(data_path):
    """
    Creates dummy news.tsv and behaviors.tsv for testing.
    """
    if not os.path.exists(data_path):
        os.makedirs(data_path)
        
    news_path = os.path.join(data_path, 'news.tsv')
    behaviors_path = os.path.join(data_path, 'behaviors.tsv')
    
    if os.path.exists(news_path) and os.path.exists(behaviors_path):
        print("Mock data already exists.")
        return

    print("Creating mock MIND data...")
    
    # Create News Data
    # NewsID, Category, SubCategory, Title, Abstract, URL, TitleEntities, AbstractEntities
    news_ids = [f'N{i}' for i in range(500)]
    categories = ['news', 'sports', 'finance', 'entertainment', 'tech', 'travel', 'food', 'health']
    # Shared subcategories to reduce correlation between Category and SubCategory
    shared_subcats = ['breaking', 'opinion', 'feature', 'general', 'report', 'interview']
    
    news_data = []
    news_info = {} # Map for quick lookup during behavior generation
    
    for nid in news_ids:
        cat = np.random.choice(categories)
        subcat = np.random.choice(shared_subcats)
        
        news_data.append([
            nid, cat, subcat, f'Title for {nid}', f'Abstract for {nid}', 
            f'http://url/{nid}', '[]', '[]'
        ])
        news_info[nid] = {'category': cat, 'subcategory': subcat}
        
    pd.DataFrame(news_data).to_csv(news_path, sep='\t', header=False, index=False)
    
    # Create Behaviors Data
    # ImpressionID, UserID, Time, History, Impressions
    behaviors_data = []
    
    # Define user preferences to create causal patterns
    user_ids = [f'U{i}' for i in range(100)]
    user_prefs = {uid: np.random.choice(categories) for uid in user_ids}
    
    for i in range(1000):
        uid = np.random.choice(user_ids)
        pref_cat = user_prefs[uid]
        
        # History: Users tend to have history in their preferred category
        hist_size = np.random.randint(0, 20)
        history_candidates = [nid for nid in news_ids if news_info[nid]['category'] == pref_cat]
        other_candidates = [nid for nid in news_ids if news_info[nid]['category'] != pref_cat]
        
        # 80% history from preferred category
        if len(history_candidates) > 0:
            n_pref = int(hist_size * 0.8)
            n_other = hist_size - n_pref
            
            hist_items = []
            if n_pref > 0:
                hist_items.extend(np.random.choice(history_candidates, size=min(n_pref, len(history_candidates)), replace=False))
            if n_other > 0:
                hist_items.extend(np.random.choice(other_candidates, size=min(n_other, len(other_candidates)), replace=False))
            
            np.random.shuffle(hist_items)
            history = ' '.join(hist_items)
        else:
            history = ''
        
        # Impressions: N1-0 N2-1 ...
        imps = []
        candidates = np.random.choice(news_ids, size=np.random.randint(5, 15), replace=False)
        
        for cand in candidates:
            # Causal Logic: Click probability depends on Category match + Randomness
            item_cat = news_info[cand]['category']
            
            base_prob = 0.05
            if item_cat == pref_cat:
                base_prob += 0.35 # 40% chance if matches preference
            
            # Add some subcategory influence (e.g., 'breaking' gets more clicks)
            if news_info[cand]['subcategory'] == 'breaking':
                base_prob += 0.1
                
            # Cap probability
            p_click = min(0.9, base_prob)
            
            label = np.random.choice([0, 1], p=[1-p_click, p_click])
            imps.append(f'{cand}-{label}')
            
        behaviors_data.append([
            i, uid, '11/11/2019 9:00:00 AM', history, ' '.join(imps)
        ])
        
    pd.DataFrame(behaviors_data).to_csv(behaviors_path, sep='\t', header=False, index=False)
    print("Mock data created.")
