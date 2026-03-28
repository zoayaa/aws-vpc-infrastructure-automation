# AWS Infrastructure Automation Framework

A modular Python-based orchestration engine that deploys a production-grade, High-Availability (HA) VPC environment with automated EC2 provisioning.

## 🏗️ Architecture Overview
- **Networking:** Custom VPC with 4 subnets across 2 Availability Zones (Public/Private Tiering).
- **Gateways:** Internet Gateway (IGW) for public access and NAT Gateways for private subnet egress.
- **Security:** IAM Role with AmazonSSMManagedInstanceCore and tailored Security Groups.
- **Automation:** Boto3-based orchestration with exponential backoff for IAM propagation.

## 🚀 How to Use
1. Configure `config.yaml` with your desired region and CIDR blocks.
2. Run the Orchestrator:
   ```bash
   python3 orchestrator.py up
3. To teardown the entire stack: 
   python3 orchestrator.py down
