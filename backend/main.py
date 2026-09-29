import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd
import requests
import firebase_admin
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from pydantic import BaseModel

load_dotenv()
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
BASE = Path(__file__).parent

# ---------- Cloud (Firestore) ----------
cred = credentials.Certificate(BASE / "serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# ---------- ML model ----------
model = joblib.load(BASE / "model" / "laptop_model.pkl")
FEATURES = ["Company", "TypeName", "CpuBrand", "GpuBrand", "OpSys",
            "Inches", "Ram", "Weight", "Touchscreen", "IPS", "SSD", "HDD"]

# ---------- App ----------
app = FastAPI(title="Laptop Price Tracker API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

cache = {}  # {query: (timestamp, data)}


class Specs(BaseModel):
    Company: str
    TypeName: str
    Inches: float
    Ram: int
    Weight: float
    Touchscreen: int = 0
    IPS: int = 0
    SSD: int = 0
    HDD: int = 0
    CpuBrand: str
    GpuBrand: str
    OpSys: str
    live_price: Optional[float] = None  # optional, for the deal verdict


@app.get("/")
def home():
    return {"status": "ok"}


@app.get("/prices")
def get_prices(q: str = "laptop"):
    key = q.lower().strip()

    # serve from cache if fetched in the last 30 minutes
    if key in cache and time.time() - cache[key][0] < 1800:
        return cache[key][1]

    try:
        r = requests.get(
            "https://serpapi.com/search.json",
            params={"engine": "google_shopping", "q": q, "gl": "in", "hl": "en", "api_key": SERPAPI_KEY},
            timeout=20,
        )
        r.raise_for_status()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Price API error: {e}")

    items = []
    for it in r.json().get("shopping_results", [])[:10]:
        if it.get("extracted_price"):
            items.append({
                "title": it.get("title"),
                "price": it["extracted_price"],
                "source": it.get("source"),
                "link": it.get("product_link") or it.get("link"),
            })

    # save this fetch to the cloud (one shared timestamp per fetch)
    if items:
        try:
            ts = datetime.now(timezone.utc)
            batch = db.batch()
            for it in items:
                doc = {"query": key, "title": it["title"], "price": it["price"],
                       "source": it["source"], "timestamp": ts}
                batch.set(db.collection("price_history").document(), doc)
            batch.commit()
        except Exception as e:
            print("Firestore write failed:", e)  # don't break the API if cloud fails

    cache[key] = (time.time(), items)
    return items


@app.post("/predict")
def predict(specs: Specs):
    data = specs.model_dump(exclude={"live_price"})
    X = pd.DataFrame([data])[FEATURES]
    predicted = float(np.exp(model.predict(X)[0]))

    result = {"predicted_price": round(predicted)}
    if specs.live_price:
        ratio = specs.live_price / predicted
        if ratio < 0.9:
            verdict = "Good deal"
        elif ratio > 1.1:
            verdict = "Overpriced"
        else:
            verdict = "Fair price"
        result.update({
            "live_price": specs.live_price,
            "difference_percent": round((ratio - 1) * 100, 1),
            "verdict": verdict,
        })
    return result


@app.get("/history")
def history(q: str):
    key = q.lower().strip()
    docs = db.collection("price_history").where(filter=FieldFilter("query", "==", key)).limit(500).stream()
    rows = []
    for d in docs:
        row = d.to_dict()
        row["timestamp"] = row["timestamp"].isoformat()
        rows.append(row)
    rows.sort(key=lambda r: r["timestamp"])  # sorted here to avoid needing a Firestore index
    return rows