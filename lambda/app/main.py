import logging
import os
from mangum import Mangum
from fastapi import FastAPI, HTTPException, Query
from app.vpcops import VpcManager
from app.models import VpcResponse, CreateVpcRequest, UpdateVpcTagsRequest

# Configure global logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("vpc_api")

app = FastAPI(title="AWS VPC CRUD API", version="1.0.0")
handler = Mangum(app)

DB_REGION = os.environ["DB_REGION"]

# VPC Create, Update and Delete API Endpoints

@app.post("/create-vpc", response_model=VpcResponse)
async def create_vpc(payload: CreateVpcRequest):
    """Create a new VPC with optional subnets and tags."""
    logger.info(
        "API: Create VPC | CIDR=%s, subnets=%s",
        payload.vpc_cidr,
        payload.subnet_count
    )

    vpc_manager = VpcManager(region_name=payload.region)
    return await vpc_manager.create_vpc(
        payload.vpc_cidr,
        payload.subnet_count,
        payload.public_subnet_count,
        payload.vpc_tags,
        payload.subnet_tags
    )


@app.get("/list-vpc/{vpc_id}", response_model=VpcResponse)
async def get_vpc(vpc_id: str):
    """Retrieve a VPC by its ID."""
    logger.info("API: Get VPC | %s", vpc_id)

    vpc_manager = VpcManager(region_name=DB_REGION)
    vpc = await vpc_manager.get_vpc(vpc_id)

    if not vpc:
        raise HTTPException(status_code=404, detail="VPC not found")

    return vpc


@app.get("/list-all-vpcs")
async def list_vpcs():
    """List all VPC records stored in DynamoDB."""
    logger.info("API: List VPCs")

    vpc_manager = VpcManager(region_name=DB_REGION)
    return await vpc_manager.list_vpcs()


@app.put("/update-vpc/{vpc_id}")
async def update_vpc(vpc_id: str, payload: UpdateVpcTagsRequest):
    """Update tags for a VPC."""
    logger.info("API: Update VPC | %s", vpc_id)

    vpc_manager = VpcManager(region_name=payload.region)

    try:
        return await vpc_manager.update_vpc(vpc_id, payload.vpc_tags)
    except Exception as exc:
        logger.error("Error updating VPC %s: %s", vpc_id, exc)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while updating VPC"
        )


@app.delete("/delete-vpc/{vpc_id}")
async def delete_vpc(
    vpc_id: str,
    region: str = Query(..., description="AWS region, e.g., ap-south-1")
):
    """Delete a VPC and associated AWS resources."""
    logger.info("API: Delete VPC | %s", vpc_id)

    vpc_manager = VpcManager(region_name=region)
    result = await vpc_manager.delete_vpc(vpc_id)

    if not result:
        raise HTTPException(
            status_code=404,
            detail="No VPC Found or Failed to delete VPC"
        )

    return result
