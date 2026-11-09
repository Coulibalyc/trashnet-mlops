# Crée automatiquement la VM AWS (EC2) qui fera tourner le projet.
#   terraform init     -> télécharge le plugin AWS
#   terraform apply    -> crée la VM
#   terraform destroy  -> supprime tout (pour ne plus payer)

terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" {
  region = var.region
}

# Image Ubuntu 24.04 officielle la plus récente
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
}

# Clé SSH pour se connecter à la VM
resource "aws_key_pair" "deployer" {
  key_name   = "trashnet-key"
  public_key = file(pathexpand(var.public_key_path))
}

# Pare-feu : qui a le droit d'entrer
resource "aws_security_group" "trashnet" {
  name        = "trashnet-sg"
  description = "TrashNet MLOps"

  ingress {
    description = "Site web + API (public)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "SSH (seulement mon IP + GitHub Actions)"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.ssh_cidrs
  }
  ingress {
    description = "MLflow (seulement mon IP)"
    from_port   = 5050
    to_port     = 5050
    protocol    = "tcp"
    cidr_blocks = [var.my_ip]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "trashnet" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  key_name               = aws_key_pair.deployer.key_name
  vpc_security_group_ids = [aws_security_group.trashnet.id]
  user_data              = file("${path.module}/user_data.sh") # installe Docker au 1er démarrage

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }
  tags = { Name = "trashnet-mlops" }
}

# IP publique fixe (ne change pas si on redémarre la VM)
resource "aws_eip" "trashnet" {
  instance = aws_instance.trashnet.id
  domain   = "vpc"
}
