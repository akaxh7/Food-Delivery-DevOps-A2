
from flask import Flask, request, jsonify, Response
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
import mlflow
from mlflow.tracking import MlflowClient
import numpy as np
import pickle
import os

app = Flask(__name__)

# MLflow configuration
mlflow.set_tracking_uri("http://mlflow:5000")
mlflow.set_experiment("House Price Prediction")
client = MlflowClient()

# Prometheus monitoring metrics
PREDICTION_COUNT = Counter(
    "house_price_predictions_total",
    "Total number of house price predictions"
)

# Sample house-area and price data
X = np.array([[500], [700], [900], [1100], [1300], [1500]])
y = np.array([100000, 140000, 180000, 220000, 260000, 300000])

# Train the model and track the experiment
model = RandomForestRegressor(n_estimators=10, random_state=42)

with mlflow.start_run(run_name="RandomForest-Demo") as run:
    model.fit(X, y)
    predictions = model.predict(X)

    mae = mean_absolute_error(y, predictions)

    mlflow.log_param("n_estimators", 10)
    mlflow.log_param("model", "RandomForestRegressor")
    mlflow.log_metric("training_mae", float(mae))

    # Save the model as an artifact
    os.makedirs("/tmp/model_artifact", exist_ok=True)
    model_path = "/tmp/model_artifact/model.pkl"

    with open(model_path, "wb") as file:
        pickle.dump(model, file)

    mlflow.log_artifact(model_path, artifact_path="model")

    # Register the model using the logged artifact
    model_name = "HousePriceRandomForest"

    try:
        client.create_registered_model(model_name)
    except Exception as error:
        if "already exists" not in str(error).lower():
            raise

    artifact_uri = f"{run.info.artifact_uri}/model/model.pkl"

    client.create_model_version(
        name=model_name,
        source=artifact_uri,
        run_id=run.info.run_id
    )

    print("Model training completed.")
    print(f"Training MAE: {mae:.2f}")
    print(f"MLflow Run ID: {run.info.run_id}")
    print(f"Registered model: {model_name}")

# Prediction endpoint
@app.route("/predict", methods=["GET"])
def predict():
    try:
        area = float(request.args.get("area", 1000))
        prediction = float(model.predict(np.array([[area]]))[0])

        PREDICTION_COUNT.inc()

        return jsonify({
            "area": area,
            "model": "RandomForestRegressor",
            "prediction": round(prediction, 2)
        })
    except (ValueError, TypeError):
        return jsonify({"error": "Please provide a valid numeric area"}), 400

# Prometheus metrics endpoint
@app.route("/metrics")
def metrics():
    return Response(
        generate_latest(),
        mimetype=CONTENT_TYPE_LATEST
    )

# Health check endpoint
@app.route("/health")
def health():
    return jsonify({"status": "healthy"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
