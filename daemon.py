import time
import collections
import subprocess
import os
import sys
import math
import paramiko
import boto3

# --- PORTFOLIO SYSTEM CONFIGURATIONS ---
CHECK_INTERVAL = 1         # Fast sampling for fluid test validation
WINDOW_SIZE = 2            # Fast queue window for instant testing
LOW_DISK_THRESHOLD = 20.0  # Trigger downscale below 20%
HIGH_DISK_THRESHOLD = 80.0 # Trigger upscale above 80% (Prevents outages)
MONITOR_PATH = "/data"
REGION_NAME = "us-east-1"
TARGET_INSTANCE_TAG = {"Key": "Name", "Value": "Autoscaler-Testing-Server"}

# Windows Absolute Key Route
PEM_KEY_PATH = r"C:\Users\hp\Downloads\Mydemkey.pem"

def get_live_ec2_details():
    """Queries AWS to discover the live instance IP and ID."""
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
                    "ip": instance.get('PublicIpAddress'),
                    "id": instance.get('InstanceId')
                }
    except Exception as e:
        print(f"[ERROR] Daemon infrastructure query failed: {e}")
    return None

def get_disk_telemetry(ip, path):
    """Fetches both usage percentage and absolute size in GB from the remote host."""
    if not ip: 
        return None, None
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        private_key = paramiko.RSAKey.from_private_key_file(PEM_KEY_PATH)
        ssh.connect(hostname=ip, username="ec2-user", pkey=private_key, timeout=5)
        
        cmd = f"df --output=pcent,size {path} | tail -n 1"
        _, stdout, stderr = ssh.exec_command(cmd)
        raw_output = stdout.read().decode('utf-8').strip()
        
        if not raw_output:
            return None, None 
            
        parts = raw_output.split()
        if not parts or len(parts) < 2:
            return None, None
            
        pct = float(parts[0].replace('%', '').strip())
        size_gb = math.ceil(float(parts[1]) / 1024 / 1024)
        return pct, size_gb
    except Exception as e:
        print(f"[WARNING] Telemetry collection link lost: {e}")
        return None, None
    finally:
        ssh.close()

def trigger_upscale_native(instance_id, current_size_gb):
    """Handles high-utilization emergency scaling by modifying the AWS volume directly."""
    ec2_client = boto3.client('ec2', region_name=REGION_NAME)
    try:
        vols = ec2_client.describe_volumes(Filters=[{'Name': 'attachment.instance-id', 'Values': [instance_id]}])
        target_vol_id = None
        for vol in vols.get('Volumes', []):
            for att in vol.get('Attachments', []):
                if att.get('Device') in ['/dev/sdf', 'sdf', '/dev/xvdf', '/dev/sdh', 'sdh']:
                    target_vol_id = vol.get('VolumeId')
                    break
        
        if not target_vol_id:
            print("[ERROR] Upscale failed: Could not map data volume asset mapping handles.")
            return False

        new_target_size = int(current_size_gb * 2) 
        print(f"\n[EMERGENCY SCALE-UP] Disk utilization critically high! Requesting AWS to expand {target_vol_id} to {new_target_size}GB...")
        
        ec2_client.modify_volume(VolumeId=target_vol_id, Size=new_target_size)
        print("[SUCCESS] AWS Volume modification request accepted. Storage lane expanding dynamically in background.")
        return True
    except Exception as e:
        print(f"[ERROR] Native AWS modification layer failure: {e}")
        return False

def execute_autoscaler_sync():
    """Executes the cloud optimizer in real-time streaming output to console."""
    print("\n[WARNING] TELEMETRY ALERT: Storage underutilization sustained. Triggering Optimizer...")
    current_dir = os.path.dirname(os.path.abspath(__file__))
    optimizer_path = os.path.join(current_dir, "cloud_optimizer.py")
    
    try:
        process = subprocess.Popen(
            [sys.executable, optimizer_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8"
        )

        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                print(f"   [Optimizer Out]: {line.strip()}")

        return process.wait() == 0
    except Exception as e:
        print(f"[ERROR] Subprocess runtime pipeline linkage broken: {e}")
        return False

def main():
    print("[INFO] Continuous Telemetry Daemon Core Online [Dual-Threshold Mode Enabled].")
    metrics_history = collections.deque(maxlen=WINDOW_SIZE)

    while True:
        try:
            ctx = get_live_ec2_details()
            if not ctx or not ctx["ip"]:
                print("[INFO] Waiting for targeted cloud server context tags to register...")
                time.sleep(CHECK_INTERVAL)
                continue
                
            live_ip = ctx["ip"]
            instance_id = ctx["id"]
            
            current_usage, current_size = get_disk_telemetry(live_ip, MONITOR_PATH)
            
            if current_usage is None:
                print("[INFO] Metrics stale due to infrastructure communication errors. Retrying...")
                time.sleep(CHECK_INTERVAL)
                continue

            metrics_history.append(current_usage)
            moving_average = sum(metrics_history) / len(metrics_history)
            print(f"[INFO] Daemon Live Analytics [IP: {live_ip}] -> Usage: {current_usage:.2f}% | Size: {current_size}GB | Moving Average: {moving_average:.2f}% ({len(metrics_history)}/{WINDOW_SIZE} samples)")
            
            # --- CONDITION 1: EMERGENCY SCALE-UP RULE ---
            if current_usage > HIGH_DISK_THRESHOLD:
                print(f"\n[HIGH UTILITY CRITICAL WARNING]: Single check hit {current_usage:.2f}%!")
                if trigger_upscale_native(instance_id, current_size):
                    print("[INFO] Scale-up triggered. Flushing historic queue metrics to absorb state changes.")
                    metrics_history.clear()
                    time.sleep(120) 
                continue

            # --- CONDITION 2: DYNAMIC SHRINK-DOWN RULE ---
            if len(metrics_history) == WINDOW_SIZE and moving_average < LOW_DISK_THRESHOLD:
                if current_size <= 1:
                    print(f"\n[INFO] Underutilization sustained at {moving_average:.2f}%, but drive is already at the absolute minimum baseline of {current_size}GB. Skipping shrink pass.")
                    metrics_history.clear()
                    time.sleep(10) 
                    continue

                success = execute_autoscaler_sync()
                
                if success:
                    print("\n[INFO] Downscale optimization complete. Clearing queues for subsequent monitoring cycles.")
                else:
                    print("\n[WARNING] Optimization engine failed. Postponing next cycle for system stabilization.")
                
                metrics_history.clear()
                time.sleep(10) 
                
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            print("\nStopping Local Telemetry Daemon console.")
            break

if __name__ == "__main__":
    main()
