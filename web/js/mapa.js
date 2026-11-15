montarNav("/ui/mapa");
const ESTILO_ONLINE = "https://tiles.openfreemap.org/styles/liberty";     // vetorial: já traz países, estados e cidades
const ESTILO_LOCAL = () => ({version: 8, sources: {paises: {type: "geojson", data: location.origin + "/vendor/paises.geojson"}}, layers: [
  {id: "fundo", type: "background", paint: {"background-color": "#dce8ee"}},
  {id: "paises-f", type: "fill", source: "paises", paint: {"fill-color": "#f6f1e6"}},
  {id: "paises-l", type: "line", source: "paises", paint: {"line-color": "#c9bd9c", "line-width": 0.7}}]});
let V, M, LUGARES = [], map = null, modo = "local", tipos = new Set(["author", "work", "periodical", "event", "institution"]), filtroTag = "", posicionando = null, porLugar = {}, todosPapeisGeograficos = false;
let mapaSvg = false, paisesSvg = null, svgMapa = null, projecaoSvg = null, zoomSvg = null, grupoSvg = null, pontosSvg = null;

(async function () {
  V = await vocab();
  await carregar(); lado();
  let seguroSolicitado = false;
  try { seguroSolicitado = new URLSearchParams(location.search).get("render") === "svg" || sessionStorage.getItem("litdex.map.safeSvg") === "1"; } catch (_) {}
  if (seguroSolicitado || !window.maplibregl || !window.d3?.geoNaturalEarth1 || !window.d3?.geoPath) {
    await iniciarMapaSvg(seguroSolicitado ? "modo seguro selecionado" : "MapLibre/WebGL ou D3 geográfico indisponível"); return;
  }
  modo = await escolherModo(); iniciarMapa();
})();

async function escolherModo() {
  if (!navigator.onLine) return "local";
  try { const c = new AbortController(), t = setTimeout(() => c.abort(), 3500); const r = await fetch(ESTILO_ONLINE, {signal: c.signal}); clearTimeout(t); return r.ok ? "online" : "local"; } catch (e) { return "local"; }
}
async function carregar() { [M, LUGARES] = await Promise.all([api("/api/mapa" + (todosPapeisGeograficos ? "?todos=1" : "")), api("/api/lugares")]); porLugar = Object.fromEntries(M.pontos.map(p => [p.place_id, p])); }

function iniciarMapa() {
  try { map = new maplibregl.Map({container: "map", style: modo === "online" ? ESTILO_ONLINE : ESTILO_LOCAL(), center: [-35, 10], zoom: 1.8, attributionControl: {compact: true}, antialias: false}); }
  catch (e) { iniciarMapaSvg(e); return; }
  map.addControl(new maplibregl.NavigationControl({showCompass: false}), "bottom-right");
  map.on("load", camadas); map.on("click", aoClicar);
  map.on("error", ev => {
    const msg = String(ev.error?.message || ev.error || "");
    if (!mapaSvg && /webgl|context lost|could not create a webgl/i.test(msg)) { const causa = ev.error || msg; try { map.remove(); } catch (_) {} map = null; iniciarMapaSvg(causa); return; }
    if (modo === "online" && /style|Failed to fetch|NetworkError/i.test(msg)) { aviso("sem acesso aos mapas online — usando o mapa simples"); trocarModo("local"); }
  });
  estado();
}

// Fallback cartográfico sem WebGL: usa GeoJSON local + SVG/D3, sem acesso de rede externa.
async function iniciarMapaSvg(motivo) {
  mapaSvg = true; map = null; modo = "svg";
  try { sessionStorage.setItem("litdex.map.safeSvg", "1"); } catch (_) {}
  const host = $("#map"); host.innerHTML = '<div class="vazio" style="padding:2rem">Carregando mapa SVG local…</div>';
  try {
    if (!window.d3?.geoNaturalEarth1 || !window.d3?.geoPath) throw new Error("D3 geográfico não carregado");
    const r = await fetch("/vendor/paises.geojson");
    if (!r.ok) throw new Error("GeoJSON local indisponível (HTTP " + r.status + ")");
    paisesSvg = await r.json(); montarMapaSvg(); estado();
    window.__mapaSvgPronto = true;
    aviso("Mapa em modo seguro SVG, sem WebGL. " + (motivo?.message || ""));
  } catch (e) {
    host.innerHTML = `<div class="vazio" style="padding:2rem">Não foi possível iniciar o mapa seguro SVG. ${esc(e.message)}</div>`;
    $("#estado").textContent = "mapa indisponível";
  }
}
function montarMapaSvg() {
  const host = $("#map"), w = Math.max(360, host.clientWidth || 900), h = Math.max(260, host.clientHeight || 600);
  host.innerHTML = ""; document.querySelectorAll(".controles-mapa-svg").forEach(x => x.remove());
  const svg = d3.select(host).append("svg").attr("class", "mapa-svg-seguro").attr("viewBox", `0 0 ${w} ${h}`).attr("width", "100%").attr("height", "100%").style("display", "block").style("touch-action", "none").style("cursor", posicionando ? "crosshair" : "grab");
  const proj = d3.geoNaturalEarth1().fitExtent([[18, 18], [w - 18, h - 18]], paisesSvg), path = d3.geoPath(proj), g = svg.append("g");
  g.append("g").attr("class", "paises-svg").selectAll("path").data(paisesSvg.features || []).join("path").attr("d", path).attr("fill", "#f6f1e6").attr("stroke", "#c9bd9c").attr("stroke-width", .65).attr("vector-effect", "non-scaling-stroke");
  pontosSvg = g.append("g").attr("class", "pontos-mapa-svg");
  projecaoSvg = proj; svgMapa = svg; grupoSvg = g;
  zoomSvg = d3.zoom().scaleExtent([1, 12]).on("zoom", e => { g.attr("transform", e.transform); pontosSvg.selectAll("text").style("display", e.transform.k >= 1.3 ? "" : "none"); });
  svg.call(zoomSvg).on("dblclick.zoom", null).on("click", e => {
    if (e.target.closest?.(".svg-ponto")) return;
    if (posicionando) {
      const xy = d3.pointer(e, svg.node()), inv = d3.zoomTransform(svg.node()).invert(xy), ll = proj.invert(inv);
      if (ll && Number.isFinite(ll[0]) && Number.isFinite(ll[1]) && Math.abs(ll[1]) <= 90) fixar(ll[1], ll[0]);
    } else $("#info").style.display = "none";
  });
  desenharPontosSvg();
  const ctl = el("div", {class:"controles-mapa-svg", style:"position:absolute;right:.8rem;bottom:3.5rem;z-index:4;display:flex;flex-direction:column;gap:.3rem"},
    el("button", {class:"mini", title:"aproximar", onclick:()=>aplicarZoomSvg(1.5)}, "+"),
    el("button", {class:"mini", title:"afastar", onclick:()=>aplicarZoomSvg(1/1.5)}, "−"),
    el("button", {class:"mini", title:"visão global", onclick:()=>aplicarZoomSvg(1,true)}, "mundo"));
  $("#palco").append(ctl);
  window.addEventListener("resize", redimensionarMapaSvg, {once:true});
}
function aplicarZoomSvg(fator, global=false) {
  if (!svgMapa || !zoomSvg) return;
  const node = svgMapa.node(), t = d3.zoomTransform(node);
  if (global) { svgMapa.call(zoomSvg.transform, d3.zoomIdentity); return; }
  const k = Math.max(1, Math.min(12, t.k * fator));
  const [px, py] = [node.clientWidth || 900, node.clientHeight || 600];
  const c = t.invert([px/2, py/2]);
  svgMapa.call(zoomSvg.transform, d3.zoomIdentity.translate(px/2-c[0]*k, py/2-c[1]*k).scale(k));
}
function centralizarSvg(lon, lat, zoom=4) {
  if (!svgMapa || !zoomSvg || !projecaoSvg) return;
  const node=svgMapa.node(), w=node.clientWidth||900, h=node.clientHeight||600, pt=projecaoSvg([+lon,+lat]);
  if (!pt) return;
  const k=Math.max(1,Math.min(12,zoom));
  svgMapa.call(zoomSvg.transform,d3.zoomIdentity.translate(w/2-pt[0]*k,h/2-pt[1]*k).scale(k));
}
function redimensionarMapaSvg() { if (mapaSvg && paisesSvg) montarMapaSvg(); else map?.resize(); }
function desenharPontosSvg() {
  if (!pontosSvg || !projecaoSvg || !M) return;
  const dados = M.pontos.filter(p => p.lat != null && p.lon != null && Number.isFinite(+p.lat) && Number.isFinite(+p.lon)).map(p => {
    const vis = p.itens.filter(i => tipos.has(i.tipo)); const c = {};
    vis.forEach(i => c[i.tipo] = (c[i.tipo] || 0) + 1);
    const dom = Object.entries(c).sort((a,b)=>b[1]-a[1])[0]?.[0] || "work";
    return {...p, itensVisiveis:vis, cor:V.entidades[dom]?.cor || "#8b3a1f", destino:!filtroTag || p.itens.some(i=>i.tags.includes(filtroTag))};
  });
  const grupos = pontosSvg.selectAll("g.svg-ponto").data(dados,d=>d.place_id).join(
    enter => { const g=enter.append("g").attr("class","svg-ponto").style("cursor","pointer");
      g.append("circle").attr("stroke","#fff").attr("stroke-width",1.6).attr("vector-effect","non-scaling-stroke");
      g.append("text").attr("y",-10).attr("text-anchor","middle").attr("font-size",11).attr("font-family","system-ui,sans-serif").attr("fill","#2b2620").attr("paint-order","stroke").attr("stroke","#fff").attr("stroke-width",3).attr("pointer-events","none");
      g.append("title"); return g; }, update=>update, exit=>exit.remove());
  grupos.attr("transform",d=>{const q=projecaoSvg([+d.lon,+d.lat]);return q?`translate(${q[0]},${q[1]})`:"translate(-100,-100)";})
    .attr("opacity",d=>d.destino ? .94 : .20)
    .on("click",(e,d)=>{e.stopPropagation(); if(posicionando) fixar(d.lat,d.lon); else detalhe(porLugar[d.place_id]||d);});
  grupos.select("circle").attr("r",d=>5+Math.min(7,Math.sqrt(d.itensVisiveis.length)*2)).attr("fill",d=>d.cor);
  grupos.select("text").text(d=>d.nome).style("display",d=>d3.zoomTransform(svgMapa.node()).k>=1.3?"":"none");
  grupos.select("title").text(d=>`${d.nome} · ${d.itensVisiveis.length} ficha(s)`);
}
async function ativarModoSeguroSvg() {
  try { sessionStorage.setItem("litdex.map.safeSvg", "1"); } catch (_) {}
  if (map) { try { map.remove(); } catch (_) {} map = null; }
  await iniciarMapaSvg("modo seguro ativado manualmente");
}
function voltarAoWebGL() {
  try { sessionStorage.removeItem("litdex.map.safeSvg"); } catch (_) {}
  location.reload();
}
function trocarModo(novo) {
  if (mapaSvg) { aviso("Mapa seguro SVG ativo; WebGL está desativado nesta visualização."); return; }
  if (!map || novo === modo) return; modo = novo;
  map.setStyle(modo === "online" ? ESTILO_ONLINE : ESTILO_LOCAL()); map.once("style.load", camadas); estado();
}
function estado() { $("#estado").textContent = mapaSvg ? "modo seguro SVG · sem WebGL" : modo === "online" ? "mapa detalhado (online) · países, estados e cidades" : "mapa simples (offline)"; lado(); }

/* ---------------- pontos: um por lugar, agrupados quando se sobrepõem ---------------- */
function geojson() {
  const feats = M.pontos.map(p => ({...p, itens: p.itens.filter(i => tipos.has(i.tipo))})).map(p => {
    const c = {}; p.itens.forEach(i => c[i.tipo] = (c[i.tipo] || 0) + 1);
    const dom = Object.entries(c).sort((a, b) => b[1] - a[1])[0]?.[0] || "work";
    return {type: "Feature", geometry: {type: "Point", coordinates: [p.lon, p.lat]},
      properties: {place_id: p.place_id, nome: p.nome, tipo_lugar: p.tipo, n: p.itens.length, cor: V.entidades[dom].cor, dest: !filtroTag || p.itens.some(i => i.tags.includes(filtroTag))}};
  });
  return {type: "FeatureCollection", features: feats};
}
function camadas() {
  if (map.getSource("pontos")) return;
  map.addSource("pontos", {type: "geojson", data: geojson(), cluster: true, clusterRadius: 38, clusterMaxZoom: 6});
  map.addLayer({id: "grupos", type: "circle", source: "pontos", filter: ["has", "point_count"],
    paint: {"circle-color": "#8b3a1f", "circle-opacity": .85, "circle-radius": ["step", ["get", "point_count"], 15, 5, 20, 20, 26], "circle-stroke-width": 2, "circle-stroke-color": "#fff"}});
  map.addLayer({id: "pontos-c", type: "circle", source: "pontos", filter: ["!", ["has", "point_count"]],
    paint: {"circle-color": ["get", "cor"], "circle-opacity": ["case", ["get", "dest"], 0.92, 0.2], "circle-radius": ["+", 7, ["*", 3, ["sqrt", ["get", "n"]]]], "circle-stroke-width": 1.8, "circle-stroke-color": "#fff"}});
  if (map.getStyle().glyphs) {                                               // com o estilo online há fontes para os rótulos
    try {
      map.addLayer({id: "grupos-n", type: "symbol", source: "pontos", filter: ["has", "point_count"], layout: {"text-field": ["get", "point_count_abbreviated"], "text-font": ["Noto Sans Regular"], "text-size": 12}, paint: {"text-color": "#fff"}});
      map.addLayer({id: "pontos-t", type: "symbol", source: "pontos", filter: ["all", ["!", ["has", "point_count"]], ["!in", ["get", "tipo_lugar"], ["literal", ["país", "pais", "country"]]]],
        layout: {"text-field": ["get", "nome"], "text-font": ["Noto Sans Regular"], "text-size": 12, "text-offset": [0, 1.4], "text-anchor": "top"}, paint: {"text-color": "#2b2620", "text-halo-color": "#fff", "text-halo-width": 1.4}});
    } catch (e) { /* sem rótulos: tudo continua funcionando */ }
  }
  ["grupos", "pontos-c"].forEach(l => { map.on("mouseenter", l, () => map.getCanvas().style.cursor = "pointer"); map.on("mouseleave", l, () => map.getCanvas().style.cursor = posicionando ? "crosshair" : ""); });
  if (M.pontos.length) { const b = new maplibregl.LngLatBounds(); M.pontos.forEach(p => b.extend([p.lon, p.lat])); if (!map._ajustado) { map._ajustado = true; map.fitBounds(b, {padding: 90, maxZoom: 5, duration: 900}); } }
  window.__mapaPronto = true;
}
function redesenhar() {
  if (mapaSvg) { desenharPontosSvg(); return; }
  map?.getSource("pontos")?.setData(geojson());
}
function focalizarLugar(it) {
  if (map) map.flyTo({center:[it.lon,it.lat],zoom:it.tipo === "pais" ? 4 : it.tipo === "estado" ? 5.5 : 8});
  else if (mapaSvg) centralizarSvg(it.lon,it.lat,it.tipo === "pais" ? 2 : it.tipo === "estado" ? 3.5 : 5);
}
function cursorMapa(cursor) {
  if (map) map.getCanvas().style.cursor = cursor;
  else if (svgMapa) svgMapa.style("cursor",cursor);
}

function aoClicar(e) {
  if (posicionando) return fixar(e.lngLat.lat, e.lngLat.lng);
  const f = map.queryRenderedFeatures(e.point, {layers: ["grupos", "pontos-c"].filter(l => map.getLayer(l))})[0];
  if (!f) { $("#info").style.display = "none"; return; }
  if (f.properties.cluster_id != null) { map.getSource("pontos").getClusterExpansionZoom(f.properties.cluster_id).then(z => map.easeTo({center: f.geometry.coordinates, zoom: z + .3})); return; }
  detalhe(porLugar[f.properties.place_id]);
}
async function fixar(lat, lon, extra = {}) {
  const p = posicionando; if (!p) return;
  try { await api(`/api/lugares/${p.place_id}`, {method: "PATCH", body: {lat: +(+lat).toFixed(4), lon: +(+lon).toFixed(4), ...extra}}); aviso("posicionado: " + p.nome); sair(); await carregar(); redesenhar(); lado(); if (map) map.flyTo({center: [lon, lat], zoom: Math.max(map.getZoom(), 4)}); else centralizarSvg(lon,lat,4); }
  catch (er) { aviso(er.message); }
}
function sair() { posicionando = null; $("#modo").style.display = "none"; cursorMapa(""); lado(); }
document.addEventListener("keydown", e => { if (e.key === "Escape") sair(); });

function detalhe(p) {
  const i = $("#info"); i.innerHTML = ""; i.style.display = "block";
  const coords = (typeof p.lat === "number" && typeof p.lon === "number")
    ? `${p.lat.toFixed(2)}, ${p.lon.toFixed(2)}` : "sem coordenadas";
  i.append(el("button", {class: "x", onclick: () => i.style.display = "none"}, "×"), el("h3", {}, p.nome),
    el("div", {class: "muted"}, [p.caminho && p.caminho !== p.nome ? p.caminho : p.contexto, coords].filter(Boolean).join(" · ")));
  // o ponto no mapa pode ser um ancestral que apenas posiciona; o lugar atribuído
  // a cada ficha é mostrado separadamente, para não confundir os dois
  const atribuidos = (p.lugares_atribuidos || []).filter(l => l.nome && l.nome !== p.nome);
  if (atribuidos.length) {
    i.append(el("p", {class: "teoria"}, "Lugar atribuído nas fichas: ",
      atribuidos.map(l => el("span", {class: "chip"}, l.nome)).reduce((a, b) => [a, " ", b], [])));
  }
  const ul = el("ul", {class: "rel-lista"});
  p.itens.filter(x => tipos.has(x.tipo)).forEach(x => ul.append(el("li", {},
    el("span", {class: "dot " + x.tipo}), el("a", {href: urlFicha(x.tipo, x.id)}, x.nome),
    x.lugar_atribuido && x.lugar_atribuido !== p.nome ? el("span", {class: "meta"}, " · " + x.lugar_atribuido) : "",
    x.papel ? el("span", {class: "meta"}, " · " + x.papel) : "",
    x.tags.length ? el("span", {class: "meta"}, x.tags.join(", ")) : "")));
  i.append(ul, el("button", {class:"mini", onclick: () => editarLugar(p)}, "editar lugar canônico"), el("button", {class:"mini", style:"margin-left:.3rem", onclick: () => associarLugar(p)}, "associar a uma ficha"));
}

async function criarLugar() {
  const nome=el("input",{placeholder:"nome canônico do lugar",style:"width:100%"});
  const tipo=el("select",{style:"width:100%"},...[["","tipo não definido"],["país","País"],["estado","Estado / província"],["cidade","Cidade"],["histórico","Lugar histórico"],["outro","Outro"]].map(([v,t])=>el("option",{value:v},t)));
  const contexto=el("input",{placeholder:"contexto para distinguir homônimos (ex.: país/estado)",style:"width:100%"});
  const lat=el("input",{placeholder:"latitude (opcional)",style:"width:100%"}),lon=el("input",{placeholder:"longitude (opcional)",style:"width:100%"});
  const status=el("div",{class:"muted"});
  const box=el("div",{style:"position:absolute;inset:12% 8%;z-index:9;background:var(--paper);border:1px solid var(--rule);border-radius:12px;padding:1rem;box-shadow:var(--sombra);overflow:auto"},el("button",{class:"x",onclick:()=>box.remove()},"×"),el("h3",{},"Novo lugar canônico"),el("p",{class:"teoria"},"O sistema reutiliza um registro de mesmo nome/contexto quando ele já existe; homônimos ambíguos exigem contexto."),el("label",{},"Nome",nome),el("label",{},"Tipo",tipo),el("label",{},"Contexto",contexto),el("label",{},"Latitude",lat),el("label",{},"Longitude",lon),el("button",{class:"primario",onclick:async()=>{try{const r=await api("/api/lugares",{method:"POST",body:{nome:nome.value,tipo:tipo.value,contexto:contexto.value,lat:lat.value||null,lon:lon.value||null}});box.remove();await carregar();redesenhar();lado();const p=LUGARES.find(x=>x.id===r.id);if(p) editarLugar(p);aviso(r.existente?"lugar canônico reutilizado":"lugar cadastrado");}catch(e){status.textContent=e.message;aviso(e.message);}}},"salvar lugar"),status);
  $("#palco").append(box);
}
async function associarLugar(p) {
  const loc=LUGARES.find(x=>x.id===(p.place_id||p.id))||p;
  const tipo=el("select",{style:"width:100%"},...[["author","Autor"],["work","Obra"],["periodical","Periódico"],["event","Evento"]].map(([v,t])=>el("option",{value:v},t)));
  const entidade=el("select",{style:"width:100%"},el("option",{value:""},"selecione uma ficha"));
  const papel=el("input",{placeholder:"papel geográfico (ex.: nascimento, escrita, publicação)",style:"width:100%"});
  const status=el("div",{class:"muted"});
  async function carregarEntidades(){try{const xs=await api(`/api/entidades/${tipo.value}?todos=1`);entidade.innerHTML="";entidade.append(el("option",{value:""},"selecione uma ficha"));xs.forEach(x=>entidade.append(el("option",{value:x.id},x.nome+(x.sub?` · ${x.sub}`:""))));}catch(e){status.textContent=e.message;}}
  tipo.onchange=carregarEntidades; await carregarEntidades();
  const box=el("div",{style:"position:absolute;inset:12% 8%;z-index:9;background:var(--paper);border:1px solid var(--rule);border-radius:12px;padding:1rem;box-shadow:var(--sombra);overflow:auto"},el("button",{class:"x",onclick:()=>box.remove()},"×"),el("h3",{},"Associar lugar a uma ficha"),el("p",{class:"teoria"},`${loc.nome}: a associação registra o contexto geográfico da entidade; não altera autoria, influência ou outras relações literárias.`),el("label",{},"Tipo de ficha",tipo),el("label",{},"Ficha",entidade),el("label",{},"Papel do lugar",papel),el("button",{class:"primario",onclick:async()=>{try{if(!entidade.value)throw new Error("Selecione uma ficha.");const r=await api(`/api/entidades/${tipo.value}/${entidade.value}/lugares`,{method:"POST",body:{nome:loc.nome,contexto:loc.contexto||loc.caminho||"",tipo:loc.tipo,lat:loc.lat,lon:loc.lon,papel:papel.value}});box.remove();await carregar();redesenhar();lado();aviso("lugar associado à ficha");const ponto=porLugar[r.place_id];if(ponto)detalhe(ponto);}catch(e){status.textContent=e.message;aviso(e.message);}}},"associar lugar"),status);
  $("#palco").append(box);
}

function editarLugar(p) {
  if(!p) return; const atual=LUGARES.find(x=>x.id===p.place_id||x.id===p.id)||p;
  const nome=el("input",{value:atual.nome||"",style:"width:100%"}),tipo=el("input",{value:atual.tipo||"",placeholder:"país / estado / cidade / histórico",style:"width:100%"}),contexto=el("input",{value:atual.contexto||"",placeholder:"contexto",style:"width:100%"}),lat=el("input",{value:atual.lat??"",placeholder:"latitude",style:"width:100%"}),lon=el("input",{value:atual.lon??"",placeholder:"longitude",style:"width:100%"}),notas=el("textarea",{rows:2,placeholder:"notas geográficas",style:"width:100%;box-sizing:border-box"});notas.value=atual.notas||"";
  const pai=el("select",{style:"width:100%"},el("option",{value:""},"sem lugar superior"),...LUGARES.filter(x=>x.id!==atual.id).map(x=>el("option",{value:x.id},x.caminho||x.nome)));pai.value=atual.parent_id||"";
  const status=el("div",{class:"muted"});
  const box=el("div",{style:"position:absolute;inset:8% 8%;z-index:9;background:var(--paper);border:1px solid var(--rule);border-radius:12px;padding:1rem;box-shadow:var(--sombra);overflow:auto"},el("button",{class:"x",onclick:()=>box.remove()},"×"),el("h3",{},"Editar lugar canônico"),el("p",{class:"teoria"},`ID ${atual.id}. Alterações neste registro refletem em todas as fichas associadas.`),el("label",{},"Nome",nome),el("label",{},"Tipo",tipo),el("label",{},"Contexto",contexto),el("label",{},"Lugar superior",pai),el("label",{},"Latitude",lat),el("label",{},"Longitude",lon),el("label",{},"Notas",notas),
    el("button",{class:"primario",onclick:async()=>{try{await api(`/api/lugares/${atual.id}`,{method:"PATCH",body:{nome:nome.value,tipo:tipo.value,contexto:contexto.value,parent_id:pai.value||null,lat:lat.value||null,lon:lon.value||null,notas:notas.value}});box.remove();await carregar();redesenhar();lado();aviso("lugar atualizado");}catch(e){status.textContent=e.message;aviso(e.message);}}},"salvar alterações"),
    el("button",{class:"mini",onclick:()=>{posicionando={place_id:atual.id,nome:nome.value};box.remove();$("#modo").style.display="block";$("#modo").textContent=`clique no mapa para posicionar «${nome.value}» (Esc cancela)`;cursorMapa("crosshair");lado();}},"posicionar clicando no mapa"),status);
  $("#palco").append(box);
}

/* ---------------- painel lateral ---------------- */
function lado() {
  if (!M) return; const l = $("#lado"); l.innerHTML = "";
  l.append(el("h4", {}, "Mostrar"));
  [["author", "Autores"], ["work", "Obras"], ["periodical", "Periódicos"], ["event", "Eventos"], ["institution", "Instituições"]].forEach(([t, n]) => l.append(el("label", {}, el("input", {type: "checkbox", checked: tipos.has(t), onchange: e => { e.target.checked ? tipos.add(t) : tipos.delete(t); redesenhar(); }}), " ", el("span", {class: "dot " + t}), n)));
  const sel = el("select", {style: "width:100%", onchange: e => { filtroTag = e.target.value; redesenhar(); }}, new Option("— todas as tags —", ""), M.tags.map(t => new Option(t, t))); sel.value = filtroTag;
  l.append(el("h4", {}, "Tag em destaque"), sel, el("div", {class: "teoria", style: "margin-top:.3rem"}, "realça no mapa o que a tag reúne."));
  l.append(el("h4", {}, "Atribuições geográficas"), el("label", {}, el("input", {type: "checkbox", checked: todosPapeisGeograficos, onchange: async e => {
    todosPapeisGeograficos = e.target.checked; await carregar(); porLugar = Object.fromEntries(M.pontos.map(p => [p.place_id, p])); redesenhar(); lado();
  }}), " Mostrar todos os papéis (nascimento, escrita, publicação…)"), el("div", {class: "teoria"}, "Desmarcado: usa apenas o lugar principal da ficha."));
  l.append(el("h4", {}, "Ir para um lugar"));
  const busca = el("input", {placeholder: posicionando ? `onde fica «${posicionando.nome}»?` : "país, estado ou cidade…", style: "width:100%"});
  l.append(buscaLugar(busca, {onPick: it => { if (posicionando) fixar(it.lat, it.lon, {tipo: it.tipo, contexto: it.contexto}); else focalizarLugar(it); }, onLivre: it => aviso("escolha um item da lista")}));
  l.append(el("h4", {}, "Lugares sem coordenada"));
  if (!M.sem_coordenada.length) l.append(el("div", {class: "muted"}, "nenhum"));
  M.sem_coordenada.forEach(s => l.append(el("div", {class: "semc"}, el("span", {}, `${s.nome} (${s.n})`),
    el("button", {class: "mini", onclick: () => { posicionando = s; $("#modo").style.display = "block"; $("#modo").textContent = `clique no mapa — ou busque ao lado — para posicionar «${s.nome}» (Esc cancela)`; cursorMapa("crosshair"); lado(); }}, posicionando === s ? "…" : "posicionar"))));
  l.append(el("h4", {}, "Catálogo canônico de lugares"),
    el("p", {class:"teoria"}, "O mapa inclui lugares com ou sem ficha associada. Edite aqui o registro canônico; as associações geográficas das fichas continuam compartilhadas."),
    el("button", {class:"mini", onclick: criarLugar}, "＋ cadastrar lugar"));
  const filtroLugar = el("input", {placeholder:"buscar lugar cadastrado…", style:"width:100%"});
  const listaLugares = el("div", {style:"margin-top:.35rem"});
  const desenharLugares = () => { listaLugares.innerHTML=""; const q=filtroLugar.value.trim().toLocaleLowerCase(); const xs=LUGARES.filter(x=>!q || `${x.nome} ${x.contexto||""} ${x.tipo||""}`.toLocaleLowerCase().includes(q)).slice(0,12); xs.forEach(x=>listaLugares.append(el("div",{class:"semc"},el("span",{},x.nome,el("small",{class:"muted",style:"display:block"},x.caminho||x.contexto||"sem contexto")),el("button",{class:"mini",onclick:()=>editarLugar(x)},"editar")))); if(!xs.length)listaLugares.append(el("div",{class:"muted"},"nenhum lugar encontrado")); };
  filtroLugar.oninput=desenharLugares; l.append(filtroLugar,listaLugares); desenharLugares();
  l.append(el("h4", {}, "Mapa"), mapaSvg
    ? el("div", {}, el("button", {class:"mini primario", onclick:()=>aviso("Modo seguro SVG ativo; nenhuma camada WebGL está sendo usada.")}, "modo seguro SVG · sem WebGL"), el("button", {class:"mini", style:"margin-top:.25rem", onclick:voltarAoWebGL}, "voltar ao mapa WebGL"))
    : el("div", {}, el("div", {style:"display:flex;gap:.4rem"}, ["online", "local"].map(m => el("button", {class: "mini" + (modo === m ? " primario" : ""), style: modo === m ? "border-style:solid" : "", onclick: () => trocarModo(m)}, m === "online" ? "detalhado" : "simples"))), el("button", {class:"mini", style:"margin-top:.35rem", onclick:ativarModoSeguroSvg}, "usar modo seguro SVG (sem WebGL)")));
  l.append(el("div", {class: "teoria", style: "margin-top:.6rem"}, "O lugar é opcional: autores não precisam de local de nascimento. Periódicos e eventos são os que mais ganham com um lugar. O ★ da ficha fixa o ponto."));
}
