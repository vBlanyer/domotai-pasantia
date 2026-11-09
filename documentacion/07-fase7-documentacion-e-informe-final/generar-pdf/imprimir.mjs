// Imprime un HTML a PDF con Chromium headless vía CDP: A4, pie con número de página y marcadores.
// Uso: node imprimir.mjs entrada.html salida.pdf
import { spawn } from "node:child_process"
import { writeFileSync } from "node:fs"
import { pathToFileURL } from "node:url"
const [,, entrada, salida] = process.argv
const chrome = spawn(process.env.CHROME ?? "chromium",
  ["--headless=new", "--no-sandbox", "--disable-gpu", "--remote-debugging-port=9334", "about:blank"], { stdio: "ignore" })
const espera = (ms) => new Promise((r) => setTimeout(r, ms))
let tabs
for (let i = 0; i < 50; i++) { try { tabs = await (await fetch("http://127.0.0.1:9334/json")).json(); if (tabs.length) break } catch {} await espera(200) }
const ws = new WebSocket(tabs.find((t) => t.type === "page").webSocketDebuggerUrl)
await new Promise((r) => ws.addEventListener("open", r))
let id = 0; const pend = new Map()
ws.addEventListener("message", (m) => { const d = JSON.parse(m.data); if (d.id && pend.has(d.id)) { pend.get(d.id)(d); pend.delete(d.id) } })
const cmd = (method, params = {}) => new Promise((r) => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })) })
await cmd("Page.navigate", { url: pathToFileURL(entrada).href }); await espera(2000)
const pie = `<div style="width:100%;font-family:'Ubuntu Sans',sans-serif;font-size:8px;color:#5b6573;padding:0 18mm;display:flex;justify-content:space-between">
  <span>Manual de usuario · MDR de triaje asistido</span><span>Página <span class="pageNumber"></span> de <span class="totalPages"></span></span></div>`
const r = await cmd("Page.printToPDF", {
  paperWidth: 8.27, paperHeight: 11.69, marginTop: 0.79, marginBottom: 0.79, marginLeft: 0.71, marginRight: 0.71,
  printBackground: true, preferCSSPageSize: true, displayHeaderFooter: true,
  headerTemplate: "<div></div>", footerTemplate: pie, generateDocumentOutline: true, generateTaggedPDF: true,
})
if (r.error) { console.error(JSON.stringify(r.error)); process.exit(1) }
writeFileSync(salida, Buffer.from(r.result.data, "base64")); ws.close(); chrome.kill(); console.log("ok", salida)
