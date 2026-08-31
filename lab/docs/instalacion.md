# Guía de instalación del entorno

De una máquina limpia a `sh lab/lab.sh up`. Documenta la instalación **tal como se hizo**, no una
receta genérica. Es el entregable *«guía de instalación y configuración del entorno»* de la
[Fase 3](../../documentacion/03-fase3-entorno-de-pruebas/).

Entorno de referencia: **Windows con WSL2**, portátil AMD Ryzen 7 5700U, 16 GB de RAM, sin GPU
dedicada. Sobre Linux nativo los pasos 2 y 3 son idénticos y el paso 1 no aplica.

---

## 1. Ajustar la memoria de WSL — antes que nada

**WSL2 asigna por defecto la mitad de la RAM del anfitrión.** Con 16 GB físicos, Linux solo ve
unos 7,4 GiB, y el presupuesto de memoria del diseño se calculó sobre los 16. Es el primer
tropiezo del proyecto y conviene quitárselo de en medio antes de instalar nada.

Desde **Windows**, crear o editar `%UserProfile%\.wslconfig`:

```ini
[wsl2]
memory=12GB
swap=4GB
```

Y reiniciar WSL desde PowerShell:

```powershell
wsl --shutdown
```

Comprobar dentro de WSL:

```sh
free -g            # debe mostrar ~11 GiB, no ~7
```

> Ver el hallazgo completo en [mediciones.md](mediciones.md).

---

## 2. Docker

Por el script oficial:

```sh
sudo apt update && sudo apt install -y curl
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

**El `usermod` no surte efecto en la sesión actual.** Hay que cerrar la sesión y volver a entrar
—o `wsl --shutdown` desde Windows— o todo `docker` seguirá pidiendo `sudo`.

```sh
docker --version   # referencia del proyecto: 29.7.2
docker run --rm hello-world
```

> `get-docker.sh` queda en la raíz del repositorio y está en `.gitignore`: es un instalador de
> terceros, no código del proyecto.

---

## 3. Containerlab

```sh
bash -c "$(curl -sL https://get.containerlab.dev)"
containerlab version   # referencia del proyecto: 0.79.0
```

No hace falta configurar nada más: Containerlab crea por su cuenta la red Docker `clab`
(172.20.20.0/24), que es el **plano de gestión out-of-band** del laboratorio. Es donde viven el
auditor y Wazuh, separados del plano de datos que observan.

---

## 4. Validar la cadena antes de montar nada

Antes de desplegar el laboratorio completo, conviene comprobar que WSL → Docker → Containerlab
funciona de punta a punta. Para eso existe la topología mínima:

```sh
containerlab deploy  -t lab/topologias/smoke-test.clab.yml
containerlab destroy -t lab/topologias/smoke-test.clab.yml
```

Tres nodos Alpine, unos 90 MiB en total y un ciclo completo en segundos. Si esto falla, no tiene
sentido seguir: el problema está en la instalación, no en el laboratorio.

---

## 5. Imágenes que se descargan

La primera ejecución de `lab.sh up` descarga unos **5 GB**. Conviene saberlo antes de empezar y no
a mitad.

| Imagen | Para qué | Tamaño |
|--------|----------|--------|
| `alpine:latest` | Los nodos de red, el puesto, el IoT y el auditor | 13 MB |
| `tleemcjr/metasploitable2:latest` | El servidor vulnerable: 19 puertos y CVEs documentados | 2,3 GB |
| `wazuh/wazuh-manager:4.14.7` | La fuente de alertas y el baseline | 2,55 GB |

Se pueden precargar para que el primer despliegue no espere:

```sh
docker pull alpine:latest
docker pull tleemcjr/metasploitable2:latest
docker pull wazuh/wazuh-manager:4.14.7
```

**Wazuh no es un nodo de Containerlab.** Su imagen es pesada y trae su propio *entrypoint*, así que
[wazuh-run.sh](../scripts/wazuh-run.sh) lo arranca como contenedor aparte enganchado a la red `clab`. Ese
script además **activa la recepción de syslog remoto**, que no viene habilitada de fábrica; sin ese
paso el manager ignora todo el syslog del laboratorio.

---

## 6. Levantar el laboratorio

```sh
sh lab/lab.sh up       # red + Wazuh + reenvío de syslog
sh lab/lab.sh status   # comprobar que está todo vivo
sh lab/lab.sh test     # prueba de humo de extremo a extremo
sh lab/lab.sh down     # apagar
```

La guía de verificación completa está en
[instrucciones-prueba-manual.md](prueba-manual.md).

---

## 7. Opcional — KVM, para el equipo de borde con firmware real

La variante [red-cliente-openwrt.clab.yml](../topologias/red-cliente-openwrt.clab.yml) usa un OpenWrt real, que **es una VM QEMU** y
no un contenedor. Necesita virtualización por hardware:

```sh
ls -l /dev/kvm            # debe existir
grep -c -E 'svm|vmx' /proc/cpuinfo   # > 0
sudo usermod -aG kvm $USER
```

La imagen **no se descarga: se construye localmente** con vrnetlab a partir del firmware de
OpenWrt, y es un paso previo que lleva más de lo esperado.

> **Estado: bloqueado.** KVM funciona y la VM arranca, pero el bootstrap de vrnetlab se cuelga, con
> las dos versiones de OpenWrt probadas. Por eso la topología de trabajo usa un equipo de borde
> provisional en Linux. Diagnóstico completo en [mediciones.md](mediciones.md).

---

## Tropiezos conocidos

| Síntoma | Causa | Solución |
|---------|-------|----------|
| `docker` pide `sudo` después de instalarlo | El grupo `docker` no se aplica a la sesión en curso | Cerrar sesión, o `wsl --shutdown` desde Windows |
| El laboratorio va justo de memoria | WSL expone la mitad de la RAM del anfitrión | El paso 1 |
| Todo *Up* pero `lab.sh test` falla en conectividad | Los contenedores se reiniciaron (arranque de WSL, reinicio de Docker) y **los enlaces del `deploy` no sobreviven** | `sh lab/lab.sh down && sh lab/lab.sh up`. `lab.sh status` lo detecta |
| `lab.sh test` reporta 0 alertas | El reenvío de syslog no está activo | `sh lab/scripts/reenvio-syslog.sh` |
| `lab.sh test` no correlaciona a nivel 10 al repetirlo | La regla 5763 lleva `ignore="60"`: se silencia 60 s tras dispararse | Esperar un minuto entre ejecuciones |
| Wazuh tarda 1–2 min en estar listo | Arranca sus demonios y se reinicia tras activar syslog | Es normal; `lab.sh up` ya espera |
| Las primeras ~180 alertas no son del laboratorio | Autoauditoría CIS del propio contenedor de Wazuh | Filtrar por regla `190xx` o por `agent.id` |
| Las mediciones de memoria salen altas | El entorno de desarrollo es el mayor consumidor de la máquina | Cerrar VS Code y el navegador antes de medir |
