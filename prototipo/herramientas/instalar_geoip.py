"""Instala una base de IPs del MDR: valida el CSV descargado de DB-IP (mensual, CC BY 4.0) y lo
copia de una vez a su ruta: «IP to Country Lite» a TRIAJE_GEOIP (`--asn`: «IP to ASN Lite» a
TRIAJE_ASN). Si el fichero no es válido, la base instalada no se toca.

    python3 -m prototipo.herramientas.instalar_geoip [--asn] <descargado.csv.gz> <destino>
"""
import os
import shutil
import sys
import tempfile

from prototipo.motor import geoip


def instalar(origen, destino, tipo="pais"):
    """Valida `origen` y lo deja en `destino`. Devuelve {rangos, fuente}. SystemExit si no vale."""
    if origen.endswith(".gz") != destino.endswith(".gz"):
        raise SystemExit("instalar-geoip: el fichero y TRIAJE_GEOIP deben tener la misma extensión (.csv o .csv.gz)")
    if "dbip" in os.path.basename(origen) and "dbip" not in os.path.basename(destino):
        raise SystemExit(f"instalar-geoip: es una base de DB-IP y {geoip.VARIABLE[tipo]} no lleva «dbip» en el "
                         "nombre: la consola no mostraría su atribución, que exige la licencia. Usa p. ej. "
                         + ("/var/lib/mdr/dbip-asn-lite.csv.gz" if tipo == "asn" else "/var/lib/mdr/dbip-country-lite.csv.gz"))
    try:
        b = geoip.leer(origen, tipo)
    except (OSError, ValueError, EOFError) as e:
        raise SystemExit(f"instalar-geoip: no es una base válida: {e}")
    d = os.path.dirname(os.path.abspath(destino))
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".geoip-")
    os.close(fd)
    try:
        shutil.copyfile(origen, tmp)
        os.chmod(tmp, 0o644)
        os.replace(tmp, destino)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return {"rangos": b.rangos, "fuente": b.fuente}


def _main(argv):
    tipo = "asn" if "--asn" in argv else "pais"
    argv = [a for a in argv if a != "--asn"]
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[-1].strip(), file=sys.stderr)
        return 2
    r = instalar(argv[0], argv[1], tipo)
    print(f"base de {'ASN' if tipo == 'asn' else 'geolocalización'} -> {argv[1]}: {r['rangos']:,} rangos".replace(",", "."))
    if r["fuente"] == "dbip":
        print("Datos de DB-IP (CC BY 4.0): la consola muestra su atribución al pie del menú.")
    print("El MDR la lee al arrancar: reinicia el servicio para usarla.")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
