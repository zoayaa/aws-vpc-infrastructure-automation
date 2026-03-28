🚀 Automated AWS VPC & EC2 Orchestration Framework
A production-grade, declarative Infrastructure-as-Code (IaC) engine built in Python. This framework programmatically provisions a highly available, two-tier AWS network foundation and deploys an automated web server with IAM-based management and SSM integration.

🏗️ Architecture
The environment features a Public/Private subnet split across two Availability Zones (AZs) for high availability, utilizing NAT Gateways for secure private egress.

🎯 Objective
To replace manual "Click-Ops" with a rigorous, idempotent deployment engine. This tool handles the complex lifecycle of networking dependencies, IAM Instance Profiles, and EC2 bootstrapping—adhering to AWS Well-Architected best practices.

🛠️ Tech Stack
Language: Python 3.12+

SDK: AWS Boto3

Configuration: YAML (Declarative Blueprint)

Services: VPC, Multi-AZ Subnets, IGW, NAT Gateways, IAM Roles, EC2, Systems Manager (SSM).

✨ Key Features
Centralized Orchestration: A master orchestrator.py manages the dependency flow between networking and compute layers.

Idempotency & State Tracking: Uses a state.json tracker to detect existing resources, preventing duplicate billing or resource collisions.

IAM-First Security: Replaces hardcoded keys with IAM Roles and Instance Profiles, enabling secure "Keyless" management via AWS Systems Manager (SSM).

Resilient Deployment: Implements Exponential Backoff retries to handle AWS IAM propagation delays during EC2 launches.

Graceful Cleanup: A recursive teardown script ensures expensive resources like NAT Gateways and Elastic IPs are released first to prevent orphaned charges.

📂 Repo Structure
Plaintext
aws-vpc-infrastructure-automation/
├── config.yaml              (The central declarative blueprint)
├── config_loader.py         (Utility for parsing YAML and setting IST logging)
├── orchestrator.py          (The master pipeline controller)
├── create_infrastructure.py  (The network layer engine)
├── deploy_ec2.py            (The compute & IAM deployment engine)
├── remove_infrastructure.py  (The safe teardown/cleanup script)
├── docs/
│   └── screenshots/         (Verified Proof of Work)
├── .gitignore               (Security filter for state and keys)
└── README.md
🔐 Required IAM Permissions
The executing IAM user requires AdministratorAccess or the following "Least Privilege" policy:

JSON
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ec2:*",
                "iam:CreateRole",
                "iam:AttachRolePolicy",
                "iam:CreateInstanceProfile",
                "iam:AddRoleToInstanceProfile",
                "iam:PassRole"
            ],
            "Resource": "*"
        }
    ]
}
🚀 Usage & Proof of Work
1. Provision Infrastructure
Run the orchestrator to build the full stack. The script will automatically skip resources that are already created.

Bash
python3 orchestrator.py up
VPC Resource Topology:

2. Access the Application
The script bootstraps Nginx automatically via User Data. Verify via the Public IP:

Live Web Server Verification:

3. IAM & Security Configuration
Verified IAM Role with SSM Core policies and trust relationships:

4. Safe Teardown
Wipe the environment cleanly to avoid unexpected AWS costs.

Bash
python3 orchestrator.py down
