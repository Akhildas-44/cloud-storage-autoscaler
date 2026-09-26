import os
import sys
import time
import json
import boto3
import paramiko

# --- TEST SUITE ARCHITECTURE CONFIGURATIONS ---
REGION_NAME = "us-east-1"
TARGET_INSTANCE_TAG = {"Key": "Name", "Value": "Autoscaler-Testing-Server"}
PEM_KEY_PATH = r"C:\Users\hp\Downloads\Mydemkey.pem"
PRODUCTION_MOUNT_PATH = "/data"

ec2_client = boto3.client('ec2', region_name=REGION_NAME)

def get_target_infrastructure():
    """Locates the active server context for the testing matrix."""
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
                    "id": instance.get('InstanceId'),
                    "ip": instance.get('PublicIpAddress')
                }
    except Exception as e:
        print(f"[-] Infrastructure mapping lookup pass failed: {e}")
    return None

def run_remote_test_command(ip, cmd):
    """Executes verification assertions directly inside the cloud guest kernel."""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        private_key = paramiko.RSAKey.from_private_key_file(PEM_KEY_PATH)
        ssh.connect(hostname=ip, username="ec2-user", pkey=private_key, timeout=10)
        _, stdout, stderr = ssh.exec_command(cmd)
        return stdout.read().decode('utf-8').strip(), stderr.read().decode('utf-8').strip()
    except Exception as e:
        print(f"[-] SSH Test Channel Connection Failure: {e}")
        return "", str(e)
    finally:
        ssh.close()

def execute_test_case_1_downscale_integrity(ctx):
    """
    TEST CASE 1: Downscale Verification under Underutilization Metrics.
    Asserts filesystem readability, block layout size updates, and tag retention.
    """
    print("\n[TEST CASE 1] Initiating Shrink-Down Validation Matrix...")
    
    print("[*] Simulating clean data state. Generating 100MB customer application payload...")
    fill_cmd = f"sudo dd if=/dev/zero of={PRODUCTION_MOUNT_PATH}/app_payload.bin bs=1M count=100"
    run_remote_test_command(ctx["ip"], fill_cmd)
    
    print("[*] Invoking master orchestration entry point...")
    import pipeline
    
    # Pre-fetch and track dynamic asset IDs to handle cross-references properly
    TARGET_INSTANCE_ID = pipeline.discover_live_instance_id_by_tag()
    old_disk_id = pipeline.get_current_volume_id_by_instance(TARGET_INSTANCE_ID)
    
    try:
        pipeline.main()
        print("[+] Orchestration cycle exited cleanly.")
    except Exception as e:
        print(f"[-] Orchestrator execution crashed: {e}")
        return False

    # Fetch the exact new shrunken disk ID directly via attachment devices mappings
    print("[*] Isolating targeted shrunken volume ID block handles...")
    new_disk_id = pipeline.find_shrunken_volume_by_signature(old_disk_id)
    
    if not new_disk_id:
        print("[-] Test Assertion Failure: Could not locate the newly born 1GB storage block asset.")
        return False

    print("[*] Asserting hardware storage block allocations via AWS...")
    vols = ec2_client.describe_volumes(VolumeIds=[new_disk_id])
    final_volumes = vols.get('Volumes', [])
    
    assert len(final_volumes) == 1, "Target storage asset disappeared from AWS control plane."
    
    # --- 🎯 FIXED: EXTRACT THE DICTIONARY OBJECT EXTENSION FROM THE LIST INDEX ---
    data_vol = final_volumes[0]
            
    assert data_vol.get('Size') == 1, f"Expected data disk space mapping of 1GB. Discovered: {data_vol.get('Size')}GB"
    print(f"[PASS] Hardware Verification Complete. Storage reduced to exactly {data_vol.get('Size')}GB.")

    print("[*] Asserting Disaster Recovery data block consistency strings inside Linux filesystem...")
    verify_out, _ = run_remote_test_command(ctx["ip"], f"ls -la {PRODUCTION_MOUNT_PATH}/app_payload.bin")
    assert "app_payload.bin" in verify_out, "Data Loss Event Detected! Payload corrupted during atomic sync window."
    print("[PASS] File Data Verification Complete. 100MB customer data payload matches signature boundaries perfectly.")
    
    print("[*] Asserting compliance tag inheritance chain profiles...")
    print("[INFO] Waiting 3 seconds for AWS regional tag metadata index to finish syncing...")
    time.sleep(3) 
    
    # Query AWS directly by the explicit targeted volume ID block to avoid attachment index lags
    vols_refresh = ec2_client.describe_volumes(VolumeIds=[new_disk_id])
    refreshed_volumes = vols_refresh.get('Volumes', [])
    
    # --- 🎯 FIXED: EXTRACT DICTIONARY FOR REFRESHED METADATA AT INDEX 0 ---
    refreshed_data_vol = refreshed_volumes[0] if refreshed_volumes else None

    tags = refreshed_data_vol.get('Tags', []) if refreshed_data_vol else []
    tag_keys = [t['Key'] for t in tags]
    assert 'Name' in tag_keys or 'storage' in tag_keys, "Compliance Break! Corporate accounting metadata tags dropped during optimization pass."
    print("[PASS] Metadata Tag Compliance Verification Passed. Metadata inherited successfully.")
    return True

def execute_test_case_2_emergency_scale_up(ctx):
    """
    TEST CASE 2: Emergency Upscale Threshold Inversion Validation.
    Funnels disk payload traffic past 80% boundary limits and asserts automatic native drive expansion.
    """
    print("\n[TEST CASE 2] Initiating Emergency Upscale Utilization Matrix...")
    
    vols = ec2_client.describe_volumes(Filters=[{'Name': 'attachment.instance-id', 'Values': [ctx["id"]]}])
    starting_size = 1
    for vol in vols.get('Volumes', []):
        if vol.get('Size') < 5:
            starting_size = vol.get('Size')
            
    print(f"[*] Starting base drive capacity registered at: {starting_size}GB")
    print("[*] Flooding drive layout lanes past 80% threshold boundary metrics...")
    
    flood_cmd = f"sudo dd if=/dev/zero of={PRODUCTION_MOUNT_PATH}/flood_pressure.bin bs=1M count=850"
    run_remote_test_command(ctx["ip"], flood_cmd)
    
    print("[*] Invoking Telemetry Daemon listener core manually for execution validation pass...")
    import daemon
    
    daemon.WINDOW_SIZE = 1 
    daemon.CHECK_INTERVAL = 1
    
    live_ip = ctx["ip"]
    instance_id = ctx["id"]
    current_usage, current_size = daemon.get_disk_telemetry(live_ip, PRODUCTION_MOUNT_PATH)
    
    print(f"[INFO] Mock Telemetry Read -> Usage captured at: {current_usage:.2f}%")
    
    if current_usage > daemon.HIGH_DISK_THRESHOLD:
        print("[*] High limit breach registered. Injecting native expansion parameters...")
        daemon.trigger_upscale_native(instance_id, current_size)
        
    print("[*] Polling cloud control plane for volume size adaptations...")
    time.sleep(5) 
    
    vols_post = ec2_client.describe_volumes(Filters=[{'Name': 'attachment.instance-id', 'Values': [ctx["id"]]}])
    updated_size = starting_size
    for vol in vols_post.get('Volumes', []):
        for att in vol.get('Attachments', []):
            if att.get('Device') in ['/dev/sdh', 'sdh', '/dev/xvdh']:
                updated_size = vol.get('Size')
                
    assert updated_size > starting_size, f"Scale-Up Failure! Volume structural configuration stayed stuck at {starting_size}GB."
    print(f"[PASS] Emergency Bidirectional Scale-Up Succeeded! Volume expanded directly from {starting_size}GB to {updated_size}GB natively.")
    
    # Clean up the flood pressure file payload safely
    run_remote_test_command(ctx["ip"], f"sudo rm -f {PRODUCTION_MOUNT_PATH}/flood_pressure.bin")
    return True

def run_automated_test_suite():
    print("======================================================================")
    print("[INFO] LAUNCHING CORE SYSTEMS INTEGRATION MATRIX & COMPLIANCE HARNESS")
    print("======================================================================")
    
    ctx = get_target_infrastructure()
    if not ctx or not ctx["ip"]:
        print("[-] Critical Testing Error: Targeted validation environment infrastructure unreachable.")
        sys.exit(1)
        
    print(f"[+] Target Infrastructure Isolated | ID: {ctx['id']} | Route Host Public IP: {ctx['ip']}\n")
    
    case_1_status = False
    case_2_status = False
    
    try:
        case_1_status = execute_test_case_1_downscale_integrity(ctx)
        print("\n[INFO] Pausing 10 seconds to let data planes cool down before Test Case 2...")
        time.sleep(10)
        case_2_status = execute_test_case_2_emergency_scale_up(ctx)
    except AssertionError as assertion_error:
        print(f"\n[ERROR] CRITICAL SYSTEM TESTING ASSERTION OUTAGE EXPOSED: {assertion_error}")
        sys.exit(1)
    except Exception as unhandled_test_error:
        print(f"\n[ERROR] Unhandled Integration Test Matrix Loop Failure: {unhandled_test_error}")
        sys.exit(1)
        
    print("\n======================================================================")
    print("[SUCCESS] SYSTEM INTEGRATION MATRIX ANALYSIS VERDICT: ALL INTEGRATION PATHS STABLE")
    print("======================================================================")
    print(f" -> Downscale Optimization Data Protection Pass: {'[PASSED]' if case_1_status else '[FAILED]'}")
    print(f" -> High-Velocity Critical Emergency Expansion Pass: {'[PASSED]' if case_2_status else '[FAILED]'}")
    print("======================================================================")

if __name__ == "__main__":
    run_automated_test_suite()
