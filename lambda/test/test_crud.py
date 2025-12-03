import pytest
import boto3
from app.vpcops import VpcManager

@pytest.mark.asyncio
async def test_calculate_subnets(aws_mock):
    vpc = VpcManager(region_name="us-east-1")
    subnets = vpc._calculate_subnets("10.0.0.0/20", 4)
    assert len(subnets) == 4
    assert all(s.startswith("10.0.") for s in subnets)

@pytest.mark.asyncio
async def test_create_and_get_vpc(aws_mock):
    vpc = VpcManager(region_name="us-east-1")

    result = await vpc.create_vpc(
        vpc_cidr="10.1.0.0/16",
        subnet_count=2,
        vpc_tags=[{"Key": "Name", "Value": "TestVPC"}]
    )

    assert result is not None
    assert "vpc_id" in result
    vpc_id = result["vpc_id"]

    fetched = await vpc.get_vpc(vpc_id)
    assert fetched["vpc_id"] == vpc_id
    assert fetched["tags"][0]["Key"] == "Name"

@pytest.mark.asyncio
async def test_list_vpcs(aws_mock):
    vpc = VpcManager(region_name="us-east-1")
    await vpc.create_vpc("10.2.0.0/20", 2)
    vpcs = await vpc.list_vpcs()
    assert isinstance(vpcs, list)
    assert len(vpcs) > 0

@pytest.mark.asyncio
async def test_update_vpc_tags(aws_mock):
    vpc = VpcManager(region_name="us-east-1")
    created = await vpc.create_vpc("10.3.0.0/20", 2)
    vpc_id = created["vpc_id"]

    updated = await vpc.update_vpc(vpc_id, tags=[{"Key": "Env", "Value": "Dev"}])
    assert updated["updated_tags"][0]["Key"] == "Env"

@pytest.mark.asyncio
async def test_delete_vpc(aws_mock):
    vpc = VpcManager(region_name="us-east-1")
    created = await vpc.create_vpc("10.4.0.0/20", 2)
    vpc_id = created["vpc_id"]

    deleted = await vpc.delete_vpc(vpc_id)
    assert "deleted" in deleted["message"].lower()

    # Verify it no longer exists
    assert await vpc.get_vpc(vpc_id) is None


@pytest.mark.asyncio
async def test_create_vpc_invalid_cidr(aws_mock):
    """Should fail when an invalid CIDR is provided."""
    vpc_mgr = VpcManager(region_name="us-east-1")
    result = await vpc_mgr.create_vpc("X.X.X.X/16", 2)
    assert result is None

@pytest.mark.asyncio
async def test_get_vpc_not_found(aws_mock):
    """Should return None if the VPC ID does not exist in DynamoDB."""
    vpc_mgr = VpcManager(region_name="us-east-1")
    vpc = await vpc_mgr.get_vpc("non-existent-vpc")
    assert vpc is None

@pytest.mark.asyncio
async def test_update_vpc_nonexistent_id(aws_mock):
    """Should raise an exception when updating a non-existent VPC."""
    vpc_mgr = VpcManager(region_name="us-east-1")
    with pytest.raises(Exception):
        await vpc_mgr.update_vpc("vpc-invalid", [{"Key": "Env", "Value": "Dev"}])