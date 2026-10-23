from fastapi.testclient import TestClient

from churn.api import app

client = TestClient(app)

NEW_CUSTOMER = {
    "gender": "Female", "senior_citizen": 0, "has_partner": 0, "has_dependents": 0,
    "tenure_months": 2, "phone_service": "Yes", "multiple_lines": "No",
    "internet_service": "Fiber optic", "online_security": "No", "online_backup": "No",
    "device_protection": "No", "tech_support": "No", "streaming_tv": "Yes",
    "streaming_movies": "Yes", "contract_type": "Month-to-month", "paperless_billing": 1,
    "payment_method": "Electronic check", "monthly_charges": 95.5, "total_charges": 191.0,
}


def test_model_beats_baseline(trained):
    assert trained["test_roc_auc"] > 0.80
    assert trained["test_lift_top_decile"] > 2.0


def test_health(trained):
    assert client.get("/health").json() == {"status": "ok", "model_loaded": True}


def test_predict_high_risk_profile(trained):
    body = client.post("/predict", json=NEW_CUSTOMER).json()
    assert 0 <= body["churn_probability"] <= 1
    assert body["risk_band"] == "high"


def test_loyal_profile_scores_lower(trained):
    loyal = {**NEW_CUSTOMER, "tenure_months": 60, "contract_type": "Two year",
             "tech_support": "Yes", "online_security": "Yes",
             "payment_method": "Bank transfer (automatic)", "total_charges": 5700.0}
    risky = client.post("/predict", json=NEW_CUSTOMER).json()["churn_probability"]
    safe = client.post("/predict", json=loyal).json()["churn_probability"]
    assert safe < risky


def test_invalid_input_rejected(trained):
    assert client.post("/predict", json={**NEW_CUSTOMER, "contract_type": "Forever"}).status_code == 422


def test_existing_customer_lookup(trained):
    body = client.get("/customers/7590-VHVEG/churn-risk").json()
    assert body["customer_id"] == "7590-VHVEG"
    assert client.get("/customers/NOPE/churn-risk").status_code == 404


def test_predictions_are_logged_and_monitored(trained):
    for _ in range(30):
        client.post("/predict", json=NEW_CUSTOMER)
    report = client.get("/monitoring/drift").json()
    assert report["n_predictions"] >= 30
    # Traffic of only brand-new month-to-month customers should be flagged as drift.
    assert report["features"]["contract_type"]["status"] == "investigate"


def test_agent_disabled_without_key(trained):
    assert client.post("/agent/ask", json={"question": "Which plan churns most?"}).status_code == 503


def test_invalid_monthly_charges_rejected(trained):
    assert client.post("/predict", json={**NEW_CUSTOMER, "monthly_charges": -5}).status_code == 422
