import boto3
import time
import sys
import os
from config_loader import load_config, setup_logging, load_state, save_state

def main():
    cfg = load_config()
    logger = setup_logging("destroy_network")
    state = load_state()
    ec2 = boto3.client("ec2", region_name=cfg['project']['region'])
    iam = boto3.client("iam")

    if not state or 'vpc_id' not in state:
        logger.info("Nothing to destroy."); return

    vid = state['vpc_id']

    # --- PHASE 0: TERMINATE INSTANCE ---
    if 'instance_id' in state:
        try:
            iid = state['instance_id']
            logger.info(f"INTENT: Terminating Instance {iid}")
            ec2.terminate_instances(InstanceIds=[iid])
            ec2.get_waiter('instance_terminated').wait(InstanceIds=[iid])
            logger.info("SUCCESS: Instance terminated.")
        except Exception as e: logger.warning(f"Termination issue: {e}")

    # --- PHASE 1: IAM & KEYPAIR (Do this before wiping state) ---
    if 'instance_profile_name' in state:
        try:
            ip_name = state['instance_profile_name']
            role_name = state['iam_role_name']
            logger.info(f"DELETING: IAM Role {role_name}")
            iam.remove_role_from_instance_profile(InstanceProfileName=ip_name, RoleName=role_name)
            iam.delete_instance_profile(InstanceProfileName=ip_name)
            iam.detach_role_policy(RoleName=role_name, PolicyArn="arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore")
            iam.delete_role(RoleName=role_name)
        except Exception as e: logger.warning(f"IAM cleanup issue: {e}")

    if 'key_pair_name' in state:
        try:
            kn = state['key_pair_name']
            ec2.delete_key_pair(KeyName=kn)
            if os.path.exists(f"{kn}.pem"): os.remove(f"{kn}.pem")
            logger.info(f"SUCCESS: KeyPair {kn} removed.")
        except Exception as e: logger.warning(f"Key cleanup issue: {e}")

    # --- PHASE 2: NATs & EIPs ---
    if 'nat_gateways' in state:
        for az, info in state['nat_gateways'].items():
            try: ec2.delete_nat_gateway(NatGatewayId=info['nat_id'])
            except: pass
        while True:
            nats = ec2.describe_nat_gateways(Filters=[{'Name': 'vpc-id', 'Values': [vid]}])['NatGateways']
            if all(n['State'] == 'deleted' for n in nats): break
            logger.info("WAIT: Waiting for NATs to delete...")
            time.sleep(30)
        for az, info in state['nat_gateways'].items():
            try: ec2.release_address(AllocationId=info['eip_alloc'])
            except: pass

    # --- PHASE 3: SUBNETS & SECURITY GROUPS ---
    all_subs = state.get('private_subnets', []) + state.get('public_subnets', [])
    for sub in all_subs:
        try:
            ec2.delete_subnet(SubnetId=sub['id'])
            if 'rt_id' in sub: ec2.delete_route_table(RouteTableId=sub['rt_id'])
        except: pass

    if 'public_rt_id' in state:
        try: ec2.delete_route_table(RouteTableId=state['public_rt_id'])
        except: pass

    if 'security_group_id' in state:
        try: 
            ec2.delete_security_group(GroupId=state['security_group_id'])
            logger.info("SUCCESS: Security Group removed.")
        except: pass

    # --- PHASE 4: IGW & VPC ---
    if 'igw_id' in state:
        try:
            ec2.detach_internet_gateway(InternetGatewayId=state['igw_id'], VpcId=vid)
            ec2.delete_internet_gateway(InternetGatewayId=state['igw_id'])
        except: pass

    # Final VPC deletion with retries
    for i in range(10):
        try:
            ec2.delete_vpc(VpcId=vid)
            logger.info("SUCCESS: Full cleanup completed.")
            save_state({}) # FINALLY wipe state
            break
        except Exception as e:
            logger.info(f"RETRY: VPC busy ({e}). Waiting 20s... ({i+1}/10)")
            time.sleep(20)

if __name__ == "__main__":
    main()
