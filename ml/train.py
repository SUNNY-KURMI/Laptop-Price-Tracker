import re
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error

EUR_TO_INR = 100  # approximate rate, update to the current one

# ---------- 1. Load ----------
df = pd.read_csv("laptop_price.csv", encoding="latin-1")

# ---------- 2. Clean ----------
df["Ram"] = df["Ram"].str.replace("GB", "").astype(int)
df["Weight"] = df["Weight"].str.replace("kg", "").astype(float)
df["Touchscreen"] = df["ScreenResolution"].str.contains("Touchscreen").astype(int)
df["IPS"] = df["ScreenResolution"].str.contains("IPS").astype(int)


def parse_storage(mem):
    """'128GB SSD +  1TB HDD' -> (ssd_gb, hdd_gb)"""
    ssd = hdd = 0.0
    for part in mem.split("+"):
        size = float(re.findall(r"[\d.]+", part)[0])
        if "TB" in part:
            size *= 1024
        if "SSD" in part or "Flash" in part:
            ssd += size
        else:  # HDD or Hybrid
            hdd += size
    return ssd, hdd


df[["SSD", "HDD"]] = df["Memory"].apply(lambda m: pd.Series(parse_storage(m)))


def cpu_brand(cpu):
    name = " ".join(cpu.split()[:3])
    if name in ("Intel Core i7", "Intel Core i5", "Intel Core i3"):
        return name
    return "Other Intel" if cpu.startswith("Intel") else "AMD"


df["CpuBrand"] = df["Cpu"].apply(cpu_brand)
df["GpuBrand"] = df["Gpu"].str.split().str[0]

# ---------- 3. Features / target ----------
CAT = ["Company", "TypeName", "CpuBrand", "GpuBrand", "OpSys"]
NUM = ["Inches", "Ram", "Weight", "Touchscreen", "IPS", "SSD", "HDD"]

X = df[CAT + NUM]
y = np.log(df["Price_euros"] * EUR_TO_INR)  # log of price in INR

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

prep = ColumnTransformer(
    [("cat", OneHotEncoder(handle_unknown="ignore"), CAT)],
    remainder="passthrough",  # numeric columns pass through unchanged
)

models = {
    "Linear Regression": LinearRegression(),
    "Random Forest": RandomForestRegressor(n_estimators=150, random_state=42, n_jobs=-1),
    "Gradient Boosting": GradientBoostingRegressor(random_state=42),
}

# ---------- 4. Train and compare ----------
results, best_name, best_r2, best_pipe = [], None, -1, None
for name, reg in models.items():
    pipe = Pipeline([("prep", prep), ("model", reg)])
    pipe.fit(X_train, y_train)
    pred = np.exp(pipe.predict(X_test))  # back to rupees
    actual = np.exp(y_test)
    r2 = r2_score(actual, pred)
    mae = mean_absolute_error(actual, pred)
    rmse = np.sqrt(mean_squared_error(actual, pred))
    results.append({"Model": name, "R2": round(r2, 3), "MAE (INR)": round(mae), "RMSE (INR)": round(rmse)})
    if r2 > best_r2:
        best_name, best_r2, best_pipe = name, r2, pipe

print(pd.DataFrame(results).to_string(index=False))
print("\nBest model:", best_name)

# ---------- 5. Save best model ----------
out = Path("../backend/model")
out.mkdir(parents=True, exist_ok=True)
joblib.dump(best_pipe, out / "laptop_model.pkl", compress=3)
print("Saved to", out / "laptop_model.pkl")