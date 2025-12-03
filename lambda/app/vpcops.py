import logging
import os
import ipaddress
from typing import List, Dict, Optional
import boto3 # type: ignore


# Setup logging
logger = logging.getLogger("VpcManager")

logger.setLevel(logging.INFO)

if not logger.handlers:
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    )
    logger.addHandler(stream_handler)

logger.propagate = True

class VpcManager:
    """
    A manager class for performing CRUD operations on AWS VPC resources.

    This class handles the creation, retrieval, updating, and deletion of 
    VPCs along with associated AWS resources (subnets, route tables, IGWs).
    Metadata about created VPCs is persisted in DynamoDB.
    """

    def __init__(self, region_name: str):
        """
        Initialize the VpcManager with AWS EC2 and DynamoDB clients.

        Args:
            region_name (str): The AWS region where VPC operations will be performed.
        """
        self.region_name = region_name
        logger.info("Initializing VpcManager in region: %s", region_name)
        self.ec2 = boto3.client("ec2", region_name=region_name)
        dynamodb = boto3.resource("dynamodb", region_name=os.environ["DB_REGION"])
        self.table = dynamodb.Table(os.environ["TABLE_NAME"])

    def _normalize_vpc_record(self, record: dict) -> dict:
        """
        Normalize a raw DynamoDB VPC record to a standardized API response format.

        Args:
            record (dict): The DynamoDB record representing a VPC.

        Returns:
            Optional[dict]: Normalized VPC record with keys: 
                `vpc_id`, `subnet_ids`, `tags`, `region`, `igw`, `route_tables`.
                Returns None if the input record is empty.
        """
        if not record:
            return None
        return {
            "vpc_id": record["VpcId"],
            "subnet_ids": record.get("SubnetIds", []),
            "tags": record.get("Tags", []),
            "region": record.get("Region", self.region_name),
            "igw": record.get("igw"),
            "route_tables": record.get("RouteTables")
        }

    def _calculate_subnets(self, vpc_cidr: str, count: int) -> List[str]:
        """
        Calculate subnet CIDR blocks based on the provided VPC CIDR.

        Args:
            vpc_cidr (str): The CIDR block of the VPC (e.g., "10.0.0.0/16").
            count (int): Number of subnets to create.

        Returns:
            List[str]: A list of calculated subnet CIDR strings.

        Raises:
            ValueError: If the requested number of subnets cannot be created 
                        from the given VPC CIDR.
        """
        network = ipaddress.ip_network(vpc_cidr, strict=False)

        current_prefix = network.prefixlen
        max_subnets = 1
        while max_subnets < count and current_prefix < 32:
            current_prefix += 1 
            max_subnets = 2 ** (current_prefix - network.prefixlen)

        if max_subnets < count:
            raise ValueError(f"Cannot create {count} subnets from {vpc_cidr}")

        subnets = list(network.subnets(new_prefix=current_prefix))[:count]
        logger.info("Calculated %s subnets (/ %s) from %s", len(subnets), current_prefix, vpc_cidr)
        return [str(s) for s in subnets]

    async def _rollback_vpc(self, vpc_id: Optional[str], igw_id: Optional[str],
                            route_table_ids: List[Optional[str]], subnet_ids: List[str]):
        """
        Roll back partially created AWS resources in case of a failure.

        Args:
            vpc_id (Optional[str]): The ID of the VPC to delete (if created).
            igw_id (Optional[str]): The ID of the Internet Gateway to delete (if created).
            route_table_ids (List[Optional[str]]): List of Route Table IDs to delete.
            subnet_ids (List[str]): List of Subnet IDs to delete.

        Returns:
            None
        """
        
        for sid in subnet_ids:
            try:
                self.ec2.delete_subnet(SubnetId=sid)
                logger.info("Rollback: Deleted subnet %s", sid)
            except Exception as e:
                logger.warning("Rollback: Failed to delete subnet %s: %s", sid, e)

        for rt_id in route_table_ids:
            if rt_id:
                try:
                    self.ec2.delete_route_table(RouteTableId=rt_id)
                    logger.info("Rollback: Deleted route table %s", rt_id)
                except Exception as e:
                    logger.warning("Rollback: Failed to delete route table %s: %s", rt_id, e)

        if igw_id and vpc_id:
            try:
                self.ec2.detach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
                self.ec2.delete_internet_gateway(InternetGatewayId=igw_id)
                logger.info("Rollback: Detached and deleted IGW %s", igw_id)
            except Exception as e:
                logger.warning("Rollback: Failed to remove IGW %s: %s", igw_id, e)

        if vpc_id:
            try:
                self.ec2.delete_vpc(VpcId=vpc_id)
                logger.info("Rollback: Deleted VPC %s", vpc_id)
            except Exception as e:
                logger.warning("Rollback: Failed to delete VPC %s: %s", vpc_id, e)

    async def create_vpc(self, vpc_cidr: str, subnet_count: int,
                        public_subnet_count: Optional[int] = None,
                        vpc_tags: Optional[List[Dict[str, str]]] = None,
                        subnet_tags: Optional[List[Dict[str, str]]] = None) -> dict:
        """
        Create a new VPC with associated public/private subnets, route tables, 
        and an Internet Gateway. Persists metadata in DynamoDB.

        Args:
            vpc_cidr (str): CIDR block for the new VPC.
            subnet_count (int): Total number of subnets to create.
            public_subnet_count (Optional[int], default=None): 
                Number of subnets to mark as public. Defaults to half of subnet_count.
            vpc_tags (Optional[List[Dict[str, str]]], default=None): 
                Tags to assign to the VPC.
            subnet_tags (Optional[List[Dict[str, str]]], default=None): 
                Tags to assign to the subnets.

        Returns:
            Optional[dict]: Normalized VPC metadata on success, 
            or None if creation fails (rollback is triggered).
        """
        vpc_id = None
        igw_id = None
        rt_public_id = None
        rt_private_id = None
        subnet_ids = []

        try:
            logger.info("Creating VPC with CIDR %s", vpc_cidr)
            network = ipaddress.ip_network(vpc_cidr, strict=False) 
            vpc = self.ec2.create_vpc(CidrBlock=str(network))
            vpc_id = vpc["Vpc"]["VpcId"]
            self.ec2.modify_vpc_attribute(VpcId=vpc_id, EnableDnsSupport={"Value": True})
            if vpc_tags:
                self.ec2.create_tags(Resources=[vpc_id], Tags=vpc_tags)

            igw = self.ec2.create_internet_gateway()
            igw_id = igw["InternetGateway"]["InternetGatewayId"]
            self.ec2.attach_internet_gateway(VpcId=vpc_id, InternetGatewayId=igw_id)
            logger.info("Created & attached IGW %s", igw_id)

            rt_public = self.ec2.create_route_table(VpcId=vpc_id)
            rt_public_id = rt_public["RouteTable"]["RouteTableId"]
            self.ec2.create_tags(Resources=[rt_public_id], Tags=[{"Key": "Name", "Value": "Public-RT"}])
            self.ec2.create_route(RouteTableId=rt_public_id,
                                DestinationCidrBlock="0.0.0.0/0",
                                GatewayId=igw_id)

            rt_private = self.ec2.create_route_table(VpcId=vpc_id)
            rt_private_id = rt_private["RouteTable"]["RouteTableId"]
            self.ec2.create_tags(Resources=[rt_private_id], Tags=[{"Key": "Name", "Value": "Private-RT"}])

            public_count = public_subnet_count if public_subnet_count is not None else subnet_count // 2
            public_count = min(public_count, subnet_count)

            subnet_cidrs = self._calculate_subnets(str(network), subnet_count)
            for idx, cidr in enumerate(subnet_cidrs):
                subnet = self.ec2.create_subnet(VpcId=vpc_id, CidrBlock=cidr)
                subnet_id = subnet["Subnet"]["SubnetId"]
                subnet_ids.append(subnet_id)

                tag = subnet_tags[idx] if subnet_tags and idx < len(subnet_tags) else {"Key": "Name", "Value": f"Subnet-{idx+1}"}
                self.ec2.create_tags(Resources=[subnet_id], Tags=[tag])

                is_public = idx < public_count
                route_table_id = rt_public_id if is_public else rt_private_id
                self.ec2.associate_route_table(SubnetId=subnet_id, RouteTableId=route_table_id)
                logger.info("Subnet %s associated with %s RT", subnet_id, "Public" if is_public else "Private")

            item = {
                "VpcId": vpc_id,
                "Region": self.region_name,
                "SubnetIds": subnet_ids,
                "Tags": vpc_tags or [],
                "igw": igw_id,
                "RouteTables": {"Public": rt_public_id, "Private": rt_private_id}
            }
            self.table.put_item(Item=item)
            logger.info("VPC %s successfully created & persisted in DynamoDB", vpc_id)

            return self._normalize_vpc_record(item)

        except Exception as e:
            logger.error("Error during VPC creation: %s. Rolling back...", e)
            await self._rollback_vpc(vpc_id, igw_id, [rt_public_id, rt_private_id], subnet_ids)
            return None

    # ----------------------------------------------------------
    # List, Get, Update, Delete Operations
    # ----------------------------------------------------------

    async def get_vpc(self, vpc_id: str) -> Optional[dict]:
        """
        Retrieve a VPC record from DynamoDB.

        Args:
            vpc_id (str): The ID of the VPC to fetch.

        Returns:
            Optional[dict]: The VPC metadata if found, otherwise None.
        """
        logger.info("Fetching VPC %s from DynamoDB", vpc_id)
        res = self.table.get_item(Key={"VpcId": vpc_id})
        return self._normalize_vpc_record(res.get("Item"))

    async def list_vpcs(self) -> List[dict]:
        """
        List all VPCs stored in DynamoDB.

        Returns:
            List[dict]: A list of normalized VPC metadata records.
        """
        logger.info("Listing all VPCs from DynamoDB")
        res = self.table.scan()
        return [self._normalize_vpc_record(i) for i in res.get("Items", [])]

    async def update_vpc(self, vpc_id: str, tags: Optional[List[Dict[str, str]]] = None) -> dict:
        """
        Update tags for an existing VPC (merging with existing tags).

        Args:
            vpc_id (str): The ID of the VPC to update.
            tags (Optional[List[Dict[str, str]]], default=None): 
                List of tags to apply to the VPC.

        Returns:
            dict: A dictionary containing the VPC ID and the updated tags.
        """
        logger.info("Updating VPC %s with new tags", vpc_id)
        try:
            if tags:
                self.ec2.create_tags(Resources=[vpc_id], Tags=tags)
                self.table.update_item(
                    Key={"VpcId": vpc_id},
                    UpdateExpression="SET #tg = :val",
                    ExpressionAttributeNames={"#tg": "Tags"},
                    ExpressionAttributeValues={":val": tags}
                )

        except Exception as e:
            logger.error("Unexpected error during VPC update: %s", e)
            raise HTTPException(status_code=500, detail="Internal server error during VPC update.")
        
        return {"vpc_id": vpc_id, "updated_tags": tags}

    async def delete_vpc(self, vpc_id: str) -> Optional[dict]:
        """
        Delete a VPC along with its subnets, route tables, and Internet Gateway. 
        Removes the corresponding record from DynamoDB.

        Args:
            vpc_id (str): The ID of the VPC to delete.

        Returns:
            Optional[dict]: A message confirming deletion on success, 
            or None if the deletion fails.
        """
        logger.info("Attempting to delete VPC %s", vpc_id)
        record = await self.get_vpc(vpc_id)

        if not record:
            logger.warning("VPC %s not found in DynamoDB", vpc_id)
            return None

        for subnet_id in record["subnet_ids"]:
            try:
                self.ec2.delete_subnet(SubnetId=subnet_id)
                logger.info("Deleted Subnet %s", subnet_id)
            except Exception as e:
                logger.warning("Subnet %s deletion failed: %s", subnet_id, e)

        try:
            rt_response = self.ec2.describe_route_tables(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])
            for rt in rt_response["RouteTables"]:
                rt_id = rt["RouteTableId"]
                associations = rt.get("Associations", [])
                for assoc in associations:
                    if not assoc.get("Main"):
                        try:
                            self.ec2.disassociate_route_table(AssociationId=assoc["RouteTableAssociationId"])
                            logger.info("Disassociated Route Table %s", rt_id)
                        except Exception as e:
                            logger.warning("Could not disassociate RT %s: %s", rt_id, e)
                if not any(assoc.get("Main") for assoc in associations):
                    try:
                        self.ec2.delete_route_table(RouteTableId=rt_id)
                        logger.info("Deleted Route Table %s", rt_id)
                    except Exception as e:
                        logger.warning("Could not delete RT %s: %s", rt_id, e)
        except Exception as e:
            logger.warning("Failed to describe or delete route tables for %s: %s", vpc_id, e)

        try:
            igw_response = self.ec2.describe_internet_gateways(Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}])
            for igw in igw_response["InternetGateways"]:
                igw_id = igw["InternetGatewayId"]
                try:
                    self.ec2.detach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
                    logger.info("Detached IGW %s", igw_id)
                except Exception as e:
                    logger.warning("Could not detach IGW %s: %s", igw_id, e)
                try:
                    self.ec2.delete_internet_gateway(InternetGatewayId=igw_id)
                    logger.info("Deleted IGW %s", igw_id)
                except Exception as e:
                    logger.warning("Could not delete IGW %s: %s", igw_id, e)
        except Exception as e:
            logger.warning("Failed to describe/delete IGW for %s: %s", vpc_id, e)

        try:
            self.ec2.delete_vpc(VpcId=vpc_id)
            logger.info("Deleted VPC %s", vpc_id)
        except Exception as e:
            logger.error("Could not delete VPC %s: %s", vpc_id, e)

        try:
            self.table.delete_item(Key={"VpcId": vpc_id})
            logger.info("Removed VPC %s from DynamoDB", vpc_id)
        except Exception as e:
            logger.warning("Failed to delete VPC record %s from DynamoDB: %s", vpc_id, e)

        return {"message": f"VPC {vpc_id} deleted successfully"}
