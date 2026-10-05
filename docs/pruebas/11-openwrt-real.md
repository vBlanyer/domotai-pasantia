# 11 · Validar la contención sobre un OpenWrt real

Cierra el hueco de la Fase 3/4: probar que la **contención del catálogo funciona sobre un cortafuegos
de borde con firmware real (OpenWrt)**, no solo sobre los contenedores Linux del laboratorio.

Dos partes: **(1)** el catálogo ya es portable por plataforma (hecho en el código), y **(2)** se valida
sobre un OpenWrt x86 en QEMU, sin depender de vrnetlab (cuyo bootstrap se cuelga con 24.10).

## 1. Qué cambió en el código (portabilidad por plataforma)

OpenWrt 22.03+ usa **`fw4`/nftables**, no `iptables`. El conector sigue siendo el mismo (SSH); solo
cambia el **comando** que se renderiza para los nodos marcados `plataforma: openwrt`.

- `prototipo/catalogo.yml` — `BLOQUEAR_IP_FIREWALL` tiene una variante `plataformas.openwrt` con nftables:
  - bloquear: `nft add rule inet fw4 forward ip saddr {ip} drop`
  - verificar: `nft list chain inet fw4 forward | grep -F {ip} | grep -qw drop`
  - revertir: localiza el *handle* de la regla y hace `nft delete rule ... handle N`
- `prototipo/catalogo.py` — `campo(acc, nombre, plataforma)` elige la variante; `sudoers` ya cubre `nft`.
- La `plataforma` del nodo viaja en la **orden** (`orden.construir` / el salto del agente la leen de
  `topologia[nodo].plataforma`), y el conector, la verificación y la reversión usan la variante.
- **Sin `plataforma` todo sigue igual** (iptables): no cambia nada del banco ni de las métricas.

Para que un nodo use nftables, se declara en el perfil del cliente:

```yaml
topologia:
  fw-edge: { rol: firewall_perimetral, ip: 192.168.1.1, plataforma: openwrt }
```

## 2. Arrancar un OpenWrt x86 en QEMU (sin vrnetlab)

En esta máquina **KVM funciona** (`/dev/kvm` existe), así que arranca con aceleración.

```bash
sudo apt install -y qemu-system-x86 qemu-utils

# Imagen oficial x86-64 (combined ext4). Ajusta la versión si hace falta.
V=24.10.0
wget https://downloads.openwrt.org/releases/$V/targets/x86/64/openwrt-$V-x86-64-generic-ext4-combined.img.gz
gunzip openwrt-$V-x86-64-generic-ext4-combined.img.gz
qemu-img resize openwrt-$V-x86-64-generic-ext4-combined.img 512M   # espacio para opkg

# Arranque con red de usuario + redirección de SSH (22) y LuCI (80) al host
sudo qemu-system-x86_64 -enable-kvm -m 256 -nographic \
  -drive file=openwrt-$V-x86-64-generic-ext4-combined.img,format=raw,if=virtio \
  -netdev user,id=n0,hostfwd=tcp::2222-:22,hostfwd=tcp::8088-:80 \
  -device virtio-net,netdev=n0
```

En la consola de OpenWrt (sale sola), fija una contraseña de root para habilitar SSH (dropbear):

```sh
passwd          # pon una contraseña
/etc/init.d/dropbear restart
```

Desde el host ya puedes entrar: `ssh root@127.0.0.1 -p 2222`.

## 3. Validar la contención

**a) A mano (lo esencial: el comando del catálogo funciona sobre OpenWrt real):**

```sh
# en el OpenWrt (por SSH)
nft add rule inet fw4 forward ip saddr 203.0.113.9 drop        # BLOQUEAR_IP_FIREWALL (openwrt)
nft list chain inet fw4 forward | grep -F 203.0.113.9 | grep -qw drop && echo BLOQUEADO
# revertir
nft -a list chain inet fw4 forward | grep -F 203.0.113.9 | grep -o 'handle [0-9]*' | grep -o '[0-9]*' \
  | xargs -r -n1 nft delete rule inet fw4 forward handle
```

Si prefieres el comando por defecto (iptables) sin tocar el catálogo, instala la capa de compatibilidad:
`opkg update && opkg install iptables-nft` — entonces `iptables -A FORWARD -s {ip} -j DROP` funciona igual.

**b) Por el motor (de punta a punta):** apunta el conector a ese OpenWrt (usuario/clave o la ruta SSH del
lab) y marca su nodo `plataforma: openwrt` en el perfil. El motor renderiza y ejecuta la variante nft sola;
la traza queda con el `comando_ejecutado` nft y la verificación correcta.

## 4. Qué deja demostrado

- La contención del catálogo es **portable a firmware real**: el mismo motor, el mismo conector SSH y la
  misma traza, con el comando adecuado por plataforma (iptables en Linux genérico, nftables en OpenWrt).
- El hueco deja de ser «no se pudo probar» y pasa a «el catálogo es portable por plataforma, validado
  sobre OpenWrt 24.10 real».

> El bloqueo original era el **bootstrap de vrnetlab** (no KVM): la VM arrancaba pero el empaquetado de
> vrnetlab se colgaba con 24.10. Arrancar el x86 directamente en QEMU lo evita. La topología
> `lab/topologias/red-cliente-openwrt.clab.yml` sigue ahí para quien resuelva vrnetlab.
