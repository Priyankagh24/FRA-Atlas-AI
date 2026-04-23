from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
import numpy as np
from PIL import Image
import io
import tensorflow as tf
import os

app = FastAPI()

MODEL_PATH = "best_model.h5"
CLASS_NAMES = [
    "AnnualCrop", "Forest", "HerbaceousVegetation",
    "Highway", "Industrial", "Pasture", "PermanentCrop",
    "Residential", "River", "SeaLake"
]
IMG_SIZE = 64

model = tf.keras.models.load_model(MODEL_PATH)

@app.get("/")
def root():
    return {"status": "FRA Atlas ML Service running"}

@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    contents = await file.read()
    image = Image.open(io.BytesIO(contents)).convert("RGB")
    image = image.resize((IMG_SIZE, IMG_SIZE))
    arr = np.array(image) / 255.0
    arr = np.expand_dims(arr, axis=0)
    preds = model.predict(arr)
    class_idx = int(np.argmax(preds))
    confidence = float(np.max(preds))
    label = CLASS_NAMES[class_idx]
    return {"land_use_class": label, "confidence": confidence}