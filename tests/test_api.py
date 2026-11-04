"""FastAPI End-to-End API Integration Tests."""

import time
import pytest
from fastapi.testclient import TestClient
from main import app


client = TestClient(app)


def test_health_endpoint():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "tesseract_installed" in data


def test_demo_pipeline_e2e():
    # 1. Trigger demo job
    demo_res = client.post("/api/demo")
    assert demo_res.status_code == 200
    job_id = demo_res.json()["job_id"]
    assert job_id is not None

    # 2. Wait for completion
    max_wait = 20
    start = time.time()
    completed = False

    while time.time() - start < max_wait:
        res = client.get(f"/api/jobs/{job_id}")
        assert res.status_code == 200
        status_data = res.json()
        if status_data["status"] == "completed":
            completed = True
            break
        elif status_data["status"] == "error":
            pytest.fail(f"Job failed with error: {status_data.get('error_message')}")
        time.sleep(0.5)

    assert completed is True

    # 3. Fetch results
    result_res = client.get(f"/api/jobs/{job_id}/result")
    assert result_res.status_code == 200
    result_data = result_res.json()

    assert "account" in result_data
    assert "transactions" in result_data
    assert "validation" in result_data
    assert "analytics" in result_data

    txns = result_data["transactions"]
    assert len(txns) == 10
    assert result_data["account"]["bank_name"] == "HDFC Bank"
    assert result_data["validation"]["is_reconciled"] is True

    # 4. Test category override
    first_txn_id = txns[0]["id"]
    override_res = client.post("/api/override", json={
        "job_id": job_id,
        "txn_id": first_txn_id,
        "category": "Custom Dining Expense"
    })
    assert override_res.status_code == 200
    assert override_res.json()["status"] == "success"

    # Verify category updated
    result_res2 = client.get(f"/api/jobs/{job_id}/result")
    assert result_res2.json()["transactions"][0]["category"] == "Custom Dining Expense"

    # 5. Test export CSV
    csv_res = client.get(f"/api/export/csv?job_id={job_id}")
    assert csv_res.status_code == 200
    assert csv_res.headers["content-type"].startswith("text/csv")
    assert len(csv_res.content) > 100

    # 6. Test export XLSX
    xlsx_res = client.get(f"/api/export/xlsx?job_id={job_id}")
    assert xlsx_res.status_code == 200
    assert "spreadsheetml" in xlsx_res.headers["content-type"]
    assert len(xlsx_res.content) > 1000

    # 7. Test page image preview
    img_res = client.get(f"/api/page-image/{job_id}/sample_1_hdfc.pdf/1?highlight=50,100,200,120")
    assert img_res.status_code == 200
    assert img_res.headers["content-type"] == "image/png"
    assert len(img_res.content) > 1000
