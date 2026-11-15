montarNav("/ui/grafo");
const Q = new URLSearchParams(location.search);
const S = {projecao: "nenhuma", tipos: new Set(["author", "work", "manifestation", "periodical", "event", "institution"]), familias: null, camadas: new Set(),
           foco: Q.get("foco") || null, prof: 2, rotulos: true, mostrarDatas: true, ordenarTempo: false, modoEdicao: false, edicaoConjunto: false, rotacaoViva: false, fpsReduzido: true, selecionados: []};
let V, G = null, sim = null, POS = {}, usuarioMexeu = false, pausado = false;
let sequenciaDesenho = 0, sequenciaCarga = 0, ultimaPintura = 0; // invalida respostas/eventos obsoletos
const SIMBOLO = () => ({circle: d3.symbolCircle, square: d3.symbolSquare, diamond: d3.symbolDiamond, triangle: d3.symbolTriangle, star: d3.symbolStar,
  // D3 7.9 não inclui symbolHexagon; desenhamos um hexágono regular como tipo de símbolo customizado.
  hexagon: {draw(context, size) { const r = Math.sqrt(2 * size / (3 * Math.sqrt(3))); for (let i = 0; i < 6; i++) { const a = Math.PI / 3 * i - Math.PI / 6; const x = r * Math.cos(a), y = r * Math.sin(a); i ? context.lineTo(x, y) : context.moveTo(x, y); } context.closePath(); }},
  wye: d3.symbolWye});
const DESCRITORES = {manifestation: {rotulo: "Objeto / manifestação", plural: "Objetos / manifestações", cor: "#b36c2e", simbolo: "wye"}};
const descritor = tipo => DESCRITORES[tipo] || V.entidades[tipo] || {rotulo: tipo, plural: tipo, cor: "#999", simbolo: "square"};

(async function () {
  V = await vocab(); S.familias = new Set(V.familias.map(f => f.chave));
  if (!window.d3) { $("#vazio").style.display = "flex"; $("#vazio").textContent = "d3 não encontrado em data/vendor — abra o LitDex uma vez com internet para baixar as bibliotecas."; return; }
  controles(); barra(); carregar();
})();

function controles() {
  const c = $("#controles"); c.innerHTML = "";
  const radio = (v, t, d) => el("label", {}, el("input", {type: "radio", name: "proj", value: v, checked: S.projecao === v, onchange: () => { S.projecao = v; S.foco = null; carregar(); atualizarEstado(); }}), " " + t, el("div", {class: "teoria", style: "margin-left:1.4rem"}, d));
  c.append(el("h4", {}, "Construção pelo grafo"),
    el("p", {class:"teoria"}, "No modo de edição, selecione dois nós para formular uma relação. Relações hipotéticas ficam marcadas como hipóteses; nenhuma proximidade visual será tratada como prova."),
    el("button", {class: S.modoEdicao ? "primario" : "", onclick: () => { S.modoEdicao = !S.modoEdicao; S.selecionados = []; if (S.modoEdicao) S.projecao = "nenhuma"; controles(); barra(); carregar(); aviso(S.modoEdicao ? "edição do grafo ativa: selecione dois nós" : "edição do grafo encerrada"); }}, S.modoEdicao ? "✓ modo de edição ativo" : "ativar modo de edição"),
    el("button", {class:"mini", style:"margin-top:.35rem", onclick: criarFichaPeloGrafo}, "＋ criar ficha neste grafo"),
    el("label", {style:"margin-top:.4rem"}, el("input", {type:"checkbox", checked:S.edicaoConjunto, onchange:e=>{
      S.edicaoConjunto=e.target.checked; S.selecionados=[];
      if (S.edicaoConjunto) S.modoEdicao=true;
      controles(); barra(); carregar();
      aviso(S.edicaoConjunto ? "edição em conjunto ativa: selecione a origem e depois os destinos" : "edição em conjunto desativada");
    }}), " edição em conjunto"),
    S.edicaoConjunto ? el("button", {class:"mini", onclick:()=>editorRelacaoEmConjunto()}, "relacionar seleção (origem → destinos)") : "",
    S.modoEdicao ? el("div", {class:"teoria"}, S.selecionados.length ? `selecionado: ${S.selecionados.map(id => nomeRef(id)?.nome || id).join(" → ")}` : "Clique em dois nós, na ordem da relação.") : "",
    el("h4", {}, "Como ver"),
    radio("nenhuma", "rizoma completo", "todas as fichas e ligações, sem centro: entre por qualquer nó"),
    radio("autores", "autores ↔ autores", "caminhos por relações entre obras, coautoria, participação em eventos e fascículos identificados; contexto não prova vínculo pessoal"),
    radio("obras", "obras ↔ obras", "relações entre textos e mídias; coaparição só quando o fascículo é identificado"));
  c.append(el("h4", {}, "Entradas"));
  Object.entries(V.entidades).forEach(([t, e]) => c.append(el("label", {class: "tp"}, el("input", {type: "checkbox", checked: S.tipos.has(t), onchange: ev => { ev.target.checked ? S.tipos.add(t) : S.tipos.delete(t); carregar(); }}),
    " ", el("span", {class: "dot " + t}), e.plural)));
  const dm = descritor("manifestation");
  c.append(el("label", {class: "tp"}, el("input", {type: "checkbox", checked: S.tipos.has("manifestation"), onchange: ev => { ev.target.checked ? S.tipos.add("manifestation") : S.tipos.delete("manifestation"); carregar(); }}),
    " ", el("span", {class: "dot manifestation", style: `background:${dm.cor}`}), dm.plural));
  c.append(el("h4", {}, "Famílias de relação"));
  V.familias.forEach(f => c.append(el("label", {class: "fm", title: f.desc}, el("input", {type: "checkbox", checked: true, onchange: ev => { ev.target.checked ? S.familias.add(f.chave) : S.familias.delete(f.chave); carregar(); }}),
    " ", el("span", {class: "dot", style: `background:${f.cor}`}), f.titulo)));
  c.append(el("h4", {}, "Tempo"),
    el("label", {}, el("input", {type: "checkbox", checked: S.mostrarDatas, onchange: ev => { S.mostrarDatas = ev.target.checked; redesenharRotulos(); }}), " mostrar datas nos nós"),
    el("label", {}, el("input", {type: "checkbox", checked: S.ordenarTempo, onchange: ev => { S.ordenarTempo = ev.target.checked; carregar(); }}), " organizar da esquerda para a direita"),
    el("div", {class: "teoria"}, "A ordenação usa anos registrados; fichas sem data ficam na faixa central."));
  c.append(el("h4", {}, "Legenda"),
    el("div", {class: "teoria"}, "Símbolos: círculo = pessoa · quadrado = obra intelectual · roseta = objeto / manifestação concreta · losango = periódico · triângulo = evento · hexágono = instituição · estrela = mídia (oculta por padrão)."),
    el("div", {class: "legenda-familias"}, V.familias.map(f => el("div", {class: "legenda-familia"}, el("span", {class: "dot", style: `background:${f.cor}`}), f.titulo))));
  c.append(el("h4", {}, "Camadas calculadas"), el("div", {class: "teoria"}, "nunca são gravadas"));
  [["contemporaneo", "contemporâneos (vidas que se sobrepõem)"], ["tags", "tags como platôs"], ["lugares", "lugares como platôs"]].forEach(([k, t]) =>
    c.append(el("label", {}, el("input", {type: "checkbox", onchange: ev => { ev.target.checked ? S.camadas.add(k) : S.camadas.delete(k); carregar(); }}), " " + t)));
  c.append(el("h4", {}, "Foco"), el("div", {id: "foco-estado", class: "muted"}, "nenhum — clique duas vezes num nó"),
    el("label", {}, "profundidade: ", el("b", {id: "prof-v"}, S.prof), el("input", {type: "range", min: 1, max: 4, value: S.prof, oninput: ev => { S.prof = +ev.target.value; $("#prof-v").textContent = S.prof; }, onchange: () => S.foco && carregar()})),
    el("button", {class: "mini", onclick: () => { S.foco = null; carregar(); }}, "limpar foco"));
  c.append(el("h4", {}, "Rótulos"), el("label", {}, el("input", {type: "checkbox", checked: true, onchange: ev => { S.rotulos = ev.target.checked; document.querySelectorAll(".no text").forEach(t => t.style.display = S.rotulos ? "" : "none"); }}), " nomes dos nós"));
  c.append(el("h4", {}, "Achar"), (() => { const i = el("input", {placeholder: "nome de uma ficha…", style: "width:100%"}); i.oninput = () => achar(i.value); return i; })());
  atualizarEstado();
}
function atualizarEstado() {
  const p = S.projecao !== "nenhuma";
  document.querySelectorAll("#controles .tp, #controles .fm").forEach(l => { l.classList.toggle("off", p); l.querySelector("input").disabled = p; });
}
function rotuloNo(d) {
  const limite = d.tipo === "work" || d.tipo === "manifestation" ? 21 : 25;
  const nome = d.nome.length > limite ? d.nome.slice(0, limite - 1) + "…" : d.nome;
  return S.mostrarDatas && d.data ? `${nome} · ${d.data}` : nome;
}
function redesenharRotulos() {
  d3.selectAll(".no text").text(rotuloNo).style("display", S.rotulos ? "" : "none");
}
function achar(q) {
  if (!G || q.length < 2) return;
  const n = (window._nos || []).find(x => x.nome.toLowerCase().includes(q.toLowerCase()));
  if (n && n.x != null) { mostrarNo(n); centrar(n); d3.selectAll(".no").filter(d => d.id === n.id).append("circle").attr("class", "achado").transition().delay(1900).remove(); }
}

async function carregar() {
  const requisicao = ++sequenciaCarga;
  const p = new URLSearchParams({projecao: S.projecao, profundidade: S.prof});
  if (S.projecao === "nenhuma") { p.set("tipos", [...S.tipos].join(",") || "none"); p.set("familias", [...S.familias].join(",") || "none"); }
  if (S.camadas.size) p.set("camadas", [...S.camadas].join(","));
  if (S.foco) p.set("foco", S.foco);
  try {
    const resposta = await api("/api/grafo?" + p);
    if (requisicao !== sequenciaCarga) return; // filtros rápidos: só a resposta mais recente pode redesenhar
    G = resposta;
  } catch (e) {
    if (requisicao !== sequenciaCarga) return;
    const v = $("#vazio"); v.style.display = "flex"; v.innerHTML = "";
    v.append(el("div", {}, el("p", {class: "erro"}, "Não consegui montar o grafo: " + e.message), el("button", {onclick: carregar}, "tentar de novo"))); return;
  }
  $("#foco-estado").textContent = S.foco ? "em torno de: " + (G.nos.find(n => n.id === S.foco)?.nome || S.foco) : "nenhum — clique duas vezes num nó";
  usuarioMexeu = false; desenhar();
}

function corFamilia(f) { return (V.familias.find(x => x.chave === f) || {}).cor || "#999"; }
function corAresta(d) {
  // Cor semântica para atos discursivos; outras relações usam a cor da família.
  if (d.tipo === "menciona") return "#7b8794";
  if (d.tipo === "elogia") return "#27865b";
  if (d.tipo === "critica") return "#c34d4d";
  if (d.tipo === "cita") return "#b8860b";
  return d.derivada === "calculada" ? "#b9c4c9" : d.derivada === "projecao" ? "#8a6a4a" : corFamilia(d.familia);
}
function desenhar() {
  const atual = ++sequenciaDesenho;
  const palco = $("#palco"), W = palco.clientWidth, Ht = palco.clientHeight, svg = d3.select("#svg");
  // Interrompe simulação, transições e enquadramentos da vista anterior antes de redesenhar.
  if (sim) { sim.on("tick", null).on("end", null).stop(); sim = null; }
  svg.interrupt(); svg.selectAll("*").interrupt();
  svg.selectAll("*").remove();
  $("#info").style.display = "none";
  const vazio = $("#vazio");
  if (!G.nos.length) {
    vazio.style.display = "flex"; vazio.textContent = "Nada para mostrar com estes filtros. Crie relações nas fichas (bloco «Relações») para o grafo ganhar forma."; $("#resumo").textContent = ""; return;
  }
  vazio.style.display = "none";
  svg.append("defs").append("marker").attr("id", "seta").attr("viewBox", "0 -4 8 8").attr("refX", 16).attr("markerWidth", 6).attr("markerHeight", 6).attr("orient", "auto").append("path").attr("d", "M0,-4L8,0L0,4").attr("fill", "#8a8175");
  const raiz = svg.append("g"); const zoom = d3.zoom().scaleExtent([0.15, 5]).on("zoom", e => { if (e.sourceEvent) usuarioMexeu = true; raiz.attr("transform", e.transform); }); svg.call(zoom).on("dblclick.zoom", null); window._zoom = {svg, zoom, W, Ht};
  const nos = G.nos.map(d => ({...d, ...(POS[d.id] || {x: W / 2 + (Math.random() - .5) * 80, y: Ht / 2 + (Math.random() - .5) * 80})})), lig = G.arestas.map(a => ({...a, source: a.origem, target: a.destino}));
  // Grafos grandes recebem menos efeitos, menos iterações de colisão e pintura limitada a ~30 fps.
  const grafoVolumoso = nos.length >= 80 || lig.length >= 160;
  const animarEntrada = !grafoVolumoso && !window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const l = raiz.append("g").selectAll("line").data(lig).join("line").attr("class", "aresta")
    .attr("stroke", corAresta)
    .attr("stroke-width", d => d.derivada === "projecao" ? Math.min(1.5 + (d.peso || 1) * 1.2, 8) : d.derivada === "estrutural" ? 1.5 : 2)
    .attr("stroke-dasharray", d => d.estatuto === "hipotese" ? "2 5" : d.derivada === "calculada" || d.derivada === "estrutural" ? "4 3" : null).attr("stroke-opacity", d => d.estatuto === "hipotese" ? .65 : .85)
    .attr("marker-end", d => (!d.simetrica && !d.derivada) ? "url(#seta)" : null).on("click", (e, d) => { e.stopPropagation(); mostrarAresta(d); });
  l.append("title").text(d => d.rotulo);
  const sym = SIMBOLO();
  const n = raiz.append("g").selectAll("g").data(nos).join("g").attr("class", d => "no" + (S.selecionados.includes(d.id) ? " selecionado" : ""))
    .call(d3.drag().on("start", (e, d) => { if (!e.active) sim.alphaTarget(.3).restart(); d.fx = d.x; d.fy = d.y; })
      .on("drag", (e, d) => { d.fx = e.x; d.fy = e.y; }).on("end", (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = d.fy = null; }))
    .on("click", (e, d) => { e.stopPropagation(); if (S.modoEdicao) { selecionarNoParaRelacao(d); } else mostrarNo(d); }).on("dblclick", (e, d) => { e.stopPropagation(); if (!["tag", "lugar"].includes(d.tipo)) { S.foco = d.id; carregar(); } })
    .on("mouseover", (e, d) => vizinhos(d, true)).on("mouseout", (e, d) => vizinhos(d, false));
  n.append("path").attr("d", d => d3.symbol().type(sym[descritor(d.tipo).simbolo] || d3.symbolSquare).size(110 + 55 * Math.sqrt(d.grau || 0))())
    .attr("fill", d => descritor(d.tipo).cor).attr("stroke", d => d.id === S.foco ? "#000" : "#fff").attr("stroke-width", d => d.id === S.foco ? 3 : 1.5);
  n.append("text").attr("x", 11).attr("y", 4).text(rotuloNo).style("display", S.rotulos ? "" : "none")
    .style("font-size", d => d.tipo === "manifestation" ? "10px" : "11px")
    .style("paint-order", "stroke").style("stroke", "#fbfaf6").style("stroke-width", "3px").style("stroke-linejoin", "round").style("fill", "#26231f").style("pointer-events", "none");
  n.append("title").text(d => `${descritor(d.tipo).rotulo}: ${d.nome}${d.data ? " · " + d.data : ""}`);
  if (S.ordenarTempo) {
    const anoCronologico = d => Number.isFinite(d.ano) ? d.ano : Number.isFinite(d.fim) ? d.fim : null;
    const temporais = nos.map(anoCronologico).filter(Number.isFinite);
    if (temporais.length) {
      const a = Math.min(...temporais), b = Math.max(...temporais), px0 = 70, px1 = W - 70;
      const xAno = ano => a === b ? W / 2 : px0 + (ano - a) / (b - a) * (px1 - px0);
      const eixo = raiz.insert("g", ":first-child").attr("class", "eixo-temporal");
      eixo.append("line").attr("x1", px0).attr("x2", px1).attr("y1", Ht - 30).attr("y2", Ht - 30).attr("stroke", "#9b9488").attr("stroke-dasharray", "3 4");
      eixo.append("text").attr("x", px0).attr("y", Ht - 12).text(rotuloAno(a));
      eixo.append("text").attr("x", px1).attr("y", Ht - 12).attr("text-anchor", "end").text(rotuloAno(b));
      nos.forEach(d => { const ano = anoCronologico(d); d._xTempo = Number.isFinite(ano) ? xAno(ano) : W / 2; });
    }
  }
  if (animarEntrada) {
    n.style("opacity", 0).transition().delay((d, i) => Math.min(i * 8, 240)).duration(260).style("opacity", 1);
    n.select("path").attr("transform", "scale(.6)").transition().delay((d, i) => Math.min(i * 8, 240)).duration(300).attr("transform", "scale(1)");
  } else {
    n.style("opacity", 1);
    n.select("path").attr("transform", "scale(1)");
  }
  svg.on("click", () => $("#info").style.display = "none");
  sim = d3.forceSimulation(nos)
    .alphaDecay(grafoVolumoso ? 0.055 : 0.04)
    .velocityDecay(0.4)
    .force("link", d3.forceLink(lig).id(d => d.id).distance(d => d.derivada === "calculada" ? 130 : 85).strength(d => d.derivada === "calculada" ? .08 : .5))
    .force("charge", d3.forceManyBody().strength(-340)).force("center", d3.forceCenter(W / 2, Ht / 2))
    // O raio considera o rótulo abreviado; grafos volumosos usam uma passagem de colisão.
    .force("collide", d3.forceCollide(d => Math.max(24, Math.min(78, 15 + rotuloNo(d).length * 2.15))).iterations(grafoVolumoso ? 1 : 2));
  if (S.ordenarTempo && nos.some(d => Number.isFinite(d._xTempo))) {
    sim.force("tempo-x", d3.forceX(d => d._xTempo ?? W / 2).strength(d => Number.isFinite(d._xTempo) ? .62 : .08));
  }
  sim.alpha(POS && Object.keys(POS).length ? (grafoVolumoso ? .35 : .5) : (grafoVolumoso ? .75 : 1));
  sim.on("end", () => { if (S.rotacaoViva && !pausado && !document.hidden && atual === sequenciaDesenho) sim?.alpha(.35).restart(); else if (atual === sequenciaDesenho && !usuarioMexeu) ajustar(!grafoVolumoso); });
  if (S.rotacaoViva) {
    // Mantém o sistema vivo com uma força orbital suave; sem simulação extra ou WebGL.
    sim.force("orbita", alpha => { const cx=W/2, cy=Ht/2; for (const d of nos) { const dx=d.x-cx, dy=d.y-cy; d.vx += (-dy*0.012)*Math.max(alpha, 0.45); d.vy += (dx*0.012)*Math.max(alpha, 0.45); } });
    sim.alphaDecay(0.018).alpha(Math.max(sim.alpha(), 0.35));
  }
  sim.on("tick", () => {
    const agora = performance.now();
    if (agora - ultimaPintura < (S.fpsReduzido || grafoVolumoso ? 33 : 16) && sim.alpha() > sim.alphaMin()) return;
    ultimaPintura = agora;
    nos.forEach(d => POS[d.id] = {x: d.x, y: d.y});
    l.attr("x1", d => d.source.x).attr("y1", d => d.source.y).attr("x2", d => d.target.x).attr("y2", d => d.target.y);
    n.attr("transform", d => `translate(${d.x},${d.y})`);
  });
  window._nos = nos; G._nos = nos;
  const fichas = G.nos.filter(x => !["tag", "lugar", "manifestation", "issue"].includes(x.tipo)).length;
  $("#resumo").textContent = `${fichas} ficha(s) · ${G.nos.length} nó(s) · ${G.arestas.length} ligação(ões)` + (S.projecao !== "nenhuma" ? ` · projeção ${S.projecao}` : "") + (grafoVolumoso ? " · modo leve ativo" : "");
  function vizinhos(d, on) {
    const viz = new Set([d.id]); lig.forEach(a => { if (a.source.id === d.id) viz.add(a.target.id); if (a.target.id === d.id) viz.add(a.source.id); });
    n.style("opacity", x => !on || viz.has(x.id) ? 1 : .15); l.style("opacity", a => !on || a.source.id === d.id || a.target.id === d.id ? 1 : .08);
  }
}
function ajustar(anim = true) {
  const z = window._zoom, nos = window._nos; if (!z || !nos?.length) return;
  // Evita espalhar milhares de coordenadas como argumentos (RangeError em grafos grandes).
  let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity, validos = 0;
  for (const d of nos) {
    if (!Number.isFinite(d.x) || !Number.isFinite(d.y)) continue;
    x0 = Math.min(x0, d.x); x1 = Math.max(x1, d.x); y0 = Math.min(y0, d.y); y1 = Math.max(y1, d.y); validos++;
  }
  if (!validos) return;
  const pad = 80;
  const k = Math.min(1.6, Math.max(0.2, Math.min((z.W - 2 * pad) / Math.max(x1 - x0, 1), (z.Ht - 2 * pad) / Math.max(y1 - y0, 1))));
  const t = d3.zoomIdentity.translate(z.W / 2 - k * (x0 + x1) / 2, z.Ht / 2 - k * (y0 + y1) / 2).scale(k);
  (anim ? z.svg.transition().duration(650) : z.svg).call(z.zoom.transform, t);
}
function barra() {
  const b = $("#barra"); b.innerHTML = "";
  const pausa = el("button", {title:pausado ? "Movimento congelado. Clique para retomar." : "Congela ou retoma o movimento das fichas e das ligações", onclick: () => {
    pausado = !pausado;
    if (pausado) sim?.stop();
    else sim?.alpha(S.rotacaoViva ? .35 : .4).restart();
    pausa.textContent = pausado ? "▶ retomar movimento" : "⏸ pausar movimento";
    pausa.title = pausado ? "Movimento congelado. Clique para retomar." : "Congela o movimento das fichas e das ligações.";
    pausa.setAttribute("aria-pressed", String(pausado));
  }}, pausado ? "▶ retomar movimento" : "⏸ pausar movimento");
  pausa.setAttribute("aria-pressed", String(pausado));
  b.append(el("button", {title: "sacudir as fichas (atalho: R)", onclick: () => { pausado = false; sim?.alpha(1).restart(); usuarioMexeu = false; barra(); }}, "↻ agitar"),
    el("button", {title: "enquadrar tudo (atalho: F)", onclick: () => { usuarioMexeu = false; ajustar(); }}, "⤢ ajustar"),
    el("button", {title:"Ativa/desativa a órbita contínua das fichas", onclick:()=>{S.rotacaoViva=!S.rotacaoViva; if (S.rotacaoViva) pausado=false; aviso(S.rotacaoViva?"órbita contínua ativada":"órbita contínua desativada"); carregar(); barra();}}, S.rotacaoViva?"◉ órbita ligada":"○ órbita desligada"),
    el("button", {title:"Alternar limite de FPS", onclick:()=>{S.fpsReduzido=!S.fpsReduzido; aviso(S.fpsReduzido?"FPS reduzido ativado":"FPS normal ativado"); barra();}}, S.fpsReduzido?"FPS reduzido":"FPS normal"), pausa);
}
document.addEventListener("keydown", e => { if (/INPUT|SELECT|TEXTAREA/.test(e.target.tagName)) return; if (e.key === "f") ajustar(); if (e.key === "r") sim?.alpha(1).restart(); });
// Não desperdiça ciclos de layout nem tenta redesenhar enquanto a aba não está visível.
document.addEventListener("visibilitychange", () => {
  if (!sim) return;
  if (document.hidden) sim.stop();
  else if (!pausado && sim.alpha() > sim.alphaMin()) sim.restart();
});
function centrar(n) { const z = window._zoom; if (!z) return; z.svg.transition().duration(500).call(z.zoom.transform, d3.zoomIdentity.translate(z.W / 2 - n.x, z.Ht / 2 - n.y)); }

/* ---------------- painel de detalhe ---------------- */
function painel(...c) { const i = $("#info"); i.innerHTML = ""; i.append(el("button", {class: "x", onclick: () => i.style.display = "none"}, "×"), ...c.flat(9).filter(x => x != null && x !== false)); i.style.display = "block"; }
const nomeRef = (id) => (G._nos || G.nos).find(n => n.id === id);
function mostrarNo(d) {
  const manifestacao = d.tipo === "manifestation", real = !["tag", "lugar", "manifestation"].includes(d.tipo);
  const minhas = G.arestas.filter(a => a.origem === d.id || a.destino === d.id);
  const descricaoTipo = descritor(d.tipo).rotulo;
  const abrir = real ? el("a", {href: urlFicha(d.tipo, d.ref_id)}, "abrir ficha")
    : manifestacao ? el("a", {href: urlFicha("work", d.work_id)}, "abrir ficha da obra") : "";
  const partes = [el("div", {class: "muted"}, el("span", {class: "dot " + d.tipo, style: d.tipo === "manifestation" ? `background:${descritor(d.tipo).cor}` : ""}), descricaoTipo), el("h3", {}, d.nome),
    d.data ? el("div", {class: "muted"}, d.data) : d.ano != null ? el("div", {class: "muted"}, rotuloAno(d.ano) + (d.fim != null ? " – " + rotuloAno(d.fim) : "")) : "",
    abrir ? el("div", {style: "margin:.4rem 0"}, abrir, " · ", el("a", {href: "#", onclick: e => { e.preventDefault(); S.foco = d.id; carregar(); }}, "focar aqui")) : ""];
  if (manifestacao) {
    partes.push(el("div", {class: "teoria"}, "Objeto concreto vinculado à obra intelectual: a edição/aparição tem seus próprios metadados, mas não é uma segunda ficha de obra."),
      d.tipo_aparicao ? el("div", {}, "Tipo: " + d.tipo_aparicao) : "",
      d.referencia ? el("div", {}, "Referência: " + d.referencia) : "",
      d.formato ? el("div", {}, "Arquivo: " + d.formato) : "",
      d.periodico_titulo ? el("div", {}, "Periódico: ", el("a", {href: urlFicha("periodical", d.periodical_id)}, d.periodico_titulo)) : "",
      d.obra_continente_titulo ? el("div", {}, "Volume / coletânea: ", el("a", {href: urlFicha("work", d.container_work_id)}, d.obra_continente_titulo)) : "");
  }
  if (real || manifestacao) {
    const notas = el("textarea", {rows: 4, style: "width:100%;box-sizing:border-box", placeholder: manifestacao ? "Notas desta manifestação…" : "Notas da ficha…"}); notas.value = d.notas || "";
    const status = el("span", {class: "muted"}); const endpoint = manifestacao ? `/api/edicoes/${d.ref_id}` : `/api/entidades/${d.tipo}/${d.ref_id}`;
    partes.push(el("details", {class: "editor-grafo"}, el("summary", {}, manifestacao ? "Anotar manifestação" : "Anotar ficha"), notas,
      el("button", {class: "mini", onclick: async () => { try { await api(endpoint, {method: "PATCH", body: {notas: notas.value}}); d.notas = notas.value; status.textContent = "salvo"; aviso("notas salvas"); } catch (e) { status.textContent = e.message; } }}, "salvar notas"), status));
  }
  partes.push(el("div", {class: "rel-fam"}, `${minhas.length} ligação(ões)`),
    el("ul", {class: "rel-lista"}, minhas.slice(0, 40).map(a => { const sai = a.origem === d.id, o = nomeRef(sai ? a.destino : a.origem);
      return el("li", {}, el("span", {class: "rot"}, a.derivada === "projecao" ? a.rotulo : (sai || a.simetrica ? a.rotulo : "← " + a.rotulo)), el("span", {class: "dot " + (o?.tipo || "")}), o ? o.nome : "?", a.ano ? el("span", {class: "meta"}, "· " + a.ano) : ""); })));
  painel(...partes);
}
function selecionarNoParaRelacao(d) {
  if (["tag", "lugar"].includes(d.tipo)) { aviso("platôs calculados não são fichas editáveis; selecione uma entidade real"); return; }
  if (!V.entidades[d.tipo]) { aviso("este objeto é estrutural e ainda não aceita relações genéricas; selecione uma ficha de autor, obra, periódico, evento ou mídia"); return; }
  const id = d.id;
  if (S.selecionados.includes(id)) { S.selecionados = S.selecionados.filter(x => x !== id); d3.selectAll(".no").filter(x => x.id === id).classed("selecionado", false); aviso("seleção removida"); return; }
  S.selecionados.push(id); d3.selectAll(".no").filter(x => x.id === id).classed("selecionado", true);
  if (S.selecionados.length === 1) { $("#info").style.display = "none"; aviso("origem selecionada; agora selecione destino(s)"); return; }
  if (S.edicaoConjunto) { aviso(`${S.selecionados.length} nós selecionados; escolha relacionar seleção`); return; }
  const [origem, destino] = S.selecionados.slice(-2).map(nomeRef);
  S.selecionados = []; d3.selectAll(".no").classed("selecionado", false);
  if (!origem || !destino) return;
  editorNovaRelacao(origem, destino);
}

function editorRelacaoEmConjunto() {
  const ns=S.selecionados.map(nomeRef).filter(Boolean);
  if(ns.length<2){aviso("Selecione a origem e pelo menos um destino.");return;}
  const origem=ns[0], destinos=ns.slice(1);
  const possiveis=Object.entries(V.relacoes).filter(([k,r])=>k!=="publicado_em" && destinos.every(d=>(r.origem.includes(origem.tipo)&&r.destino.includes(d.tipo)) || (!r.simetrica&&r.origem.includes(d.tipo)&&r.destino.includes(origem.tipo))));
  const sel=el("select",{style:"width:100%"},...possiveis.map(([k,r])=>el("option",{value:k},`${r.familia} · ${r.direta} → ${r.destino.join(", ")} · ${r.simetrica?"↔":"→"}`)));
  const estatuto=el("select",{style:"width:100%"},el("option",{value:"documentada"},"Documentada"),el("option",{value:"hipotese"},"Hipótese"));
  const fonte=el("input",{placeholder:"fonte / referência (opcional)",style:"width:100%"}), ano=el("input",{placeholder:"data (opcional)",style:"width:100%"}), notas=el("textarea",{placeholder:"nota comum",rows:2,style:"width:100%"}),status=el("div",{class:"muted"});
  const legenda=el("div",{class:"legenda-familias"},...possiveis.slice(0,8).map(([k,r])=>el("div",{class:"legenda-familia"},el("span",{class:"dot",style:`background:${corFamilia(r.familia)}`}),`${r.direta} ${r.simetrica?"↔":"→"}`)));
  painel(el("h3",{},"Relação em conjunto"),el("p",{},`${origem.nome} → ${destinos.length} destino(s)`),el("p",{class:"teoria"},"Prévia: uma aresta será criada para cada destino. Revise a direção, a legenda e o estatuto antes de gravar."),legenda,el("label",{},"Relação / direção",sel),el("label",{},"Estatuto",estatuto),el("label",{},"Fonte",fonte),el("label",{},"Data",ano),el("label",{},"Notas",notas),el("button",{class:"primario",onclick:async()=>{try{const tipo=sel.value;if(!tipo)throw new Error("Nenhuma relação é compatível com todos os destinos.");const relacoes=destinos.map(d=>{const r=V.relacoes[tipo];let o=origem,alvo=d;if(!(r.origem.includes(o.tipo)&&r.destino.includes(alvo.tipo))){o=d;alvo=origem;}return {origem_tipo:o.tipo,origem_id:o.ref_id,destino_tipo:alvo.tipo,destino_id:alvo.ref_id,tipo,ano:ano.value,fonte:fonte.value,notas:notas.value,estatuto:estatuto.value};});const resposta=await api("/api/relacoes/lote",{method:"POST",body:{relacoes}});const dup=resposta.relacoes.filter(x=>x.duplicado).length,ok=resposta.total-dup;S.selecionados=[];aviso(`${ok} relação(ões) criada(s); ${dup} duplicada(s). Lote transacional concluído.`);await carregar();controles();}catch(e){status.textContent=e.message;aviso(e.message);}}},"confirmar e gravar lote"),status);
}

function editorNovaRelacao(o, d) {
  // O pesquisador escolhe o tipo entre opções semanticamente válidas para os
  // nós selecionados. Quando só o sentido inverso se aplica, a interface o
  // declara e inverte a orientação gravada — a seta não deve contrariar o rótulo.
  const relacoes = [];
  const familia = chave => V.familias.find(f => f.chave === chave)?.titulo || chave;
  Object.entries(V.relacoes).forEach(([chave, r]) => {
    // Publicação em periódico é registrada como manifestação/fascículo, não
    // como aresta manual paralela.
    if (chave === "publicado_em") return;
    const direta = r.origem.includes(o.tipo) && r.destino.includes(d.tipo);
    const inversa = r.origem.includes(d.tipo) && r.destino.includes(o.tipo);
    if (direta) relacoes.push({value: chave + "|d", tipo: chave, invertida: false,
      label: `${familia(r.familia)} · ${r.direta} ${r.simetrica ? "↔" : "→"}`});
    if (!r.simetrica && inversa) relacoes.push({value: chave + "|i", tipo: chave, invertida: true,
      label: `${familia(r.familia)} · ← ${r.inversa} (sentido inverso)`});
  });
  const categoriaDe = r => ["cita","alude","epigrafe"].includes(r.tipo) ? "citacao" : r.tipo === "menciona" ? "mencao" : ["elogia","critica","comenta"].includes(r.tipo) ? "avaliacao" : r.tipo === "parte_de" || r.tipo === "versao_de" ? "estrutura" : "outras";
  const categorias = [{value:"citacao",label:"Citação / referência textual"},{value:"mencao",label:"Menção neutra"},{value:"avaliacao",label:"Comentário / avaliação"},{value:"estrutura",label:"Estrutura de obras"},{value:"outras",label:"Outras relações"}];
  const categoriasValidas = categorias.filter(c=>relacoes.some(r=>categoriaDe(r)===c.value));
  const categoria = el("select", {style:"width:100%"}, ...categoriasValidas.map(x=>el("option",{value:x.value},x.label)));
  const porValor = Object.fromEntries(relacoes.map(r => [r.value, r]));
  const tipo = el("select", {style:"width:100%"});
  const preencherTipos = () => { tipo.innerHTML=""; const xs=relacoes.filter(r=>categoriaDe(r)===categoria.value); xs.forEach(r=>tipo.append(el("option",{value:r.value},r.label))); if(!xs.length && categoriasValidas.length){categoria.value=categoriasValidas[0].value;relacoes.filter(r=>categoriaDe(r)===categoria.value).forEach(r=>tipo.append(el("option",{value:r.value},r.label)));} };
  categoria.addEventListener("change",preencherTipos); preencherTipos();
  const rotulo = el("input", {placeholder:"rótulo específico (obrigatório para ligação livre)", style:"width:100%"});
  const ano = el("input", {placeholder:"data/intervalo, se conhecido", style:"width:100%"});
  const fonte = el("input", {placeholder:"referência da fonte / páginas", style:"width:100%"});
  const notas = el("textarea", {rows:3, placeholder:"nota analítica: por que esta conexão é proposta?", style:"width:100%;box-sizing:border-box"});
  const estatuto = el("select", {style:"width:100%"}, el("option",{value:"documentada"},"Documentada — há suporte documental"), el("option",{value:"hipotese"},"Hipótese — ainda não confirmada"));
  const mediacaoTipo = el("select", {style:"width:100%"}, el("option",{value:""},"sem mediação explícita"), ...Object.entries(V.entidades).map(([k,v])=>el("option",{value:k},v.rotulo)));
  const mediacaoBusca = el("input", {placeholder:"ID da ficha mediadora (opcional)", style:"width:100%"});
  const status = el("div", {class:"muted"});
  const ajuda = el("p", {class:"teoria"}, "A direção importa. Uma crítica publicada sobre uma obra pode ligar o texto crítico à obra criticada através de uma manifestação e de um periódico; isso não prova amizade ou influência pessoal. Só aparecem tipos compatíveis com as entidades selecionadas.");
  const legendaRel = el("div", {class:"legenda-familias"},
    ...[{c:"#7b8794",t:"→ menção neutra"},{c:"#27865b",t:"→ elogio"},{c:"#c34d4d",t:"→ crítica"},{c:"#b8860b",t:"→ citação"}].map(x=>el("div",{class:"legenda-familia"},el("span",{class:"dot",style:`background:${x.c}`}),x.t)));
  const atualizarTipo = () => { const r = porValor[tipo.value]; rotulo.style.display = r?.tipo === "liga" ? "" : "none"; };
  tipo.addEventListener("change", atualizarTipo); atualizarTipo();
  painel(el("h3",{},"Nova relação de pesquisa"), el("p",{},el("b",{},o.nome)," → ",el("b",{},d.nome)), ajuda, legendaRel,
    el("label",{},"Modalidade",categoria), el("label",{},"Tipo específico / direção",tipo), el("label",{},"Rótulo",rotulo), el("label",{},"Data",ano),
    el("label",{},"Fonte / referência",fonte), el("label",{},"Mediação (opcional)",mediacaoTipo,mediacaoBusca),
    el("label",{},"Estatuto",estatuto), el("label",{},"Notas",notas),
    el("button",{class:"primario",onclick:async()=>{try{
      const rel = porValor[tipo.value];
      if (!rel) throw new Error("Não há tipo de relação válido para este par de entidades.");
      if (rel.tipo === "liga" && !rotulo.value.trim()) throw new Error("Informe o rótulo da ligação livre.");
      const origem = rel.invertida ? d : o, destino = rel.invertida ? o : d;
      const body={origem_tipo:origem.tipo,origem_id:origem.ref_id,destino_tipo:destino.tipo,destino_id:destino.ref_id,tipo:rel.tipo,rotulo:rotulo.value,ano:ano.value,fonte:fonte.value,notas:notas.value,estatuto:estatuto.value};
      if(mediacaoTipo.value){const raw=mediacaoBusca.value.trim(); if(!/^\d+$/.test(raw)) throw new Error("Informe o ID numérico da ficha mediadora."); body.via_tipo=mediacaoTipo.value;body.via_id=+raw;}
      const r=await api("/api/relacoes",{method:"POST",body});
      if(r.duplicado) aviso("essa relação já existe com os mesmos dados"); else aviso("relação registrada");
      S.modoEdicao=true; await carregar();
    }catch(e){status.textContent=e.message; aviso(e.message);}}},"registrar relação"),status);
}
async function criarFichaPeloGrafo() {
  const tipo=el("select",{style:"width:100%"},...Object.entries(V.entidades).map(([k,v])=>el("option",{value:k},v.rotulo)));
  const nome=el("input",{placeholder:"nome ou título",style:"width:100%"});
  const ano=el("input",{placeholder:"data/ano (opcional)",style:"width:100%"});
  const notas=el("textarea",{rows:3,placeholder:"notas iniciais",style:"width:100%;box-sizing:border-box"});
  const status=el("div",{class:"muted"});
  painel(el("h3",{},"Criar ficha a partir do grafo"),el("p",{class:"teoria"},"A ficha criada passa a integrar o cadastro canônico e pode ser ligada imediatamente a outras entidades."),
    el("label",{},"Tipo",tipo),el("label",{},"Nome/título",nome),el("label",{},"Data",ano),el("label",{},"Notas",notas),
    el("button",{class:"primario",onclick:async()=>{try{
      const t=tipo.value, campo=(t==="work"||t==="periodical")?"titulo":"nome"; S.projecao="nenhuma"; S.foco=null; S.tipos.add(t); const body={[campo]:nome.value.trim(),notas:notas.value};
      if(ano.value.trim()){if(t==="author") body.nascimento=ano.value; else if(t==="periodical") body.ano_inicio=ano.value; else body.ano=ano.value;}
      const r=await api(`/api/entidades/${t}`,{method:"POST",body}); aviso("ficha criada"); S.modoEdicao=true; await carregar(); const n=nomeRef(`${t}:${r.id}`); if(n) mostrarNo(n); else aviso("ficha criada; ajuste os filtros para visualizá-la");
    }catch(e){status.textContent=e.message; aviso(e.message);}}},"criar ficha"),status);
}

function mostrarAresta(a) {
  const o = nomeRef(a.origem.id || a.origem), d = nomeRef(a.destino.id || a.destino);
  const cab = [el("h3", {}, `${o?.nome} — ${d?.nome}`), el("div", {class: "muted"}, a.derivada === "projecao" ? "ligação mediada" : a.rotulo)];
  if (a.mediacoes) {
    const rot = {obra: "através de obra", periodical: "contexto de periódico", event: "participação em evento", issue: "mesmo fascículo", manifestacao: "papel na manifestação", direta: "relação direta", work: "através de obra"};
    const estatutos = {
      documentada: "Relação explicitamente registrada no fichário.",
      derivada_de_relacao_entre_obras: "Caminho derivado de uma relação documentada entre estas obras; não equivale a uma relação pessoal entre os autores.",
      derivada_de_participacoes_de_autoria: "Caminho reconstruído a partir de créditos de autoria da mesma obra.",
      "coocorrencia_documental; nao implica vinculo pessoal": "Coocorrência documental: os registros situam os agentes no mesmo fascículo ou evento; isso não prova contato pessoal.",
      "contexto_de_producao; nao implica vinculo pessoal": "Contexto de produção de uma manifestação; não implica vínculo pessoal.",
      "projecao_analitica": "Projeção calculada a partir de registros canônicos; não é uma relação independente cadastrada."
    };
    const linkEnt = ent => {
      if (!ent) return "";
      const id = String(ent.id ?? "").includes(":") ? String(ent.id).split(":")[1] : ent.id;
      const nome = ent.nome || `${ent.tipo} ${id}`;
      if (!["author", "work", "periodical", "event", "media"].includes(ent.tipo)) return el("span", {}, nome);
      return el("a", {href: urlFicha(ent.tipo, id)}, nome);
    };
    const cards = a.mediacoes.map(m => {
      const partes = [el("div", {}, el("b", {}, rot[m.como] || m.como), " · ", m.relacao)];
      if (m.estatuto) partes.push(el("div", {class: "teoria"}, estatutos[m.estatuto] || m.estatuto.replaceAll("_", " ")));
      if (m.origem_autor || m.destino_autor) {
        const ao = nomeRef(m.origem_autor), ad = nomeRef(m.destino_autor);
        partes.push(el("div", {class: "teoria"}, "Direção do caminho: ", ao?.nome || m.origem_autor, " → ", ad?.nome || m.destino_autor));
      }
      if (m.entidade?.origem && m.entidade?.destino) {
        partes.push(el("div", {class: "teoria"}, "Obras envolvidas: ", linkEnt(m.entidade.origem), " → ", linkEnt(m.entidade.destino)));
      } else if (m.entidade) {
        partes.push(el("div", {}, "Mediação: ", linkEnt(m.entidade)));
      }
      if (m.fonte) partes.push(el("div", {class: "teoria"}, "Fonte: " + m.fonte));
      if (m.ano) partes.push(el("div", {class: "teoria"}, "Data registrada: " + m.ano));
      if (m.manifestacao_a || m.manifestacao_b) partes.push(el("div", {class: "teoria"}, "Manifestações: ", String(m.manifestacao_a || ""), " ↔ ", String(m.manifestacao_b || "")));
      return el("div", {class: "med"}, ...partes);
    });
    painel(...cab, el("p", {class: "teoria"}, "Esta projeção resume caminhos reconstruídos do fichário. Relações documentadas, vínculos estruturais e coocorrências são distinguidos; uma mediação editorial não equivale, por si só, a amizade, influência ou contato pessoal."), cards);
  } else {
    const itens = [...cab, a.via ? el("div", {}, "através de: ", el("a", {href: urlFicha(a.via.tipo, a.via.id.split(":")[1])}, a.via.nome)) : "",
      a.ano ? el("div", {}, "quando: " + a.ano) : "", a.fonte ? el("div", {}, "fonte: " + a.fonte) : "", a.nota ? el("div", {}, a.nota) : "",
      a.estatuto ? el("p", {class: "teoria"}, a.estatuto === "estrutural" ? "Vínculo estrutural reconstruído a partir dos registros canônicos." : a.estatuto === "derivada" ? "Ligação calculada a partir dos dados; não está gravada como fato independente." : a.estatuto === "hipotese" ? "Hipótese de pesquisa; não deve ser lida como fato confirmado." : "Relação documentada no fichário.") : ""];
    if (/^(r\d+|wa:\d+|ma:\d+)$/.test(a.id || "") && (!a.derivada || String(a.id).startsWith("wa:") || String(a.id).startsWith("ma:"))) {
      const ano = el("input", {placeholder: "ano / data desconhecida", value: a.ano || "", style: "width:100%"});
      const fonte = el("input", {placeholder: "fonte / página", value: a.fonte || "", style: "width:100%"});
      const nota = el("textarea", {rows: 3, placeholder: "nota de pesquisa", style: "width:100%;box-sizing:border-box"}); nota.value = a.nota || "";
      const estatuto = el("select", {style:"width:100%"}, el("option", {value:"documentada"}, "documentada — sustentada por fonte"), el("option", {value:"hipotese"}, "hipótese — formulação em investigação")); estatuto.value = a.estatuto === "hipotese" ? "hipotese" : "documentada";
      const status = el("span", {class: "muted"});
      const participacaoManifestacao = String(a.id).startsWith("ma:");
      itens.push(el("details", {class: "editor-grafo"}, el("summary", {}, "Editar ocorrência e evidência"),
        participacaoManifestacao ? el("p", {class: "teoria"}, "Este papel pertence à manifestação indicada; a data é consultada na ficha documental.") : ano,
        fonte, nota,
        String(a.id).startsWith("r") ? el("label", {class:"teoria"}, "Estatuto epistemológico", estatuto) : el("p", {class:"teoria"}, "Este vínculo é um papel canônico no Fichário. Para não criar uma hipótese paralela nem simular uma alteração que não seria persistida, o estatuto não pode ser alterado neste formulário."),
        el("button", {class: "mini", onclick: async () => { try {
          const rid = /^(wa:|ma:)/.test(String(a.id)) ? a.id : String(a.id).replace(/^r/, "");
          await api(`/api/relacoes/${rid}`, {method: "PATCH", body: {...(participacaoManifestacao ? {} : {ano: ano.value}), fonte: fonte.value, notas: nota.value, ...(String(a.id).startsWith("r") ? {estatuto: estatuto.value} : {})}});
          a.ano = participacaoManifestacao ? a.ano : ano.value; a.fonte = fonte.value; a.nota = nota.value; if(String(a.id).startsWith("r")) a.estatuto = estatuto.value; status.textContent = "salvo"; aviso("relação atualizada");
        } catch (e) { status.textContent = e.message; } }}, "salvar alterações"), status));
    }
    if (/^(r\d+|wa:\d+|ma:\d+)$/.test(String(a.id || ""))) {
      itens.push(editorEstrutural(a, o, d));
      itens.push(editorEvidenciaRelacao(a, o, d));
    }
    painel(...itens);
    if (/^(r\d+|wa:\d+|ma:\d+)$/.test(String(a.id || ""))) carregarEvidenciasRelacao(a);
  }
}


let _catalogoRelacional = null;
async function catalogoRelacional() {
  if (_catalogoRelacional) return _catalogoRelacional;
  const tipos = Object.keys(V.entidades);
  const registros = await Promise.all(tipos.map(async tipo => (await api(`/api/entidades/${tipo}?todos=1`)).map(x => ({...x, tipo}))));
  const manifestacoes = (await api('/api/manifestacoes?todos=1')).map(x => ({
    id: x.id, tipo: 'manifestation', nome: [x.obra, x.tipo_aparicao, x.periodico, x.ano_edicao, x.referencia].filter(Boolean).join(' · '),
    sub: `manifestação ${x.id}`, work_id: x.work_id
  }));
  const byType = Object.fromEntries(tipos.map((t,i) => [t, registros[i].sort((a,b)=>a.nome.localeCompare(b.nome,'pt-BR'))]));
  byType.manifestation = manifestacoes;
  _catalogoRelacional = {byType, all: [...registros.flat(), ...manifestacoes]};
  return _catalogoRelacional;
}
function idTipado(x) { if (!x) return ''; const raw=String(x.ref_id ?? x.id ?? ''); return raw.includes(':') ? raw : `${x.tipo}:${raw}`; }
function opcoesDeRelacao(ot, dt, current) {
  const opts = [];
  Object.entries(V.relacoes).forEach(([k,r]) => {
    // O vínculo publicação–periódico é uma manifestação, não uma aresta genérica.
    if (k === 'publicado_em') return;
    const papelCanonico = ['autor_de','traduziu','organizou','ilustrou','prefaciou','entrevistou','entrevistado_em'].includes(k);
    // Não criar cópia genérica de crédito pessoa–obra; a edição do crédito tem painel próprio.
    if (papelCanonico && ot === 'author' && dt === 'work') return;
    const direta = r.origem.includes(ot) && r.destino.includes(dt);
    const inversa = !r.simetrica && r.origem.includes(dt) && r.destino.includes(ot);
    if (direta) opts.push({value:`${k}|d`, tipo:k, invertida:false, label:`${V.familias.find(f=>f.chave===r.familia)?.titulo||r.familia} · ${r.direta}`});
    if (inversa) opts.push({value:`${k}|i`, tipo:k, invertida:true, label:`${V.familias.find(f=>f.chave===r.familia)?.titulo||r.familia} · ${r.inversa} (sentido inverso)`});
  });
  if (!opts.some(x=>x.value===current)) opts.unshift({value:'liga|d',tipo:'liga',invertida:false,label:'Ligação livre · rótulo específico'});
  return opts;
}
function selectTipado(itens, valor, placeholder='selecione') {
  const sel=el('select',{style:'width:100%'});
  sel.append(el('option',{value:''},placeholder));
  itens.forEach(x=>sel.append(el('option',{value:`${x.tipo}:${x.id}`},`${x.nome}${x.sub?` · ${x.sub}`:''}`)));
  sel.value=valor||''; return sel;
}
function editorEstrutural(a, o, d) {
  const rid=String(a.id);
  const detalhes=el('details',{class:'editor-grafo'});
  detalhes.append(el('summary',{},'Editar estrutura da relação'));
  detalhes.append(el('p',{class:'teoria'},'Altere participantes, tipo, direção ou mediação. Se a afirmação mudar, as evidências vinculadas serão marcadas para revisão antes de serem consideradas válidas para a nova formulação.'));
  const corpo=el('div',{}); detalhes.append(corpo); let carregando=false;
  detalhes.addEventListener('toggle', async()=>{
    if(!detalhes.open||carregando)return; carregando=true;
    const status=el('div',{class:'muted'}); corpo.append(status);
    try {
      const cat=await catalogoRelacional(); corpo.innerHTML='';
      const salvar=async(url,body)=>{try{const r=await api(url,{method:'PATCH',body});let msg=r.revisao_evidencias?'salvo; evidências marcadas para revisão':'alterações estruturais salvas';if(r.conflito_campo_legado)msg+='; texto legado conflitante foi preservado — revise a ficha da manifestação';status.textContent=msg;aviso(msg);_catalogoRelacional=null;await carregar();}catch(e){status.textContent=e.message;aviso(e.message);}};
      if(rid.startsWith('wa:')) {
        const authors=cat.byType.author||[], works=cat.byType.work||[];
        const autor=selectTipado(authors,o?.tipo==='author'?`${o.tipo}:${o.ref_id}`:'');
        const obra=selectTipado(works,d?.tipo==='work'?`${d.tipo}:${d.ref_id}`:'');
        const roles=[['autor_principal','autor(a) principal'],['coautor','coautor(a)'],['tradutor','tradutor(a)'],['organizador','organizador(a)'],['ilustrador','ilustrador(a)'],['prefaciador','prefaciador(a)'],['entrevistador','entrevistador(a)'],['entrevistado','entrevistado(a)']];
        const papel=el('select',{style:'width:100%'},...roles.map(([v,t])=>el('option',{value:v},t)));papel.value=a.papel||'coautor';
        corpo.append(el('label',{},'Agente',autor),el('label',{},'Obra',obra),el('label',{},'Papel canônico',papel),
          el('div',{class:'teoria'},'A participação continuará no registro canônico obra–agente; não será criada uma relação paralela.'),
          el('button',{class:'mini',onclick:()=>{if(!autor.value||!obra.value) {status.textContent='Selecione agente e obra.';return;} const [_,aid]=autor.value.split(':');const [__,wid]=obra.value.split(':');salvar(`/api/relacoes/${rid}`,{author_id:+aid,work_id:+wid,papel:papel.value});}},'salvar estrutura'));
      } else if(rid.startsWith('ma:')) {
        const authors=cat.byType.author||[], manifests=cat.byType.manifestation||[];
        const autor=selectTipado(authors,o?.tipo==='author'?`${o.tipo}:${o.ref_id}`:'');
        const manifestacao=selectTipado(manifests,d?.tipo==='manifestation'?`${d.tipo}:${d.ref_id}`:'');
        const roles=[['tradutor','tradutor(a)'],['organizador','organizador(a)'],['ilustrador','ilustrador(a)'],['prefaciador','prefaciador(a)'],['entrevistador','entrevistador(a)'],['entrevistado','entrevistado(a)']];
        const papel=el('select',{style:'width:100%'},...roles.map(([v,t])=>el('option',{value:v},t)));papel.value=a.papel||'tradutor';
        corpo.append(el('label',{},'Agente',autor),el('label',{},'Manifestação concreta',manifestacao),el('label',{},'Papel nesta manifestação',papel),
          el('div',{class:'teoria'},'Este crédito pertence a uma edição/manuscrito específico, não automaticamente à obra em todas as suas manifestações.'),
          el('button',{class:'mini',onclick:()=>{if(!autor.value||!manifestacao.value){status.textContent='Selecione agente e manifestação.';return;} const [_,aid]=autor.value.split(':');const [__,mid]=manifestacao.value.split(':');salvar(`/api/relacoes/${rid}`,{author_id:+aid,manifestation_id:+mid,papel:papel.value});}},'salvar estrutura'));
      } else {
        const all=cat.all.filter(x=>x.tipo!=='manifestation');
        const src=selectTipado(all,idTipado(o)), dst=selectTipado(all,idTipado(d));
        const via=selectTipado(all,idTipado(a.via),'sem mediação explícita');
        const tipo=el('select',{style:'width:100%'}); const rotulo=el('input',{value:a.tipo==='liga'?(a.rotulo||''):'',placeholder:'rótulo específico (obrigatório para ligação livre)',style:'width:100%'});
        function atualizarTipos(preferido) {
          const [ot]=String(src.value).split(':');const [dt]=String(dst.value).split(':');
          const opts=opcoesDeRelacao(ot,dt,preferido||`${a.tipo}|d`);tipo.innerHTML='';opts.forEach(x=>tipo.append(el('option',{value:x.value},x.label)));
          tipo.value=opts.some(x=>x.value===preferido)?preferido:opts[0]?.value||'';
          rotulo.style.display=tipo.value.startsWith('liga|')?'':'none';
        }
        const atualTipo=`${a.tipo}|d`;
        atualizarTipos(atualTipo);src.addEventListener('change',()=>atualizarTipos());dst.addEventListener('change',()=>atualizarTipos());tipo.addEventListener('change',()=>{rotulo.style.display=tipo.value.startsWith('liga|')?'':'none';});
        const resumo=el('div',{class:'teoria'},'O catálogo inclui as fichas existentes, mesmo que estejam fora dos filtros visuais atuais. A direção da seta segue o predicado selecionado.');
        corpo.append(el('label',{},'Origem',src),el('label',{},'Destino',dst),el('label',{},'Tipo e direção',tipo),el('label',{},'Rótulo',rotulo),el('label',{},'Mediação (opcional)',via),resumo,
          el('button',{class:'mini',onclick:()=>{
            if(!src.value||!dst.value||!tipo.value){status.textContent='Selecione origem, destino e tipo.';return;}
            const [sk,si]=src.value.split(':');const [dk,di]=dst.value.split(':');const [tk,sense]=tipo.value.split('|');
            if(tk==='liga'&&!rotulo.value.trim()){status.textContent='A ligação livre exige um rótulo.';return;}
            const inverted=sense==='i';const body={origem_tipo:inverted?dk:sk,origem_id:+(inverted?di:si),destino_tipo:inverted?sk:dk,destino_id:+(inverted?si:di),tipo:tk,rotulo:rotulo.value};
            if(via.value){const [vt,vi]=via.value.split(':');body.via_tipo=vt;body.via_id=+vi;}else{body.via_tipo=null;body.via_id=null;}
            salvar(`/api/relacoes/${rid.replace(/^r/, '')}`,body);
          }},'salvar estrutura'));
      }
    } catch(e) {corpo.append(el('p',{class:'erro'},'Não foi possível carregar o catálogo de edição: '+e.message));}
  });
  return detalhes;
}

function editorEvidenciaRelacao(a, o, d) {
  const titulo=el("input",{placeholder:"título/descrição da fonte",style:"width:100%"});
  const url=el("input",{placeholder:"URL/identificador persistente (opcional)",style:"width:100%"});
  const autor=el("input",{placeholder:"autor/editor da fonte (opcional)",style:"width:100%"});
  const afirmacao=el("input",{placeholder:"afirmação exata que esta fonte sustenta",style:"width:100%"});
  const trecho=el("textarea",{rows:3,placeholder:"trecho transcrito ou resumo fiel",style:"width:100%;box-sizing:border-box"});
  const localizador=el("input",{placeholder:"página, coluna, número, URL-fragmento",style:"width:100%"});
  const status=el("div",{class:"muted"});
  const id=`evidencias-rel-${String(a.id).replace(/[^a-z0-9]/gi,"")}`;
  const alvoTipo=String(a.id).startsWith("wa:")?"work_agent":String(a.id).startsWith("ma:")?"manifestation_agent":"relation";
  return el("details",{class:"editor-grafo"},el("summary",{},"Vincular evidência a esta relação"),
    el("p",{class:"teoria"},"A evidência fica vinculada à afirmação relacional específica, não apenas à ficha de uma das entidades."),
    el("label",{},"Fonte",titulo),el("label",{},"URL",url),el("label",{},"Autor",autor),
    el("label",{},"Afirmação sustentada",afirmacao),el("label",{},"Trecho / resumo",trecho),el("label",{},"Localizador",localizador),
    el("button",{class:"mini",onclick:async()=>{try{
      if(!titulo.value.trim()||!afirmacao.value.trim()) throw new Error("Informe a fonte e a afirmação sustentada.");
      const f=await api("/api/fontes",{method:"POST",body:{titulo:titulo.value,url:url.value,autor:autor.value}});
      await api("/api/evidencias",{method:"POST",body:{source_id:f.id,entidade_tipo:o?.tipo||d?.tipo,entidade_id:o?.ref_id??d?.ref_id,afirmacao:afirmacao.value,alvo_tipo:alvoTipo,alvo_id:String(a.id).replace(/^(r|wa:|ma:)/,""),trecho:trecho.value,localizador:localizador.value}});
      status.textContent="evidência vinculada à relação"; aviso("evidência registrada"); carregarEvidenciasRelacao(a);
    }catch(e){status.textContent=e.message;aviso(e.message);}}},"registrar evidência"),status,
    el("div",{id,class:"teoria"},"Carregando evidências…"));
}
async function carregarEvidenciasRelacao(a){
  const alvo=String(a.id).replace(/^(r|wa:|ma:)/,""); const alvoTipo=String(a.id).startsWith("wa:")?"work_agent":String(a.id).startsWith("ma:")?"manifestation_agent":"relation"; const id=`evidencias-rel-${String(a.id).replace(/[^a-z0-9]/gi,"")}`;
  try{const xs=await api(`/api/evidencias?alvo_tipo=${alvoTipo}&alvo_id=${encodeURIComponent(alvo)}`); const box=$("#"+id); if(!box)return; box.innerHTML="";
    box.append(el("b",{},`Evidências vinculadas: ${xs.length}`));
    xs.forEach(x=>{
      const estado=x.estado||"vigente"; const card=el("div",{class:"med"+(estado==="revisao_necessaria"?" evidencia-revisao":"")},
        el("b",{},x.afirmacao),el("div",{},x.fonte_titulo||"fonte não identificada"),
        el("div",{class:estado==="revisao_necessaria"?"erro":"teoria"},estado==="revisao_necessaria"?"REVISÃO NECESSÁRIA — "+(x.motivo_revisao||"a formulação relacional mudou"):estado==="nao_sustenta"?"Esta evidência foi marcada como não sustentando a afirmação atual.":"Evidência vigente"),
        x.localizador?el("div",{},x.localizador):"",x.trecho?el("blockquote",{},x.trecho):"",
        x.fonte_url&&/^https?:\/\//i.test(x.fonte_url)?el("a",{href:x.fonte_url,target:"_blank",rel:"noopener"},"abrir fonte"):"");
      if(estado==="revisao_necessaria") card.append(el("button",{class:"mini",onclick:async()=>{try{await api(`/api/evidencias/${x.id}`,{method:"PATCH",body:{estado:"vigente"}});aviso("evidência revista e confirmada");carregarEvidenciasRelacao(a);}catch(e){aviso(e.message);}}},"confirmar pertinência"),el("button",{class:"mini",onclick:async()=>{try{await api(`/api/evidencias/${x.id}`,{method:"PATCH",body:{estado:"nao_sustenta"}});aviso("evidência marcada como insuficiente");carregarEvidenciasRelacao(a);}catch(e){aviso(e.message);}}},"não sustenta a afirmação"));
      box.append(card);
    });
    if(!xs.length) box.append(el("div",{},"Ainda não há evidência vinculada a esta relação."));
  }catch(e){const box=$("#"+id);if(box)box.textContent="Não foi possível carregar as evidências: "+e.message;}
}
