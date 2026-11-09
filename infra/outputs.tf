output "public_ip" {
  value = aws_eip.trashnet.public_ip
}

output "ssh" {
  value = "ssh -i ~/.ssh/trashnet ubuntu@${aws_eip.trashnet.public_ip}"
}

output "app_url" {
  value = "http://${aws_eip.trashnet.public_ip}"
}
