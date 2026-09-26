# 1. Configure the AWS Provider connection
provider "aws" {
  region = "us-east-1" 
}

# 2. Dynamic Lookup for the Latest Official Amazon Linux 2023 AMI
data "aws_ami" "latest_amazon_linux" {
  most_recent = true
  owners      = ["137112412989"] 

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# 3. Create a Security Group to allow secure SSH access
resource "aws_security_group" "autoscaler_sg" {
  name        = "autoscaler-testing-sg"
  description = "Allow SSH access to storage testing environment"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # In production, restrict this to your specific IP
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# 4. Define the IAM Policy permissions required by your Python daemon script
resource "aws_iam_role" "autoscaler_agent_role_v2" {
  name = "AutoscalerStorageAgentRole-v2"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action    = "sts:AssumeRole"
        Effect    = "Allow"
        Principal = { Service = "ec2.amazonaws.com" }
      }
    ]
  })
}

resource "aws_iam_role_policy" "autoscaler_agent_policy_v2" {
  name = "AutoscalerStorageAgentPolicy-v2"
  role = aws_iam_role.autoscaler_agent_role_v2.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateVolume",
          "ec2:DescribeVolumes",
          "ec2:DescribeInstances"
        ]
        Resource = "*" 
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:AttachVolume",
          "ec2:DetachVolume",
          "ec2:DeleteVolume",
          "ec2:ModifyVolume"
        ]
        Resource = "*"
        # INTERVIEW NOTE: Restricting management contexts to target testing tags explicitly
        Condition = {
          StringEquals = {
            "aws:ResourceTag/Name" = ["Bloated-Source-Disk", "Autoscaler-Testing-Server"]
          }
        }
      }
    ]
  })
}

resource "aws_iam_instance_profile" "Autoscaler_profile_v2" {
  name = "AutoscalerInstanceProfile-v2"
  role = aws_iam_role.autoscaler_agent_role_v2.id
}

# 5. Provision the primary Amazon Linux EC2 Application Server
resource "aws_instance" "Autoscaler_server" {
  ami                  = data.aws_ami.latest_amazon_linux.id 
  instance_type        = "t3.micro"               
  security_groups      = [aws_security_group.autoscaler_sg.name]
  iam_instance_profile = aws_iam_instance_profile.Autoscaler_profile_v2.name
  key_name             = "Mydemkey" 

  # FIXED: Replaced arbitrary sleep with an active polling check loop on device symlinks
  user_data = <<EOF
#!/bin/bash
dnf install -y python3-boto3 rsync util-linux
mkdir -p /home/ec2-user/ec2-agent
mkdir -p /data

# Actively poll for the disk to be hot-attached to prevent startup race conditions
TARGET_LINK=""
while [ -z "$TARGET_LINK" ]; do
    TARGET_LINK=$(ls /dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_* 2>/dev/null | head -n 1)
    sleep 1
done

if ! blkid "$TARGET_LINK"; then 
    mkfs.ext4 "$TARGET_LINK"
fi

mount "$TARGET_LINK" /data
chown -R ec2-user:ec2-user /home/ec2-user/ec2-agent /data
chmod 775 /data
EOF

  tags = { Name = "Autoscaler-Testing-Server" }

  provisioner "file" {
    source      = "../ec2-agent/daemon.py"
    destination = "/home/ec2-user/ec2-agent/daemon.py"

    connection {
      type        = "ssh"
      user        = "ec2-user"
      private_key = file("~/Downloads/Mydemkey.pem") 
      host        = self.public_ip
    }
  }

  provisioner "file" {
    source      = "../ec2-agent/cloud_optimizer.py"
    destination = "/home/ec2-user/ec2-agent/cloud_optimizer.py"

    connection {
      type        = "ssh"
      user        = "ec2-user"
      private_key = file("~/Downloads/Mydemkey.pem") 
      host        = self.public_ip
    }
  }
}

# 6. Provision and attach the secondary "Bloated" 20GB Volume
resource "aws_volume_attachment" "ebs_att" {
  device_name = "/dev/sdf"
  volume_id   = aws_ebs_volume.bloated_volume.id
  instance_id = aws_instance.Autoscaler_server.id
}

resource "aws_ebs_volume" "bloated_volume" {
  availability_zone = aws_instance.Autoscaler_server.availability_zone
  size              = 20
  type              = "gp3"

  tags = { Name = "Bloated-Source-Disk" }
}

# 7. FIXED: Replaced platform-specific PowerShell scripts with native Terraform file generators
resource "local_file" "ssh_config_sync" {
  filename = "${path.module}/ssh_target_host.txt"
  content  = "HostName ${aws_instance.Autoscaler_server.public_ip}"
}

# 8. Output variables
output "ec2_public_ip" { value = aws_instance.Autoscaler_server.public_ip }
