output "vpc_id" {
  description = "VPC creada."
  value       = module.base.vpc_id
}

output "laboratorio_instance_id" {
  description = "Instancia del laboratorio (banco, Wazuh y MDR)."
  value       = aws_instance.laboratorio.id
}

# La consola del MDR, sin puerto público: túnel SSM al 8787 de la instancia (el daemon liga a 127.0.0.1).
output "comando_tunel_visor" {
  description = "Túnel SSM para abrir la consola en http://127.0.0.1:8787."
  value = join(" ", [
    "aws ssm start-session --region ${var.region} --target ${aws_instance.laboratorio.id}",
    "--document-name AWS-StartPortForwardingSession",
    "--parameters '{\"portNumber\":[\"8787\"],\"localPortNumber\":[\"8787\"]}'",
  ])
}

output "comando_token_admin" {
  description = "Cómo leer el token del analista admin de la consola."
  value       = "aws ssm start-session --region ${var.region} --target ${aws_instance.laboratorio.id}   # y dentro: sudo cat /root/mdr-token-admin"
}

# Para la instantánea de la traza antes de un destroy (el disco vive en el módulo común).
output "volumen_traza_id" {
  description = "Disco cifrado de la traza (/var/lib/mdr)."
  value       = module.base.volumen_traza_id
}
