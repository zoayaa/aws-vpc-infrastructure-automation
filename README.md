# 🚀 Automated AWS VPC & EC2 Orchestration Framework

A production-grade, declarative Infrastructure-as-Code (IaC) engine built in Python. This framework programmatically provisions a highly available, two-tier AWS network foundation and deploys an automated web server with IAM-based management and SSM integration.

---

## 🏗️ Architecture

The environment features a **Public/Private subnet split across two Availability Zones (AZs)** for high availability, utilizing **NAT Gateways** for secure private egress.

---

## 🎯 Objective

To replace manual **"Click-Ops"** with a rigorous, idempotent deployment engine.

This tool handles:
- Networking dependencies lifecycle
- IAM Instance Profiles
- EC2 bootstrapping  

All while adhering to **AWS Well-Architected best practices**.

---

## 🛠️ Tech Stack

- **Language:** Python 3.12+
- **SDK:** AWS Boto3
- **Configuration:** YAML (Declarative Blueprint)
- **AWS Services:**
  - VPC
  - Multi-AZ Subnets
  - Internet Gateway (IGW)
  - NAT Gateways
  - IAM Roles
  - EC2
  - AWS Systems Manager (SSM)

---

## ✨ Key Features

### 🔹 Centralized Orchestration
A master `orchestrator.py` manages dependency flow between networking and compute layers.

### 🔹 Idempotency & State Tracking
Uses a `state.json` tracker to:
- Detect existing resources  
- Prevent duplicate billing  
- Avoid resource collisions  

### 🔹 IAM-First Security
- Eliminates hardcoded credentials  
- Uses IAM Roles & Instance Profiles  
- Enables **secure keyless access via SSM**

### 🔹 Resilient Deployment
Implements **Exponential Backoff retries** to handle AWS IAM propagation delays.

### 🔹 Graceful Cleanup
Recursive teardown ensures:
- NAT Gateways deleted first  
- Elastic IPs released  
- No orphaned billing resources  

## 📂 Repository Structure

```plaintext
aws-vpc-infrastructure-automation/
├── config.yaml               # Central declarative blueprint
├── config_loader.py          # YAML parser + IST logging
├── orchestrator.py           # Master pipeline controller
├── create_infrastructure.py  # Network layer engine
├── deploy_ec2.py             # Compute & IAM deployment
├── remove_infrastructure.py  # Safe teardown script
├── docs/
│   └── screenshots/          # Proof of Work
├── .gitignore                # सुरक्षा filter for state & keys
└── README.md

```

# 🔐 Required IAM Permissions

The executing IAM user should have:

AdministratorAccess
OR the following least-privilege policy:
```plaintext
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
```

## 🚀 Infrastructure Deployment & Verification

1️⃣ Provision Infrastructure

- Run the orchestrator to build the full stack:

    ```bash
    python3 orchestrator.py up
    ```
- Automatically skips already-created resources
- Ensures idempotent execution

2️⃣ Access the Application

- The framework bootstraps Nginx via EC2 User Data.
- Retrieve the Public IP
- Open in browser to verify deployment

3️⃣ IAM & Security Configuration

- IAM Role configured with:
- SSM Core policies
- Proper trust relationships

4️⃣ Safe Teardown

- Cleanly destroy all resources to avoid unexpected AWS costs:
    ```bash
    python3 orchestrator.py down
    ```
- Screenshots available in:
    - docs/screenshots/
    - Includes:
        - VPC topology
        - EC2 instance status
        - IAM configuration
        - Live web server verification

# Final Notes

This project demonstrates:

- Real-world Infrastructure Automation
- Production-grade AWS architecture design
- Strong focus on cost control, security, and resilience
