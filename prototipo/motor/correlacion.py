"""Correlación del MDR: un login correcto tras fuerza bruta desde el mismo origen contra el mismo equipo.

El SIEM ya lo correlaciona (Wazuh: fuerza bruta 5763 → «fallos seguidos de un login» 40112 → regla local
100600, familia acceso_consumado), pero su regla de fuerza bruta lleva `ignore="60"`: tras dispararse calla
60 s para TODOS los orígenes. Un segundo atacante dentro de ese minuto no deja la compuesta, su login llega
suelto (5715, «authentication success») y acababa en no_soportada (24/11, banco: 31 s después de otro
ataque). El MDR ve cada fallo que le llega, así que lo correlaciona él, en el daemon, al llegar cada alerta
—antes de agrupar y de suprimir repeticiones—.

Solo cambia una alerta que nadie clasificó (familia «otra») y que el adaptador marcó como login correcto:
si en los últimos VENTANA_S segundos llegaron al menos UMBRAL fallos de autenticación del mismo origen
contra el mismo equipo, pasa a acceso_consumado y lleva `correlacion` (lo dice la decisión). La hora es la
de las propias alertas (como la ráfaga). Los lotes cerrados (evaluación) no pasan por aquí: las cifras
canónicas no se mueven.
"""
import collections

from prototipo.motor import rafaga

VENTANA_S = 240          # la de la compuesta del SIEM (Wazuh 40112: timeframe 240)
UMBRAL = 5               # menos fallos es un usuario que se equivoca de contraseña
FAMILIA_FALLOS = "acceso_credenciales"
MAX_ORIGENES = 10_000    # (origen, equipo) recordados a la vez; al pasar, se olvidan los más antiguos


class LoginTrasFuerzaBruta:
    def __init__(self, ventana_s=VENTANA_S, umbral=UMBRAL, excluir=(), max_origenes=MAX_ORIGENES):
        self.ventana_s, self.umbral, self.max_origenes = ventana_s, umbral, max_origenes
        self.excluir = {str(x) for x in excluir or () if x}
        self._fallos = collections.OrderedDict()      # (origen, equipo) -> deque de instantes

    def __len__(self):
        return len(self._fallos)

    def _recientes(self, clave, t):
        cola = self._fallos.get(clave)
        if cola is None:
            return 0
        while cola and (t - cola[0]).total_seconds() > self.ventana_s:
            cola.popleft()
        if not cola:
            del self._fallos[clave]
            return 0
        return sum(1 for x in cola if x <= t)

    def anotar(self, alerta):
        """Registra el fallo, o convierte el login en acceso_consumado (in situ). True si lo convirtió."""
        ip, activo = alerta.get("origen_ip"), alerta.get("activo")
        t = rafaga._instante(alerta) if ip and activo else None
        if t is None:
            return False
        clave = (ip, activo)
        if alerta.get("familia") == FAMILIA_FALLOS:
            self._fallos.setdefault(clave, collections.deque()).append(t)
            self._fallos.move_to_end(clave)
            while len(self._fallos) > self.max_origenes:
                self._fallos.popitem(last=False)
            return False
        if alerta.get("familia") != "otra" or alerta.get("login_correcto") is not True or ip in self.excluir:
            return False
        n = self._recientes(clave, t)
        if n < self.umbral:
            return False
        alerta["familia"] = "acceso_consumado"
        alerta["correlacion"] = {
            "regla": "login_tras_fuerza_bruta", "fallos": n, "ventana_s": self.ventana_s,
            "texto": (f"login correcto tras {n} fallos de autenticación desde {ip} contra {activo} en los últimos "
                      f"{self.ventana_s} s: el SIEM no lo marcó como intrusión; lo correlacionó el MDR")}
        return True
