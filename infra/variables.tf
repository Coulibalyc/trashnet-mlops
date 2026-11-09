variable "region" {
  default = "eu-west-3" # Paris
}

variable "instance_type" {
  default = "m7i-flex.large" # 2 vCPU, 8 Go RAM, éligible offre gratuite (comptes depuis juillet 2025)
}

variable "public_key_path" {
  default = "~/.ssh/trashnet.pub"
}

variable "my_ip" {
  description = "Votre IP publique au format x.x.x.x/32 (curl ifconfig.me)"
  type        = string
}

variable "ssh_cidrs" {
  description = "Qui peut se connecter en SSH. GitHub Actions a des IP variables, d'où 0.0.0.0/0 par défaut (protégé par la clé SSH)."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}
