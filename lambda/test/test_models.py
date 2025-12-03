import pytest
from pydantic import ValidationError
from app.models import Tag, VpcResponse, CreateVpcRequest, UpdateVpcTagsRequest

def test_tag_model():
    tag = Tag(Key="Name", Value="TestVpc")
    assert tag.Key == "Name"
    assert tag.Value == "TestVpc"

def test_vpc_response_model():
    data = {
        "vpc_id": "vpc-123abc",
        "subnet_ids": ["subnet-1", "subnet-2"],
        "tags": [{"Key": "Env", "Value": "Dev"}],
        "region": "us-east-1",
        "igw": "igw-123abc",
        "route_tables": {"Public": "rtb-public", "Private": "rtb-private"}
    }
    vpc = VpcResponse(**data)
    assert vpc.vpc_id == "vpc-123abc"
    assert vpc.route_tables["Private"] == "rtb-private"

def test_create_vpc_request_valid():
    payload = {"vpc_cidr": "10.0.0.0/16", "subnet_count": 2, "region": "us-east-1"}
    req = CreateVpcRequest(**payload)
    assert req.subnet_count == 2

def test_create_vpc_request_invalid():
    with pytest.raises(ValidationError):
        CreateVpcRequest(subnet_count=2, region="us-east-1")

def test_update_vpc_tags_request():
    req = UpdateVpcTagsRequest(vpc_tags=[{"Key": "Env", "Value": "Prod"}], region="us-east-1")
    assert req.vpc_tags[0]["Key"] == "Env"
