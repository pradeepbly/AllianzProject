import pytest

@pytest.mark.asyncio
async def test_create_vpc_api(test_client):
    payload = {
        "vpc_cidr": "10.10.0.0/16",
        "subnet_count": 2,
        "region": "us-east-1",
        "vpc_tags": [{"Key": "Name", "Value": "API-VPC"}]
    }
    response = test_client.post("/create-vpc", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["vpc_id"].startswith("vpc-")

@pytest.mark.asyncio
async def test_list_vpcs_api(test_client):
    response = test_client.get("/list-all-vpcs")
    print(response.json())
    assert response.status_code == 200
    vpcs = response.json()
    assert isinstance(vpcs, list)

@pytest.mark.asyncio
async def test_get_vpc_api(test_client):
    payload = {
        "vpc_cidr": "10.20.0.0/16",
        "subnet_count": 2,
        "region": "us-east-1"
    }
    create_resp = test_client.post("/create-vpc", json=payload)
    vpc_id = create_resp.json()["vpc_id"]

    resp = test_client.get(f"/list-vpc/{vpc_id}")
    assert resp.status_code == 200
    assert resp.json()["vpc_id"] == vpc_id

@pytest.mark.asyncio
async def test_update_vpc_api(test_client):

    payload = {
        "vpc_cidr": "10.30.0.0/16",
        "subnet_count": 2,
        "region": "us-east-1"
    }
    vpc_id = test_client.post("/create-vpc", json=payload).json()["vpc_id"]

    update_payload = {"vpc_tags": [{"Key": "Env", "Value": "QA"}], "region": "us-east-1"}
    resp = test_client.put(f"/update-vpc/{vpc_id}", json=update_payload)
    assert resp.status_code == 200
    assert resp.json()["updated_tags"][0]["Value"] == "QA"

@pytest.mark.asyncio
async def test_delete_vpc_api(test_client):
    payload = {
        "vpc_cidr": "10.40.0.0/16",
        "subnet_count": 2,
        "region": "us-east-1"
    }
    vpc_id = test_client.post("/create-vpc", json=payload).json()["vpc_id"]

    resp = test_client.delete(f"/delete-vpc/{vpc_id}?region=us-east-1")
    assert resp.status_code == 200
    assert "deleted" in resp.json()["message"].lower()

def test_get_vpc_api_not_found(test_client):
    """GET should return 404 if VPC does not exist."""
    response = test_client.get("/list-vpc/non-existent-vpc")
    assert response.status_code == 404
    assert response.json()["detail"] == "VPC not found"

def test_update_vpc_api_not_found(test_client):
    """PUT should return 500 if updating a non-existent VPC fails."""
    payload = {"region": "us-east-1", "vpc_tags": [{"Key": "Env", "Value": "Dev"}]}
    response = test_client.put("/update-vpc/non-existent-vpc", json=payload)
    assert response.status_code == 500

def test_delete_vpc_api_not_found(test_client):
    """DELETE should return 404 if the VPC does not exist."""
    response = test_client.delete("/delete-vpc/non-existent-vpc?region=us-east-1")
    assert response.status_code == 404
    assert "No VPC Found" in response.json()["detail"]

def test_create_vpc_api_invalid_payload(test_client):
    """POST should fail with 422 if payload is invalid."""
    response = test_client.post("/create-vpc", json={})
    assert response.status_code == 422