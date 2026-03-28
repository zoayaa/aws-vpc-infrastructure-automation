import boto3
import sys
import time
from botocore.exceptions import ClientError
from config_loader import load_config, setup_logging, load_state, save_state

def check_drift(ec2_client, resource_type, resource_id):
    """Verifies if a resource recorded in state still exists in AWS."""
    try:
        if resource_type == "vpc":
            ec2_client.describe_vpcs(VpcIds=[resource_id])
        elif resource_type == "subnet":
            ec2_client.describe_subnets(SubnetIds=[resource_id])
        elif resource_type == "igw":
            ec2_client.describe_internet_gateways(InternetGatewayIds=[resource_id])
        return True
    except ClientError as e:
        if 'NotFound' in str(e):
            return False
        raise e

def rollback(ec2, state, logger):
    """The 'Safety Net': Cleans up only what was recorded in state."""
    logger.error("!!! CRITICAL FAILURE: Initiating automatic rollback !!!")
    
    # 1. NATs and EIPs
    if 'nat_gateways' in state:
        for az, info in state['nat_gateways'].items():
            try: ec2.delete_nat_gateway(NatGatewayId=info['nat_id'])
            except: pass
        
        logger.info("Rollback: Waiting for NATs to clear...")
        time.sleep(45) 
        
        for az, info in state['nat_gateways'].items():
            try: ec2.release_address(AllocationId=info['eip_alloc'])
            except: pass

    # 2. Subnets and Route Tables
    for tier in ['private_subnets', 'public_subnets']:
        if tier in state:
            for sub in state[tier]:
                try:
                    ec2.delete_subnet(SubnetId=sub['id'])
                    if 'rt_id' in sub: ec2.delete_route_table(RouteTableId=sub['rt_id'])
                except: pass

    # 3. IGW and VPC
    if 'igw_id' in state:
        try:
            ec2.detach_internet_gateway(InternetGatewayId=state['igw_id'], VpcId=state.get('vpc_id'))
            ec2.delete_internet_gateway(InternetGatewayId=state['igw_id'])
        except: pass

    if 'vpc_id' in state:
        try: ec2.delete_vpc(VpcId=state['vpc_id'])
        except: pass
    
    save_state({}) # Clear state ONLY after successful rollback
    logger.info("Rollback Complete.")

def main():
    cfg = load_config()
    logger = setup_logging("create_network")
    state = load_state()
    
    p_name = cfg['project']['name']
    region = cfg['project']['region']
    ec2 = boto3.client("ec2", region_name=region)

    def get_tags(name):
        return [{"Key": "Name", "Value": name}, {"Key": "Project", "Value": p_name}]

    try:
        # --- BLOCK 1: VPC ---
        vpc_id = state.get('vpc_id')
        if not vpc_id or not check_drift(ec2, "vpc", vpc_id):
            vpc = ec2.create_vpc(CidrBlock=cfg['network']['vpc_cidr'], 
                                TagSpecifications=[{"ResourceType": "vpc", "Tags": get_tags(f"{p_name}-vpc")}])
            vpc_id = vpc['Vpc']['VpcId']
            ec2.modify_vpc_attribute(VpcId=vpc_id, EnableDnsSupport={'Value': True})
            ec2.modify_vpc_attribute(VpcId=vpc_id, EnableDnsHostnames={'Value': True})
            state['vpc_id'] = vpc_id
            save_state(state)
            logger.info(f"SUCCESS: VPC {vpc_id} created.")
        
        # --- BLOCK 2: IGW ---
        igw_id = state.get('igw_id')
        if not igw_id or not check_drift(ec2, "igw", igw_id):
            igw = ec2.create_internet_gateway(TagSpecifications=[{"ResourceType": "internet-gateway", "Tags": get_tags(f"{p_name}-igw")}])
            igw_id = igw['InternetGateway']['InternetGatewayId']
            ec2.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
            state['igw_id'] = igw_id
            save_state(state)
            logger.info(f"SUCCESS: IGW {igw_id} attached.")

        # --- BLOCK 3: PUBLIC SUBNETS ---
        if not state.get('public_subnets'):
            rt = ec2.create_route_table(VpcId=vpc_id, TagSpecifications=[{"ResourceType": "route-table", "Tags": get_tags(f"{p_name}-public-rt")}])['RouteTable']['RouteTableId']
            ec2.create_route(RouteTableId=rt, DestinationCidrBlock='0.0.0.0/0', GatewayId=igw_id)
            
            subs = []
            for s_cfg in cfg['network']['public_subnets']:
                s = ec2.create_subnet(VpcId=vpc_id, CidrBlock=s_cfg['cidr'], AvailabilityZone=s_cfg['az'],
                                      TagSpecifications=[{"ResourceType": "subnet", "Tags": get_tags(s_cfg['name'])}])
                s_id = s['Subnet']['SubnetId']
                ec2.modify_subnet_attribute(SubnetId=s_id, MapPublicIpOnLaunch={'Value': True})
                ec2.associate_route_table(SubnetId=s_id, RouteTableId=rt)
                subs.append({"id": s_id, "az": s_cfg['az']})
            state['public_rt_id'] = rt
            state['public_subnets'] = subs
            save_state(state)

        # --- BLOCK 4: NAT GATEWAYS ---
        if not state.get('nat_gateways'):
            nats = {}
            for pub in state['public_subnets']:
                az = pub["az"]
                eip = ec2.allocate_address(Domain='vpc', TagSpecifications=[{"ResourceType": "elastic-ip", "Tags": get_tags(f"{p_name}-nat-eip-{az}")}])
                nat = ec2.create_nat_gateway(SubnetId=pub["id"], AllocationId=eip['AllocationId'], TagSpecifications=[{"ResourceType": "natgateway", "Tags": get_tags(f"{p_name}-nat-{az}")}])
                nats[az] = {"nat_id": nat['NatGateway']['NatGatewayId'], "eip_alloc": eip['AllocationId']}
            state['nat_gateways'] = nats
            save_state(state)
            
            logger.info("WAIT: NAT Gateways provisioning...")
            ec2.get_waiter('nat_gateway_available').wait(NatGatewayIds=[v['nat_id'] for v in nats.values()])

        # --- BLOCK 5: PRIVATE SUBNETS ---
        if not state.get('private_subnets'):
            pvt_subs = []
            for s_cfg in cfg['network']['private_subnets']:
                az = s_cfg['az']
                nat_id = state['nat_gateways'][az]['nat_id']
                rt = ec2.create_route_table(VpcId=vpc_id, TagSpecifications=[{"ResourceType": "route-table", "Tags": get_tags(f"{p_name}-private-rt-{az}")}])['RouteTable']['RouteTableId']
                ec2.create_route(RouteTableId=rt, DestinationCidrBlock='0.0.0.0/0', NatGatewayId=nat_id)
                s = ec2.create_subnet(VpcId=vpc_id, CidrBlock=s_cfg['cidr'], AvailabilityZone=az,
                                      TagSpecifications=[{"ResourceType": "subnet", "Tags": get_tags(s_cfg['name'])}])
                ec2.associate_route_table(SubnetId=s['Subnet']['SubnetId'], RouteTableId=rt)
                pvt_subs.append({"id": s['Subnet']['SubnetId'], "az": az, "rt_id": rt})
            state['private_subnets'] = pvt_subs
            save_state(state)
            logger.info("INFRASTRUCTURE COMPLETE.")

    except Exception as e:
        rollback(ec2, state, logger)
        sys.exit(1)

if __name__ == "__main__":
    main()
