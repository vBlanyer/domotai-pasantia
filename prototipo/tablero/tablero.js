const $ = (s) => document.querySelector(s);
const paneles = document.querySelectorAll(".panel");

document.querySelectorAll("nav button").forEach((b) => {
  b.onclick = () => {
    document.querySelectorAll("nav button").forEach((x) => x.classList.remove("activa"));
    paneles.forEach((p) => p.classList.remove("activa"));
    b.classList.add("activa");
    $("#" + b.dataset.tab).classList.add("activa");
  };
});

async function json(ruta, opciones) {
  const r = await fetch(ruta, opciones);
  return r.json();
}
const esc = (t) => String(t == null ? "" : t).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

async function pintarSalud() {
  const d = await json("/api/salud");
  if (d.sin_datos) { $("#salud").innerHTML = "<p>sin datos del monitor (¿banco levantado?)</p>"; return; }
  const filas = d.servicios.map((s) =>
    `<tr><td>${esc(s.nombre)}</td><td class="${s.estado === "ok" ? "ok" : "caido"}">${s.estado === "ok" ? "● OK" : "✖ CAÍDO"}</td><td>${esc((s.depende_de || []).join(", ") || "—")}</td></tr>`).join("");
  $("#salud").innerHTML = `<p>${d.caidos} de ${d.total} servicios caídos · ${esc(d.t)}</p>
    <table><tr><th>Servicio</th><th>Estado</th><th>Depende de</th></tr>${filas}</table>`;
}

function filasDecision(lst) {
  return lst.map((x) =>
    `<tr><td>${esc(x.timestamp)}</td><td>${esc(x.activo)}</td><td>${esc(x.clase)}</td><td>${esc(x.accion_final)}</td><td>${x.requiere_humano ? "humano" : "auto"}</td></tr>`).join("");
}
async function pintarDecisiones() {
  const lst = await json("/api/decisiones");
  $("#decisiones").innerHTML = lst.length
    ? `<table><tr><th>Cuándo</th><th>Activo</th><th>Clase</th><th>Acción</th><th></th></tr>${filasDecision(lst)}</table>`
    : "<p>sin decisiones todavía</p>";
}

async function aprobar(id, respuesta) {
  await fetch("/api/aprobar", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id, respuesta }) });
  pintarPendientes();
}
async function pintarPendientes() {
  const lst = await json("/api/pendientes");
  $("#n-pend").textContent = lst.length ? "(" + lst.length + ")" : "";
  $("#aprobaciones").innerHTML = lst.length ? lst.map((p) => {
    const ctrl = p.tipo === "escalada"
      ? `<button class="aprobar" onclick="aprobar('${p.id}','s')">Aprobar</button><button class="rechazar" onclick="aprobar('${p.id}','')">Rechazar</button>`
      : `<button class="aprobar" onclick="aprobar('${p.id}','1')">Aprobar (1)</button><button class="rechazar" onclick="aprobar('${p.id}','2')">Rechazar (2)</button>
         <input id="r-${p.id}" size="3" placeholder="otra"><button onclick="aprobar('${p.id}',document.getElementById('r-${p.id}').value)">Enviar</button>`;
    return `<div class="tarjeta"><pre>${esc((p.lineas || []).join("\n"))}</pre><p>${esc(p.prompt)}</p>${ctrl}</div>`;
  }).join("") : "<p>ninguna decisión esperando</p>";
}

async function pintarTrazas() {
  const lst = await json("/api/trazas");
  const v = await json("/api/verificar");
  const cadena = v.ok ? '<span class="ok">cadena íntegra</span>' : `<span class="caido">cadena rota en ${esc(v.roto_en)}: ${esc(v.motivo)}</span>`;
  $("#trazas").innerHTML = `<p>${cadena} · <button onclick="pintarTrazas()">verificar</button></p>` +
    (lst.length ? `<table><tr><th>Cuándo</th><th>Activo</th><th>Clase</th><th>Acción</th></tr>${filasDecision(lst)}</table>` : "<p>sin trazas</p>");
}

function refrescar() { pintarSalud(); pintarDecisiones(); pintarPendientes(); pintarTrazas(); }
refrescar();
setInterval(refrescar, 2000);
