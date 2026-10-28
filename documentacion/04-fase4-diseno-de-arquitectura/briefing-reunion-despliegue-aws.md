# Despliegue en AWS — briefing para la reunión con el tutor industrial

> Una página para preparar la conversación. El diseño técnico completo está en
> [despliegue-aws-opentofu.md](despliegue-aws-opentofu.md). El tutor **académico** indicó hacer un
> despliegue; este documento resume qué es, qué hace falta de la empresa y qué decidir.

## Qué es (en una frase)
Coger lo que ya corre en el portátil —el daemon MDR + el visor, con su arranque `systemd` ya preparado
en `deploy/`— y hacerlo correr en una máquina de AWS de la empresa, de forma **reproducible** mediante
código de infraestructura (**OpenTofu**). Opcionalmente, una segunda máquina **con GPU** para el LLM
justificador (lo único que el portátil no puede mover).

## Qué aporta y qué NO (para encuadrar expectativas)
- **NO** mejora la evaluación del prototipo (recall 1.0 / FP 0.009 ya están medidos y validados en el
  laboratorio; son cifras congeladas). El despliegue no cambia el motor ni sus métricas.
- **SÍ** demuestra tres cosas: (1) que el sistema es **desplegable** de verdad (camino a producción),
  (2) que corre el **LLM justificador en GPU** (capacidad que el portátil no tiene), y (3) que la
  **infraestructura** es reproducible y mantiene la seguridad en la nube (todo en subred privada, sin
  exposición a Internet, secretos gestionados).

## Qué hace falta de la empresa (lo que se pide en la reunión)
1. **Acceso a la cuenta AWS**: un usuario/rol con permiso para crear red (VPC), máquinas (EC2), disco
   (EBS), roles (IAM), secretos (Secrets Manager/SSM) y acceso remoto (SSM Session Manager). *O*, si
   prefieren no dar acceso, que yo entregue el código de infraestructura y **lo apliquen ellos**.
2. **Alcance** (marca el coste): **(a)** solo MDR + visor → barato (unos pocos €/mes); **(b)** además
   el **LLM en GPU** → es el grueso del coste (~0,5 $/h la GPU; se puede **encender solo para probar y
   apagar**, o usar instancias *Spot*).
3. **GPU** (si va el LLM): si la cuenta ya puede usar instancias GPU (familias g4/g5) o hay que
   **solicitar el aumento de cuota** a Amazon (puede tardar), y si hay **presupuesto** para esas horas.
4. **A qué se conecta el MDR**: ¿hay un SIEM/equipos reales de un cliente, o montamos **1-2 máquinas de
   prueba** en AWS para demostrar el ciclo detección → contención? (Para una demo de tesis, lo normal
   es simular con máquinas de prueba.)
5. **Convenciones de la empresa**: región de AWS, nombres/etiquetas, restricciones de seguridad, y
   dónde guardar el «estado» de OpenTofu (local, o en un bucket S3 de la empresa).
6. **Secretos y modelo**: dónde guardan claves/tokens (Secrets Manager) y quién aporta los pesos del
   modelo del LLM.

## Preguntas concretas para el tutor industrial
- [ ] ¿Me dais acceso a la cuenta AWS con esos permisos, o preparo la IaC y la aplicáis vosotros?
- [ ] ¿Desplegamos solo MDR + visor, o también el LLM en GPU? ¿Hay presupuesto para la GPU?
- [ ] ¿La cuenta ya tiene cuota de instancias GPU, o hay que pedirla?
- [ ] ¿Región y convenciones (nombres, etiquetas, seguridad) que debo respetar?
- [ ] ¿Conectamos a un cliente real o monto máquinas de prueba para la demo?
- [ ] ¿Dónde guardo el estado de OpenTofu (local o vuestro S3)?

## Plan por fases (de menor a mayor compromiso/coste)
1. **Validación offline — sin cuenta, sin coste.** Escribo la infraestructura (OpenTofu) y la valido en
   local con **LocalStack** (sobre Docker). Demuestra que la receta de despliegue es correcta sin
   alquilar nada ni tocar la cuenta de la empresa.
2. **Despliegue real — con la cuenta de la empresa.** Aplicar la infraestructura (`apply`), arrancar,
   probar y apagar. La GPU del LLM solo si se decide incluirla (fase 2b, por su coste).

## Resumen para abrir la conversación
> «El despliegue ya está diseñado y la infraestructura se puede validar sin coste. Para un despliegue
> real necesito acceso a la cuenta AWS de la empresa (o que la apliquéis vosotros con el código que
> entrego), y el coste depende de si incluimos la GPU del LLM. El resto (MDR + visor) es de coste bajo.»
