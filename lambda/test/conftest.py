import os
import pytest
import boto3
from moto import mock_aws
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(scope="function")
def aws_mock():
    """Mock AWS services EC2 & DynamoDB."""
    with mock_aws():
        # Create DynamoDB table for VpcManager
        dynamodb = boto3.client("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName=os.environ["TABLE_NAME"],
            KeySchema=[{"AttributeName": "VpcId", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "VpcId", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST"
        )
        yield

@pytest.fixture(scope="function")
def test_client(aws_mock):
    """FastAPI TestClient with AWS mocks applied."""
    return TestClient(app)
