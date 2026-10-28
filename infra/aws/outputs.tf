output "vpc_id" {
  description = "VPC creada."
  value       = aws_vpc.main.id
}

output "mdr_instance_id" {
  description = "Instancia del daemon MDR + visor."
  value       = aws_instance.mdr.id
}

output "llm_instance_id" {
  description = "Instancia GPU del LLM (null si llm_habilitado = false)."
  value       = var.llm_habilitado ? aws_instance.llm[0].id : null
}

# Cómo abre el analista el visor SIN puerto público: túnel SSM reenviando el 8787 local al de la
# instancia (el daemon liga a 127.0.0.1). Requiere el plugin de SSM en el equipo del analista.
output "comando_tunel_visor" {
  description = "Túnel SSM para abrir el visor en http://127.0.0.1:8787 del analista."
  value = join(" ", [
    "aws ssm start-session --region ${var.region} --target ${aws_instance.mdr.id}",
    "--document-name AWS-StartPortForwardingSession",
    "--parameters '{\"portNumber\":[\"8787\"],\"localPortNumber\":[\"8787\"]}'",
  ])
}
