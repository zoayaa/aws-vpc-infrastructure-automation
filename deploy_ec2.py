import boto3
import sys
import os
import json
import time
import botocore
from config_loader import load_config, setup_logging, load_state, save_state

def get_latest_ami(ec2_client):
    """Dynamically finds the latest Amazon Linux 2023 AMI."""
    filters = [
        {'Name': 'name', 'Values': ['al2023-ami-2023*-kernel-6.1-x86_64']},
        {'Name': 'state', 'Values': ['available']}
    ]
    images = ec2_client.describe_images(Owners=['137112412989'], Filters=filters)
    images_sorted = sorted(images['Images'], key=lambda x: x['CreationDate'], reverse=True)
    return images_sorted[0]['ImageId']

def main():
    cfg = load_config()
    logger = setup_logging("deploy_ec2_final")
    state = load_state()
    
    region = cfg['project']['region']
    p_name = cfg['project']['name']
    ec2 = boto3.client("ec2", region_name=region)
    iam = boto3.client("iam")

    if not state or 'vpc_id' not in state:
        logger.error("FATAL: No VPC found in state. Run create_infrastructure.py first.")
        sys.exit(1)

    # --- BLOCK 1: IAM ROLE & PROFILE ---
    role_name = f"{p_name}-ssm-role"
    profile_name = f"{p_name}-instance-profile"

    if 'instance_profile_name' not in state:
        try:
            logger.info("INTENT: Setting up IAM for SSM access...")
            policy = {"Version": "2012-10-17","Statement": [{"Effect": "Allow", "Principal": {"Service": "ec2.amazonaws.com"}, "Action": "sts:AssumeRole"}]}
            iam.create_role(RoleName=role_name, AssumeRolePolicyDocument=json.dumps(policy))
            iam.attach_role_policy(RoleName=role_name, PolicyArn="arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore")
            iam.create_instance_profile(InstanceProfileName=profile_name)
            iam.add_role_to_instance_profile(InstanceProfileName=profile_name, RoleName=role_name)
            state['iam_role_name'], state['instance_profile_name'] = role_name, profile_name
            save_state(state)
        except Exception as e: logger.error(f"IAM Failed: {e}"); sys.exit(1)

    # --- BLOCK 2: KEY PAIR GENERATION ---
    key_name = f"{p_name}-key"
    if 'key_pair_name' not in state:
        try:
            logger.info(f"INTENT: Generating Key Pair: {key_name}")
            kp = ec2.create_key_pair(KeyName=key_name)
            with open(f"{key_name}.pem", "w") as f: f.write(kp['KeyMaterial'])
            os.chmod(f"{key_name}.pem", 0o400)
            state['key_pair_name'] = key_name
            save_state(state)
        except Exception as e: logger.warning(f"Key Gen Failed: {e}")

    # --- BLOCK 3: SECURITY GROUP ---
    if 'security_group_id' not in state:
        try:
            sg = ec2.create_security_group(Description="SSH and HTTP", GroupName=f"{p_name}-sg", VpcId=state['vpc_id'])
            sid = sg['GroupId']
            ec2.authorize_security_group_ingress(GroupId=sid, IpProtocol='tcp', FromPort=22, ToPort=22, CidrIp='0.0.0.0/0')
            ec2.authorize_security_group_ingress(GroupId=sid, IpProtocol='tcp', FromPort=80, ToPort=80, CidrIp='0.0.0.0/0')
            state['security_group_id'] = sid
            save_state(state)
        except Exception as e: logger.error(f"SG Error: {e}"); sys.exit(1)
    else: sid = state['security_group_id']

    # --- BLOCK 4: RESILIENT LAUNCH (The Fix) ---
    if 'instance_id' not in state:
        ami_id = get_latest_ami(ec2)
        user_data = """#!/bin/bash
        dnf update -y
        dnf install -y nginx
        systemctl start nginx
        systemctl enable nginx
        echo "<h1>Automation Success: VPC + IAM + SSM + Nginx</h1>" > /usr/share/nginx/html/index.html
        """

        # Build the argument dictionary dynamically
        launch_args = {
            'ImageId': ami_id,
            'InstanceType': 't2.micro',
            'MinCount': 1, 'MaxCount': 1,
            'SubnetId': state['public_subnets'][0]['id'],
            'SecurityGroupIds': [sid],
            'IamInstanceProfile': {'Name': profile_name},
            'UserData': user_data,
            'TagSpecifications': [{"ResourceType": "instance", "Tags": [{"Key": "Name", "Value": f"{p_name}-server"}]}]
        }

        # The Fix: Only add KeyName if it is actually in our state
        if 'key_pair_name' in state:
            launch_args['KeyName'] = state['key_pair_name']
            logger.info(f"SECURITY: Attaching Key Pair '{state['key_pair_name']}' to launch args.")

        for attempt in range(6):
            try:
                logger.info(f"DEPLOY: Launching EC2 (Attempt {attempt+1}/6)")
                # Use ** to unpack the dictionary into the function
                instance = ec2.run_instances(**launch_args)
                state['instance_id'] = instance['Instances'][0]['InstanceId']
                save_state(state)
                logger.info(f"SUCCESS: Instance {state['instance_id']} is live!")
                break
            except botocore.exceptions.ClientError as e:
                if "InvalidParameterValue" in str(e) and "Instance Profile" in str(e):
                    wait = 2 ** attempt
                    logger.warning(f"WAIT: IAM Profile propagating... retrying in {wait}s")
                    time.sleep(wait)
                else: logger.error(f"FATAL: {e}"); sys.exit(1)
    else: logger.info(f"SKIP: Instance {state['instance_id']} already exists.")

if __name__ == "__main__":
    main()
