import os
import sys
import time
import subprocess
from datetime import datetime, timedelta, timezone
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

# --- CONFIGURATIONS ---
REGION_NAME = "us-east-1"
TARGET_TAG_KEY = "Name"
TARGET_TAG_VALUE = "Autoscaler-Testing-Server"

aws_config = Config(
    connect_timeout=5,
    read_timeout=5,
    retries={'max_attempts': 3} # Absorbs AWS API replication latency easily
)

ec2 = boto3.client('ec2', region_name=REGION_NAME, config=aws_config)

def discover_live_instance_id_by_tag():
    """Dynamically fetches the live EC2 Instance ID using infrastructure Name tags."""
    try:
        response = ec2.describe_instances(
            Filters=[
                {'Name': f'tag:{TARGET_TAG_KEY}', 'Values': [TARGET_TAG_VALUE]},
                {'Name': 'instance-state-name', 'Values': ['running']}
            ]
        )
        for reservation in response.get('Reservations', []):
            for instance in reservation.get('Instances', []):
                return instance.get('InstanceId')
        return None
    except Exception as e:
        print(f"[-] Automated instance tag discovery failed: {e}")
        return None

def get_current_volume_id_by_instance(instance_id):
    """Finds the correct secondary attached data volume on the target instance."""
    try:
        response = ec2.describe_instances(InstanceIds=[instance_id])
        mappings = response['Reservations'][0]['Instances'][0].get('BlockDeviceMappings', [])
        
        for device in mappings:
            dev_name = device.get('DeviceName', '').lower()
            if any(target in dev_name for target in ['sdf', 'xvdf', 'sdh', 'nvme1n1']):
                return device['Ebs']['VolumeId']
        return None
    except Exception as e:
        print(f"[-] Error tracking attached disk nodes: {e}")
        return None

def find_shrunken_volume_by_signature(old_volume_id):
    """
    DETERMINISTIC ASSET TRACER: Bypasses metadata tag indexing latency entirely.
    Directly queries the server's device attachment maps to isolate the new 1GB disk asset.
    """
    print("[*] Polling AWS regional registries for the active shrunken volume block layout...")
    
    for attempt in range(6):
        try:
            response = ec2.describe_volumes(
                Filters=[
                    {'Name': 'status', 'Values': ['in-use', 'available']}
                ]
            )
            volumes = response.get('Volumes', [])
            
            for vol in volumes:
                vol_id = vol['VolumeId']
                if vol_id == old_volume_id:
                    continue
                    
                if vol.get('VolumeType') == 'gp3' and vol.get('Size') < 20:
                    for attachment in vol.get('Attachments', []):
                        if attachment.get('Device') in ['/dev/sdh', 'sdh', '/dev/xvdh']:
                            return vol_id
                            
            print(f"[!] Storage virtualization map settling down. Retrying pass {attempt + 1}/6...")
            time.sleep(5)
            
        except Exception as e:
            print(f"[-] Hardware mapping registry analysis pass failed: {e}")
            
    return None

def get_tags_from_old_disk(old_volume_id):
    """DR Step 1: Capture compliance tags from the source volume before optimization."""
    print(f"[*] [DR Guard] Extracting backup metadata strings from source drive: {old_volume_id}")
    try:
        response = ec2.describe_volumes(VolumeIds=[old_volume_id])
        tags = response['Volumes'][0].get('Tags', [])
        print(f"[+] Successfully captured tags: {tags}")
        return tags
    except Exception as e:
        print(f"[-] Failed to extract tags from live reference source: {e}")
        return []

def run_daemon_until_cutover():
    """Step 2: Streams daemon.py logs asynchronously and ensures unbuffered real-time environment matching."""
    print("[*] Launching your bidirectional engine via daemon.py...")
    try:
        env_config = os.environ.copy()
        env_config["PYTHONIOENCODING"] = "utf-8"

        process = subprocess.Popen(
            [sys.executable, "-u", "daemon.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            env=env_config
        )

        cutover_detected = False

        for line in process.stdout:
            print(line, end="")
            
            if "Storage mapping cutover complete." in line:
                print("\n[SUCCESS] [Pipeline Alert] Optimization success signature captured from daemon stream output!")
                cutover_detected = True
                break
                
        print("[*] Shutting down telemetry daemon process monitoring cycles.")
        process.terminate()
        process.wait(timeout=5)
        
        return cutover_detected
    except KeyboardInterrupt:
        print("\n[USER INTERRUPTION DETECTED] Pipeline halted.")
        return False
    except Exception as e:
        print(f"[-] Execution thread crash: {e}")
        return False

def apply_tags_to_new_disk(new_volume_id, saved_tags):
    """DR Step 3: Inject compliance tags onto the recovered drive"""
    if not saved_tags:
        print("[!] No compliance tags discovered to replicate. Skipping infrastructure stitch.")
        return
    print(f"[*] [DR Healing] Post-migration check active. Stitching tags onto target volume: {new_volume_id}")
    try:
        ec2.create_tags(Resources=[new_volume_id], Tags=saved_tags)
        print("[SUCCESS] Disaster Recovery compliance chain successfully healed!")
    except ClientError as e:
        print(f"[-] DR Healing Failed: {e.response['Error']['Message']}")

def main():
    print("=== STARTING DR-SAFE AUTOMATED ORCHESTRATION PIPELINE ===")
    
    print("[*] Resolving live target EC2 server instance mapping dynamically via tags...")
    TARGET_INSTANCE_ID = discover_live_instance_id_by_tag()
    
    if not TARGET_INSTANCE_ID:
        print("[-] Critical Error: Could not locate a running 'Autoscaler-Testing-Server'.")
        print("[!] Ensure your Terraform environment is deployed and active. Terminating.")
        sys.exit(1)
        
    print(f"[+] Dynamic Target Resolved -> Instance ID: {TARGET_INSTANCE_ID}")
    
    old_disk_id = get_current_volume_id_by_instance(TARGET_INSTANCE_ID)
    if not old_disk_id:
        print("[-] Critical Error: Could not identify an attached data volume footprint mapping.")
        sys.exit(1)
        
    print(f"[+] Live Source Disk Identified -> Volume ID: {old_disk_id}")
        
    saved_tags = get_tags_from_old_disk(old_disk_id)
    migration_success = run_daemon_until_cutover()
    
    if migration_success:
        print("\n[*] [DR Discovery] Searching for newly created storage assets...")
        new_disk_id = find_shrunken_volume_by_signature(old_disk_id)
        
        if new_disk_id:
            print(f"[+] Found brand new shrunken storage asset: {new_disk_id}")
            apply_tags_to_new_disk(new_disk_id, saved_tags)
        else:
            print("[-] Bypassed: No new storage assets discovered in your AWS account.")
    else:
        print("[-] Bypassed: Tag recovery skipped because the core daemon failed or was stopped.")

if __name__ == "__main__":
    main()
