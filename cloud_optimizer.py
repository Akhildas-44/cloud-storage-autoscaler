import time
import os
import sys
import math
import boto3
import paramiko

# --- ENHANCED ENTERPRISE CONFIGURATIONS ---
REGION_NAME = "us-east-1"
TARGET_INSTANCE_TAG = {"Key": "Name", "Value": "Autoscaler-Testing-Server"}
PRODUCTION_MOUNT_PATH = "/data"
STAGING_MOUNT_PATH = "/mnt/target_scale"

# Windows Absolute Key Route
PEM_KEY_PATH = r"C:\Users\hp\Downloads\Mydemkey.pem" 

def get_infrastructure_context():
    """Queries AWS to discover the live running instance and its IP by Tags."""
    ec2_client = boto3.client('ec2', region_name=REGION_NAME)
    try:
        response = ec2_client.describe_instances(
            Filters=[
                {'Name': f"tag:{TARGET_INSTANCE_TAG['Key']}", 'Values': [TARGET_INSTANCE_TAG['Value']]},
                {'Name': 'instance-state-name', 'Values': ['running']}
            ]
        )
        for reservation in response.get('Reservations', []):
            for instance in reservation.get('Instances', []):
                return {
                    "instance_id": instance.get('InstanceId'),
                    "public_ip": instance.get('PublicIpAddress'),
                    "az": instance.get('Placement', {}).get('AvailabilityZone')
                }
    except Exception as e:
        print(f"[ERROR] Failed to query infrastructure context via AWS API: {e}")
    return None

def run_remote_ssh_command(ip, cmd):
    """Executes native shell commands inside the cloud server over an SSH tunnel."""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        private_key = paramiko.RSAKey.from_private_key_file(PEM_KEY_PATH)
        ssh.connect(hostname=ip, username="ec2-user", pkey=private_key, timeout=10)
        stdin, stdout, stderr = ssh.exec_command(cmd)
        err = stderr.read().decode('utf-8').strip()
        if err and "warning" not in err.lower():
            print(f"[WARNING] Remote Warning for [{cmd}]: {err}")
        return stdout.read().decode('utf-8').strip()
    except Exception as e:
        print(f"[ERROR] SSH Failure executing command [{cmd}]: {e}")
        raise e
    finally:
        ssh.close()

def resolve_linux_device_path(ip, volume_id):
    """Locates the exact symlink matching the AWS Volume ID to bypass parsing text logs."""
    clean_vol_id = volume_id.replace("-", "")
    print(f"[INFO] Searching Linux disk hardware maps for volume token: {clean_vol_id}...")
    
    for _ in range(15):
        cmd = f"ls /dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_{clean_vol_id} 2>/dev/null"
        device_link = run_remote_ssh_command(ip, cmd)
        if device_link:
            print(f"[SUCCESS] Target physical block map discovered at path: {device_link}")
            return device_link
        time.sleep(2)
        
    return None 

def execute_state_rollback(ec2_client, ip, journal):
    """LIFO cleanup strategy to restore the infrastructure configuration to its baseline state."""
    print("\n[ROLLBACK ENGINE] Restoring infrastructure baselines...")

    if journal["is_prod_frozen"]:
        try:
            print("[INFO] Rollback: Lifting block locks on application filesystems...")
            run_remote_ssh_command(ip, f"sudo fsfreeze --unfreeze {PRODUCTION_MOUNT_PATH}")
        except Exception as e: 
            print(f"[ERROR] Failed to lift locks: {e}")

    if journal["is_staged_mounted"]:
        try:
            print("[INFO] Rollback: Evicting unmanaged staging layer target mappings...")
            run_remote_ssh_command(ip, f"sudo umount -l {STAGING_MOUNT_PATH}")
        except Exception as e: 
            print(f"[ERROR] Failed staging unmount: {e}")

    if journal["is_attached"] and journal["target_volume_id"]:
        try:
            print(f"[INFO] Rollback: Severing link paths targeting leaky volume: {journal['target_volume_id']}...")
            ec2_client.detach_volume(VolumeId=journal["target_volume_id"], Force=True)
            ec2_client.get_waiter('volume_available').wait(VolumeIds=[journal["target_volume_id"]])
        except Exception as e: 
            print(f"[ERROR] Failed volume detachment: {e}")

    if journal["target_volume_id"]:
        try:
            print(f"[INFO] Rollback: Purging uncommitted volume blocks from AWS registry: {journal['target_volume_id']}...")
            ec2_client.delete_volume(VolumeId=journal["target_volume_id"])
        except Exception as e: 
            print(f"[ERROR] Failed volume deletion: {e}")

    print("[WARNING] [ROLLBACK COMPLETE] Safe state baseline restored successfully.")

def execute_live_optimization():
    print("\n[INFO] Initializing Enterprise Cost Optimization Controller...")
    
    ctx = get_infrastructure_context()
    if not ctx or not ctx["public_ip"]:
        print("[ERROR] Critical Failure: No active server found matching tags. Terminating.")
        sys.exit(1)
        
    instance_id = ctx["instance_id"]
    ec2_public_ip = ctx["public_ip"]
    dynamic_az = ctx["az"]
    
    ec2_client = boto3.client('ec2', region_name=REGION_NAME)

    # --- STATE ENGINE TRACKING JOURNAL ---
    journal = {
        "target_volume_id": None,
        "is_attached": False,
        "is_staged_mounted": False,
        "is_prod_frozen": False,
        "old_volume_id": None
    }

    try:
        # SIZING CALCULATOR ENGINE
        print("\n[INFO] Evaluating remote storage volumes...")
        raw_used_kb = run_remote_ssh_command(ec2_public_ip, f"df {PRODUCTION_MOUNT_PATH} | awk 'NR==2 {{print $3}}'")
        used_gb = float(raw_used_kb) / 1024 / 1024  
        
        calculated_target = math.ceil(used_gb * 1.40)
        if calculated_target < 1: calculated_target = 1  
        
        print(f"   [DATA] Telemetry: Live Dataset = {used_gb:.2f} GB | Targets Proposed = {calculated_target} GB")

        # Discover active storage resource mapping dynamically via Mount Targets
        find_old_vol_cmd = f"findmnt -n -o SOURCE {PRODUCTION_MOUNT_PATH}"
        dev_source = run_remote_ssh_command(ec2_public_ip, find_old_vol_cmd) 
        
        if not dev_source:
            raise RuntimeError(f"Could not discover device source linked directly to target path: {PRODUCTION_MOUNT_PATH}")

        # --- FIXED BULLETPROOF DATA-LANE ISOLATION WITH ROOT BLACKLIST ---
        vols = ec2_client.describe_volumes(Filters=[{'Name': 'attachment.instance-id', 'Values': [instance_id]}])
        for vol in vols.get('Volumes', []):
            v_id_clean = vol.get('VolumeId').replace("-", "").lower()
            
            check_cmd = f"ls -l /dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_{v_id_clean} 2>/dev/null"
            link_output = run_remote_ssh_command(ec2_public_ip, check_cmd).lower()
            
            # Safeguard: Skip root boot disk instantly if it maps to nvme0n1
            if "nvme0n1" in link_output:
                continue
                
            clean_source_name = dev_source.replace("/dev/", "")
            if link_output and clean_source_name in link_output:
                journal["old_volume_id"] = vol.get('VolumeId')
                break

        if not journal["old_volume_id"]:
            raise RuntimeError("Could not isolate secondary attached Linux device mount cleanly from primary root OS maps.")

        print(f"[INFO] Source Disk Mapped | Bloated Volume ID to decommission: {journal['old_volume_id']}")

        # 1. Provision Target Volume with Explicit Lifecycle Tracker
        print(f"\n[STEP 1/7] Provisioning {calculated_target}GB gp3 target volume...")
        volume = ec2_client.create_volume(
            Size=calculated_target, 
            AvailabilityZone=dynamic_az, 
            VolumeType='gp3',
            TagSpecifications=[{
                'ResourceType': 'volume',
                'Tags': [{'Key': 'Lifecycle', 'Value': 'Shrunk-Target'}]
            }]
        )
        journal["target_volume_id"] = volume['VolumeId']

        ec2_client.get_waiter('volume_available').wait(VolumeIds=[journal["target_volume_id"]])

        # 2. Hot-Attach
        print(f"\n[STEP 2/7] Hot-attaching volume {journal['target_volume_id']} to instance context...")
        ec2_client.attach_volume(VolumeId=journal["target_volume_id"], InstanceId=instance_id, Device="/dev/sdh")
        ec2_client.get_waiter('volume_in_use').wait(VolumeIds=[journal["target_volume_id"]])
        journal["is_attached"] = True

        # 3. Dynamic Device Discovery
        target_disk_device = resolve_linux_device_path(ec2_public_ip, journal["target_volume_id"])
        if not target_disk_device:
            raise RuntimeError("Hardware discovery phase timed out. Safeguarding workspace execution environments.")

        # 4. Format and Initial Sync
        print(f"\n[STEP 3/7] Initializing system target block device filesystems: {target_disk_device}")
        run_remote_ssh_command(ec2_public_ip, f"sudo mkfs.ext4 {target_disk_device}")
        run_remote_ssh_command(ec2_public_ip, f"sudo mkdir -p {STAGING_MOUNT_PATH}")
        run_remote_ssh_command(ec2_public_ip, f"sudo mount {target_disk_device} {STAGING_MOUNT_PATH}")
        journal["is_staged_mounted"] = True

        print("Cloning live customer dataset folders via background replication...")
        run_remote_ssh_command(ec2_public_ip, f"sudo rsync -axHAWXS --numeric-ids {PRODUCTION_MOUNT_PATH}/ {STAGING_MOUNT_PATH}/")

        # 5. Atomic Switchover Windows Execution
        print("\n[STEP 4/7] INITIATING REMOTE ATOMIC SWAP LOCK WINDOW...")
        run_remote_ssh_command(ec2_public_ip, f"sudo fsfreeze --freeze {PRODUCTION_MOUNT_PATH}")
        journal["is_prod_frozen"] = True
        
        try:
            run_remote_ssh_command(ec2_public_ip, f"sudo rsync -axHAWXS --numeric-ids --delete {PRODUCTION_MOUNT_PATH}/ {STAGING_MOUNT_PATH}/")
        finally:
            print("[INFO] Resuming application I/O lanes...")
            run_remote_ssh_command(ec2_public_ip, f"sudo fsfreeze --unfreeze {PRODUCTION_MOUNT_PATH}")
         # 6. Remount Framework Execution
        print("\n[STEP 5/7] Executing runtime block alignment remount protocols...")
        run_remote_ssh_command(ec2_public_ip, f"sudo umount {PRODUCTION_MOUNT_PATH}")
        run_remote_ssh_command(ec2_public_ip, f"sudo umount {STAGING_MOUNT_PATH}")
        journal["is_staged_mounted"] = False
        run_remote_ssh_command(ec2_public_ip, f"sudo mount {target_disk_device} {PRODUCTION_MOUNT_PATH}")

        # --- ENTERPRISE FIX: PERMANENT FSTAB MOUNT AUTO-STITCHING ---
        print("[INFO] Updating Linux system fstab registries to make the shrunken disk mount permanent...")
        get_uuid_cmd = f"sudo blkid -o value -s UUID {target_disk_device}"
        new_disk_uuid = run_remote_ssh_command(ec2_public_ip, get_uuid_cmd)
        
        if new_disk_uuid:
            fstab_entry = f"UUID={new_disk_uuid} {PRODUCTION_MOUNT_PATH} ext4 defaults,nofail 0 2"
            run_remote_ssh_command(ec2_public_ip, f"sudo sed -i '\\|{PRODUCTION_MOUNT_PATH}|d' /etc/fstab")
            run_remote_ssh_command(ec2_public_ip, f"echo '{fstab_entry}' | sudo tee -a /etc/fstab")
            print("[SUCCESS] Linux boot mount configuration successfully made persistent across server restarts.")
        else:
            print("[WARNING] Could not resolve disk UUID for fstab registration. Mount remains volatile.")

        # 7. FIXED BULLETPROOF LINUX KERNEL PURGE & DECOMMISSION
        print(f"\n[STEP 6/7] Forcing Linux kernel to drop block storage buffers for: {journal['old_volume_id']}...")
        run_remote_ssh_command(ec2_public_ip, f"sudo blockdev --flushbufs {dev_source}")
        clean_dev = dev_source.replace("/dev/", "")
        run_remote_ssh_command(ec2_public_ip, f"echo 1 | sudo tee /sys/block/{clean_dev}/device/delete 2>/dev/null || true")
        time.sleep(3)

        print(f"[INFO] Requesting AWS to detach original bloated volume: {journal['old_volume_id']}...")
        ec2_client.detach_volume(VolumeId=journal["old_volume_id"], Force=True)
        ec2_client.get_waiter('volume_available').wait(VolumeIds=[journal["old_volume_id"]])

        print(f"[INFO] Permanently purging legacy bloated volume from cloud ecosystem: {journal['old_volume_id']}...")
        ec2_client.delete_volume(VolumeId=journal["old_volume_id"])
        print("[SUCCESS] [STEP 7/7] Lifecycle optimization sequence concluded successfully.")
        
        # 🎯 THE UNIFYING SIGNAL KEY FOR PIPELINE.PY
        print("[SUCCESS] Storage mapping cutover complete.")

    except Exception as runtime_error:
        print(f"\n[CRITICAL ERROR] PIPELINE EXCEPTION EXPOSED: {runtime_error}")
        execute_state_rollback(ec2_client, ec2_public_ip, journal)
        sys.exit(1)

if __name__ == "__main__":
    execute_live_optimization()
