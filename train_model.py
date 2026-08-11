import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
import joblib

def generate_synthetic_data(num_samples=8000):
    np.random.seed(42)
    
    methane_ppm = np.random.uniform(0, 1500, num_samples)
    co_ppm = np.random.uniform(0, 300, num_samples)
    heart_rate_bpm = np.random.uniform(55, 150, num_samples)
    body_temp_c = np.random.uniform(35.5, 40.5, num_samples)

    labels = []
    
    for m, c, hr, temp in zip(methane_ppm, co_ppm, heart_rate_bpm, body_temp_c):
        if (m > 1000 and hr > 120) or (c > 200) or (temp > 39.0 and hr > 130) or (m > 1200):
            base_label = 2  # High Risk
        elif (m > 500) or (c > 100) or (hr > 110) or (temp > 38.0):
            base_label = 1  # Medium Risk
        else:
            base_label = 0  # Low Risk
            
        if np.random.rand() < 0.05:
            base_label = np.random.choice([0, 1, 2])
            
        labels.append(base_label)

    df = pd.DataFrame({
        'methane_ppm': methane_ppm,
        'co_ppm': co_ppm,
        'heart_rate_bpm': heart_rate_bpm,
        'body_temp_c': body_temp_c,
        'risk_class': labels
    })
    return df

def train_and_save():
    print("[+] Generating synthetic domain-informed dataset (8,000 samples)...")
    df = generate_synthetic_data()
    
    X = df[['methane_ppm', 'co_ppm', 'heart_rate_bpm', 'body_temp_c']]
    y = df['risk_class']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    print("[+] Training Random Forest Classifier...")
    model = RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    print("\n=== Model Performance Report ===")
    print(classification_report(y_test, y_pred, target_names=['Low Risk', 'Medium Risk', 'High Risk']))
    print("Confusion Matrix:")
    print(confusion_matrix(y_test, y_pred))

    joblib.dump(model, 'risk_model.pkl')
    print("\n[✔] Model successfully saved to risk_model.pkl")

if __name__ == '__main__':
    train_and_save()