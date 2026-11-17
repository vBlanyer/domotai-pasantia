output "vpc_id" {
  value = aws_vpc.main.id
}

output "vpc_cidr" {
  value = aws_vpc.main.cidr_block
}

output "subred_privada_id" {
  value = aws_subnet.privada.id
}

output "zona" {
  description = "Zona de disponibilidad de la subred privada (y del disco de la traza)."
  value       = aws_subnet.privada.availability_zone
}

output "sg_instancia_id" {
  description = "Grupo de seguridad de la instancia del MDR (sin ingreso; salida libre)."
  value       = aws_security_group.mdr.id
}

output "perfil_instancia" {
  description = "Perfil IAM de la instancia (SSM, los secretos y los objetos de S3 indicados)."
  value       = aws_iam_instance_profile.instancia.name
}

output "ami_al2023" {
  value = data.aws_ami.al2023.id
}

output "volumen_traza_id" {
  value = aws_ebs_volume.traza.id
}

output "volumen_traza_nvme" {
  description = "El id del disco sin guion: el arranque lo busca en /dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_<este>."
  value       = replace(aws_ebs_volume.traza.id, "-", "")
}
