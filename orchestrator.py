import sys
import argparse
from config_loader import setup_logging

# Import the main functions from your verified scripts
import create_infrastructure
import deploy_ec2
import remove_infrastructure

def main():
    logger = setup_logging("orchestrator")
    
    parser = argparse.ArgumentParser(description="AWS Infrastructure Orchestrator")
    parser.add_argument("action", choices=["up", "down"], help="Build (up) or Destroy (down) the environment")
    args = parser.parse_args()

    if args.action == "up":
        logger.info("--- PIPELINE START: DEPLOYING FULL STACK ---")
        try:
            # Step 1: Network Foundation
            logger.info("PHASE 1: Building VPC Networking...")
            create_infrastructure.main()
            
            # Step 2: Compute Layer
            logger.info("PHASE 2: Deploying EC2 with IAM & SSM...")
            deploy_ec2.main()
            
            logger.info("--- PIPELINE SUCCESS: Environment is Ready! ---")
        except Exception as e:
            logger.error(f"PIPELINE FAILED: {e}")
            sys.exit(1)

    elif args.action == "down":
        logger.info("--- PIPELINE START: DESTROYING FULL STACK ---")
        try:
            # Single Step: The removal script handles dependencies internally
            remove_infrastructure.main()
            logger.info("--- PIPELINE SUCCESS: Environment is Clean! ---")
        except Exception as e:
            logger.error(f"PIPELINE FAILED: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
