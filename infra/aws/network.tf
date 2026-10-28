data "aws_availability_zones" "disponibles" {
  state = "available"
}

# VPC con subred PRIVADA (sin IGW, sin IP pública): nada del MDR queda expuesto a Internet (RNF-01).
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true   # necesario para el DNS privado de los endpoints VPC
  tags                 = { Name = "${var.proyecto}-vpc" }
}

resource "aws_subnet" "privada" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.subred_privada_cidr
  availability_zone = data.aws_availability_zones.disponibles.names[0]
  tags              = { Name = "${var.proyecto}-privada" }
}

# Tabla de rutas sin ruta a Internet: solo la ruta local de la VPC (implícita) + el gateway de S3.
resource "aws_route_table" "privada" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${var.proyecto}-rt-privada" }
}

resource "aws_route_table_association" "privada" {
  subnet_id      = aws_subnet.privada.id
  route_table_id = aws_route_table.privada.id
}

# --- Grupos de seguridad ---
# MDR: sin ingreso público (el acceso del analista va por SSM, saliente). Egreso abierto para llegar
# al LLM, a los endpoints VPC y al plano de gestión del cliente (por VPN/peering).
resource "aws_security_group" "mdr" {
  name_prefix = "${var.proyecto}-mdr-"
  description = "MDR daemon + visor (sin ingreso publico)"
  vpc_id      = aws_vpc.main.id

  egress {
    description = "salida (LLM, endpoints VPC, plano de gestion del cliente via VPN)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "${var.proyecto}-sg-mdr" }
}

# LLM: solo acepta del SG del MDR (la URL privada del justificador). Nada público.
resource "aws_security_group" "llm" {
  name_prefix = "${var.proyecto}-llm-"
  description = "LLM justificador (solo desde el MDR)"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "llama-server desde el MDR"
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.mdr.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "${var.proyecto}-sg-llm" }
}

# Endpoints de interfaz (SSM): aceptan 443 desde la VPC. Permiten el acceso del analista por SSM y la
# gestión sin NAT ni salida a Internet.
resource "aws_security_group" "endpoints" {
  name_prefix = "${var.proyecto}-vpce-"
  description = "Endpoints VPC de interfaz (443 desde la VPC)"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTPS desde la VPC"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "${var.proyecto}-sg-vpce" }
}

# Endpoints de interfaz para SSM Session Manager (acceso del analista sin puerto público).
resource "aws_vpc_endpoint" "ssm" {
  for_each            = toset(["ssm", "ssmmessages", "ec2messages"])
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.region}.${each.key}"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.privada.id]
  security_group_ids  = [aws_security_group.endpoints.id]
  private_dns_enabled = true
  tags                = { Name = "${var.proyecto}-vpce-${each.key}" }
}

# Endpoint de gateway para S3 (artefactos/pesos desde S3 sin salir a Internet).
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.privada.id]
  tags              = { Name = "${var.proyecto}-vpce-s3" }
}

# --- Egreso de BOOTSTRAP (opcional, apagado por defecto) ---
# La subred privada no tiene salida a Internet (postura del diseño: RNF-01). Pero el PRIMER ARRANQUE
# (dnf install, git clone, descarga del modelo) necesita egreso temporal. Con `egreso_bootstrap = true`
# se crea IGW + subred pública + NAT gateway y una ruta por defecto de la subred privada al NAT; el
# RUNTIME del daemon sigue sin llamar a Internet (eso lo garantiza el producto, no la red). Con `false`
# hay que desplegar desde una AMI horneada o artefactos en S3 (ver README y templates).
resource "aws_internet_gateway" "igw" {
  count  = var.egreso_bootstrap ? 1 : 0
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${var.proyecto}-igw" }
}

resource "aws_subnet" "publica" {
  count             = var.egreso_bootstrap ? 1 : 0
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.subred_publica_cidr
  availability_zone = data.aws_availability_zones.disponibles.names[0]
  tags              = { Name = "${var.proyecto}-publica" }
}

resource "aws_route_table" "publica" {
  count  = var.egreso_bootstrap ? 1 : 0
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw[0].id
  }
  tags = { Name = "${var.proyecto}-rt-publica" }
}

resource "aws_route_table_association" "publica" {
  count          = var.egreso_bootstrap ? 1 : 0
  subnet_id      = aws_subnet.publica[0].id
  route_table_id = aws_route_table.publica[0].id
}

resource "aws_eip" "nat" {
  count  = var.egreso_bootstrap ? 1 : 0
  domain = "vpc"
  tags   = { Name = "${var.proyecto}-eip-nat" }
}

resource "aws_nat_gateway" "nat" {
  count         = var.egreso_bootstrap ? 1 : 0
  allocation_id = aws_eip.nat[0].id
  subnet_id     = aws_subnet.publica[0].id
  tags          = { Name = "${var.proyecto}-nat" }
}

resource "aws_route" "privada_egreso" {
  count                  = var.egreso_bootstrap ? 1 : 0
  route_table_id         = aws_route_table.privada.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.nat[0].id
}
