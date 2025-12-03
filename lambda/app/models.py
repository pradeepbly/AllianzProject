from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class Tag(BaseModel):
    """
    Represents an AWS resource tag.

    Attributes:
        Key (str): The tag key (e.g., "Name").
        Value (str): The tag value associated with the key.
    """
    Key: str
    Value: str


class VpcResponse(BaseModel):
    """
    Response model containing normalized VPC metadata.
    """
    vpc_id: str = Field(..., description="Unique VPC ID (e.g. vp)")
    subnet_ids: List[str] = Field(..., description="List of associated subnet IDs")
    tags: Optional[List[Tag]] = Field(None, description="Tags applied to the VPC")
    region: str = Field(..., description="Region where the VPC exists")
    internet_gateway_id: Optional[str] = Field(
        None, description="Internet Gateway ID attached to the VPC"
    )
    route_tables: Dict[str, str] = Field(
        ..., description="Public and private route table IDs"
    )


class CreateVpcRequest(BaseModel):
    """
    Request body for VPC creation.
    """
    vpc_cidr: str = Field(..., description="CIDR block for VPC (e.g. 10.0.0.0/20)")
    subnet_count: int = Field(..., description="Total number of subnets to create")
    public_subnet_count: Optional[int] = Field(
        None, description="Number of public subnets (defaults to half)"
    )
    vpc_tags: Optional[List[Dict[str, str]]] = Field(
        None, description="Tags to apply to the VPC"
    )
    subnet_tags: Optional[List[Dict[str, str]]] = Field(
        None, description="Tags for individual subnets"
    )
    region: str = Field(..., description="AWS region (e.g. us-east-1)")


class UpdateVpcTagsRequest(BaseModel):
    """
    Request body for updating VPC tags.
    """
    vpc_tags: Optional[List[Dict[str, str]]] = Field(
        None, description="New tags for the VPC"
    )
    region: str = Field(..., description="AWS region (e.g. us-east-1)")