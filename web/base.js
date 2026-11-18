/* Base compartilhada: helpers, navegação, perfil ativo, busca de entidades e painel de relações. */
const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const H = {"Content-Type": "application/json"};

function el(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === false || v == null) continue;
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else if (k === "value") n.value = v;
    else if (k === "checked" || k === "disabled" || k === "selected") n[k] = !!v;
    else n.setAttribute(k, v);
  }
  kids.flat(9).forEach(f => { if (f != null && f !== false) n.append(f.nodeType ? f : document.createTextNode(f)); });
  return n;
}
function aviso(m) {
  let s = $("#status"); if (!s) { s = el("div", {id: "status"}); document.body.append(s); }
  s.textContent = m; s.classList.add("on"); clearTimeout(s._t); s._t = setTimeout(() => s.classList.remove("on"), 1800);
}
const md2html = t => (window.marked && window.DOMPurify) ? DOMPurify.sanitize(marked.parse(t || "")) : esc(t || "").replace(/\n/g, "<br>");

/* ---- perfil ativo: um recorte de pesquisa, ou "Geral" (0). Vai em TODA chamada /api.
   Regra de abertura: o app NÃO abre no Geral. Sem escolha registrada, entra no primeiro
   perfil existente ("Perfil I"); o Geral fica disponível apenas como visualização do todo. */
const Perfil = {
  get id() { return +localStorage.getItem("litdex.perfil") || 0; },
  get escolhido() { return localStorage.getItem("litdex.perfil") !== null; },
  set(id) { localStorage.setItem("litdex.perfil", String(id || 0)); },
};
const _fetch = window.fetch.bind(window);
window.fetch = (u, o = {}) => {
  if (typeof u === "string" && u.startsWith("/api") && Perfil.id) o = {...o, headers: {...(o.headers || {}), "X-Perfil": String(Perfil.id)}};
  return _fetch(u, o);
};
async function api(path, {method = "GET", body, form} = {}) {
  const o = {method};
  if (form) o.body = form; else if (body !== undefined) { o.headers = H; o.body = JSON.stringify(body); }
  const r = await fetch(path, o); let j = null;
  try { j = await r.json(); } catch (e) {}
  if (!r.ok) throw new Error((j && (typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail))) || ("erro " + r.status));
  return j;
}
const urlFicha = (t, id) => `/ui/fichas?t=${t}&id=${id}`;
const urlArquivo = c => "/arq/" + String(c || "").split("/").map(encodeURIComponent).join("/");
const rotuloAno = n => n == null ? "" : (n < 0 ? `${-n} a.C.` : String(n));

let _vocab = null;
async function vocab() { return _vocab || (_vocab = await api("/api/vocab")); }

/* ---- navegação */
const PAGINAS = [["/ui/fichas", "fichário"], ["/ui/biblioteca", "biblioteca"], ["/ui/grafo", "rizoma"],
                 ["/ui/timeline", "linha do tempo"], ["/ui/mapa", "mapa"], ["/ui/perfis", "perfis"]];
async function montarNav(ativa) {
  const nav = $("#nav") || document.body.prepend(el("header", {id: "nav"})) || $("#nav");
  nav.innerHTML = ""; nav.append(el("a", {href: "/ui/", class: "marca", "aria-label": "LitDex — início", title: "Ir para Início"}, "LitDex"));
  PAGINAS.forEach(([h, t]) => nav.append(el("a", {href: h, class: h === ativa ? "on" : ""}, t)));
  let perfis = [];
  try { perfis = await api("/api/perfis"); } catch (e) {}
  // Abertura fora do Geral: sem escolha registrada, o app entra no primeiro perfil ("Perfil I").
  if (!Perfil.escolhido) {
    const anterior = +localStorage.getItem("litdex.perfil.anterior") || 0;
    const alvo = perfis.find(p => p.id === anterior) || perfis[0];
    Perfil.set(alvo ? alvo.id : 0);
  } else if (Perfil.id && !perfis.some(p => p.id === Perfil.id)) {
    // O perfil ativo deixou de existir (apagado): volta ao primeiro perfil, não ao Geral.
    Perfil.set(perfis[0] ? perfis[0].id : 0);
  }
  const sel = el("select", {title: "Perfil: um recorte de pesquisa sobre o mesmo acervo"});
  sel.append(new Option("Geral (visualização do todo)", 0));
  perfis.forEach(p => sel.append(new Option(`${p.nome} (${p.n})`, p.id)));
  sel.value = Perfil.id;
  sel.onchange = () => { localStorage.setItem("litdex.perfil.anterior", String(Perfil.id)); Perfil.set(+sel.value); location.reload(); };
  nav.append(el("span", {class: "fim"}, "perfil ", sel, el("a", {href: "/ui/diagnostico"}, "diagnóstico")));
  document.body.classList.toggle("com-perfil", !!Perfil.id);
}

/* ---- busca de entidades (autocomplete) */
function buscaEntidade(input, {tipos = [], onPick, criar = true, excluir = null} = {}) {
  const wrap = el("span", {class: "ac"}); input.replaceWith(wrap); wrap.append(input);
  let lista = null, itens = [], pos = -1, t;
  const fechar = () => { lista?.remove(); lista = null; itens = []; pos = -1; };
  async function escolher(it) { fechar(); input.value = ""; await onPick(it); }
  function desenhar() {
    lista?.remove(); lista = el("div", {class: "ac-lista"});
    itens.forEach((it, i) => lista.append(el("div", {class: i === pos ? "sel" : "", onmousedown: e => { e.preventDefault(); escolher(it); }},
      el("span", {class: "dot " + (it.criar ? it.tipo : it.tipo)}), it.criar ? `➕ criar «${it.nome}» (${_vocab?.entidades[it.tipo].rotulo.toLowerCase() || it.tipo})` : it.nome,
      it.sub ? el("small", {}, it.sub) : "", it.campo ? el("small", {class: "muted", style: "display:block"}, `${it.campo}: ${it.trecho || ""}`) : "")));
    wrap.append(lista);
  }
  input.addEventListener("input", () => { clearTimeout(t); t = setTimeout(async () => {
    const q = input.value.trim(); if (q.length < 2) return fechar();
    await vocab();
    let r = await api(`/api/busca?q=${encodeURIComponent(q)}&tipos=${tipos.join(",")}`);
    if (excluir) r = r.filter(x => !(x.tipo === excluir.tipo && x.id === excluir.id));
    itens = r.slice(0, 8);
    if (criar) tipos.forEach(tp => itens.push({criar: true, tipo: tp, nome: q}));
    pos = -1; desenhar(); }, 200); });
  input.addEventListener("keydown", e => {
    if (!lista) return;
    if (e.key === "ArrowDown") { pos = Math.min(pos + 1, itens.length - 1); desenhar(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { pos = Math.max(pos - 1, 0); desenhar(); e.preventDefault(); }
    else if (e.key === "Enter" && itens.length) { escolher(itens[Math.max(pos, 0)]); e.preventDefault(); }
    else if (e.key === "Escape") fechar();
  });
  input.addEventListener("blur", () => setTimeout(fechar, 150));
  return wrap;
}
async function resolverEntidade(it) {
  if (!it.criar) return it;
  const campo = it.tipo === "work" || it.tipo === "periodical" ? "titulo" : "nome";
  const r = await api(`/api/entidades/${it.tipo}`, {method: "POST", body: {[campo]: it.nome}});
  return {tipo: it.tipo, id: r.id, nome: it.nome};
}

/* ---- painel de relações: o mesmo em todas as fichas.
   Cada relação é tipada, pode dizer ATRAVÉS DE QUÊ se deu (obra, revista, evento, carta), quando e em que fonte. */
async function painelRelacoes(tipo, id, onChange = () => {}) {
  const V = await vocab(); const raiz = el("div", {class: "rel-painel"});
  const fam = Object.fromEntries(V.familias.map(f => [f.chave, f]));
  async function carregar() {
    const rels = await api(`/api/entidades/${tipo}/${id}/relacoes`);
    raiz.innerHTML = "";
    if (!rels.length) raiz.append(el("p", {class: "muted", style: "font-style:italic;margin:0"}, "sem relações registradas"));
    V.familias.forEach(f => {
      const doGrupo = rels.filter(r => r.familia === f.chave); if (!doGrupo.length) return;
      raiz.append(el("div", {class: "rel-fam"}, el("span", {class: "dot", style: `background:${f.cor}`}), f.titulo));
      const ul = el("ul", {class: "rel-lista"});
      doGrupo.forEach(r => {
        const ano = el("input", {placeholder: "ano / data desconhecida", value: r.ano || "", style: "width:8rem"});
        const fonte = el("input", {placeholder: "fonte / página", value: r.fonte || "", style: "min-width:12rem"});
        const nota = el("textarea", {placeholder: "nota sobre esta ocorrência", rows: 2, style: "width:100%;box-sizing:border-box"}); nota.value = r.nota || "";
        const estado = el("span", {class: "muted"});
        const editar = el("details", {style: "flex-basis:100%;margin:.35rem 0"}, el("summary", {}, "editar evidência / ocorrência"),
          el("div", {class: "linha", style: "margin:.35rem 0"}, ano, fonte), nota,
          el("div", {class: "linha"}, el("button", {class: "mini", onclick: async () => { try { await api(`/api/relacoes/${r.id}`, {method: "PATCH", body: {ano: ano.value, fonte: fonte.value, notas: nota.value}}); estado.textContent = "salvo"; await carregar(); onChange(); } catch (e) { estado.textContent = e.message; } }}, "salvar alterações"), estado));
        ul.append(el("li", {},
          el("span", {class: "rot"}, r.rotulo), el("span", {class: "dot " + r.outro.tipo}),
          el("a", {href: urlFicha(r.outro.tipo, r.outro.id)}, r.outro.nome),
          r.estatuto === "hipotese" ? el("span", {class: "chip falta", title: "conjectura, ainda não confirmada"}, "hipótese") : "",
          r.via ? el("span", {class: "meta"}, ["· através de ", el("a", {href: urlFicha(r.via.tipo, r.via.id)}, r.via.nome)]) : "",
          r.ano ? el("span", {class: "meta"}, "· " + r.ano) : "", r.nota ? el("span", {class: "meta"}, "· " + r.nota) : "",
          r.fonte ? el("span", {class: "meta"}, "· fonte: " + r.fonte) : "", editar,
          el("button", {class: "x", title: "remover esta relação do acervo", onclick: async () => {
            if (!confirm("Esta relação pertence ao acervo geral e desaparecerá também dos perfis que a exibem. Remover?")) return;
            await api(`/api/relacoes/${r.id}`, {method: "DELETE"}); await carregar(); onChange(); }}, "×")));
      });
      raiz.append(ul);
    });
    raiz.append(formulario());
  }
  function formulario() {
    const sel = el("select", {style: "max-width:100%"}); const opcoes = {};
    V.familias.forEach(f => {
      const g = el("optgroup", {label: f.titulo}); let n = 0;
      Object.entries(V.relacoes).filter(([k, r]) => r.familia === f.chave && k !== "publicado_em").forEach(([k, r]) => {
        if (r.origem.includes(tipo)) { opcoes[k + "|d"] = {k, sentido: "d", alvo: r.destino, r}; g.append(new Option(r.direta, k + "|d")); n++; }
        if (!r.simetrica && r.destino.includes(tipo)) { opcoes[k + "|i"] = {k, sentido: "i", alvo: r.origem, r}; g.append(new Option(r.inversa, k + "|i")); n++; }
        else if (r.simetrica && !r.origem.includes(tipo) && r.destino.includes(tipo)) { opcoes[k + "|d"] = {k, sentido: "d", alvo: r.origem, r}; g.append(new Option(r.direta, k + "|d")); n++; }
      });
      if (n) sel.append(g);
    });
    const alvoIn = el("input", {placeholder: "ficha de destino…"}); let alvo = null; let acWrap;
    const rotulo = el("input", {placeholder: "rótulo (qual é a ligação?)", style: "display:none"});
    const viaIn = el("input", {placeholder: "através de… (obra, revista, evento, carta)"}); let via = null;
    const ano = el("input", {placeholder: "quando? (ex.: 1923)", style: "width:9rem"});
    const fonte = el("input", {placeholder: "fonte / página"}); const nota = el("input", {placeholder: "nota", style: "min-width:14rem"});
    const estatuto = el("select", {title: "Uma hipótese aparece marcada e não é promovida sozinha"},
      new Option("documentada", "documentada"), new Option("hipótese", "hipotese"));
    const teoria = el("div", {class: "teoria"}); const estado = el("span", {class: "muted"});
    const rotuloSel = () => { const o = opcoes[sel.value]; if (!o) return;
      rotulo.style.display = o.k === "liga" ? "" : "none"; teoria.textContent = o.r.desc || fam[o.r.familia].desc;
      alvo = null; alvoIn.value = ""; estado.textContent = ""; montarAc(); };
    function montarAc() {
      const o = opcoes[sel.value]; if (!o) return;
      const novo = el("input", {placeholder: "ficha de destino…"}); acWrap?.replaceWith(novo); acWrap = novo;
      acWrap = buscaEntidade(novo, {tipos: o.alvo, excluir: {tipo, id}, onPick: async it => {
        alvo = await resolverEntidade(it); estado.textContent = "→ " + alvo.nome; }});
    }
    sel.onchange = rotuloSel; acWrap = alvoIn;
    const viaWrap = el("span"); viaWrap.append(viaIn);
    const rodape = el("div", {class: "linha"}, ano, fonte, nota, estatuto);
    const botao = el("button", {onclick: async () => {
      const o = opcoes[sel.value]; if (!alvo) return aviso("escolha a ficha de destino");
      const [ot, oi, dt, di] = o.sentido === "d" ? [tipo, id, alvo.tipo, alvo.id] : [alvo.tipo, alvo.id, tipo, id];
      try {
        const r = await api("/api/relacoes", {method: "POST", body: {origem_tipo: ot, origem_id: oi, destino_tipo: dt, destino_id: di, tipo: o.k,
          rotulo: rotulo.value, via_tipo: via?.tipo, via_id: via?.id, ano: ano.value, fonte: fonte.value, notas: nota.value,
          estatuto: estatuto.value}});
        aviso(r.duplicado ? "já existia" : "relação criada"); await carregar(); onChange();
      } catch (e) { aviso(e.message); }
    }}, "ligar");
    const f = el("div", {class: "rel-form"},
      el("div", {class: "linha"}, el("strong", {}, "esta ficha"), sel, acWrap, rotulo, estado),
      teoria,
      el("div", {class: "linha"}, viaWrap, el("span", {class: "muted", id: "via-estado"})),
      rodape, el("div", {class: "linha"}, botao));
    setTimeout(() => { rotuloSel();
      buscaEntidade(viaIn, {tipos: ["work", "periodical", "event"], criar: false, onPick: it => { via = it; $("#via-estado", f).textContent = "através de: " + it.nome; }}); }, 0);
    return f;
  }
  await carregar(); return raiz;
}

/* ---- anel de completude: quanto da ficha está preenchido */
function anel(pct, tam = 44, espessura = 5) {
  const r = (tam - espessura) / 2, circ = 2 * Math.PI * r, NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg"); svg.setAttribute("width", tam); svg.setAttribute("height", tam);
  const mk = (cls, off) => { const c = document.createElementNS(NS, "circle"); c.setAttribute("class", cls); c.setAttribute("cx", tam / 2); c.setAttribute("cy", tam / 2); c.setAttribute("r", r);
    c.setAttribute("fill", "none"); c.setAttribute("stroke-width", espessura); c.setAttribute("stroke-dasharray", circ); c.setAttribute("stroke-dashoffset", off); return c; };
  const arco = mk("arco", circ); svg.append(mk("trilho", 0), arco);
  requestAnimationFrame(() => requestAnimationFrame(() => arco.setAttribute("stroke-dashoffset", circ * (1 - pct / 100))));
  return el("span", {class: "anel" + (pct >= 90 ? " cheio" : ""), title: pct + "% de cobertura dos campos descritivos centrais", style: `width:${tam}px;height:${tam}px`}, svg, el("b", {style: tam < 40 ? "font-size:.6rem" : ""}, pct + (tam >= 40 ? "%" : "")));
}

/* ---- escolha de lugar: catálogo embutido (países, estados, cidades) + internet (opcional) */
function buscaLugar(input, {onPick, onLivre} = {}) {
  const wrap = el("span", {class: "ac"}); input.replaceWith(wrap); wrap.append(input);
  let lista = null, itens = [], pos = -1, t;
  const fechar = () => { lista?.remove(); lista = null; itens = []; pos = -1; };
  const rotuloTipo = {pais: "país", estado: "estado", cidade: "cidade", historico: "histórico", outro: ""};
  function desenhar() {
    lista?.remove(); lista = el("div", {class: "ac-lista"});
    itens.forEach((it, i) => lista.append(el("div", {class: i === pos ? "sel" : "", onmousedown: e => { e.preventDefault(); escolher(it); }},
      it.internet ? "🌐 buscar «" + input.value.trim() + "» na internet" : [it.nome, el("small", {}, [rotuloTipo[it.tipo], it.contexto].filter(Boolean).join(" · ")), it.fonte && it.fonte !== "catálogo embutido" ? el("small", {}, "🌐") : ""])));
    wrap.append(lista);
  }
  async function escolher(it) {
    if (it.internet) { const q = input.value.trim(); let r;
      try { r = await api(`/api/lugares/buscar?q=${encodeURIComponent(q)}&internet=1`); } catch (e) { return aviso(e.message); }
      if (r.aviso) aviso(r.aviso); itens = [...r.lugares]; pos = -1; desenhar(); return; }
    fechar(); input.value = ""; await onPick(it);
  }
  input.addEventListener("input", () => { clearTimeout(t); t = setTimeout(async () => {
    const q = input.value.trim(); if (q.length < 2) return fechar();
    const r = await api(`/api/lugares/buscar?q=${encodeURIComponent(q)}`); itens = [...r.lugares, {internet: true}]; pos = -1; desenhar(); }, 180); });
  input.addEventListener("keydown", e => {
    if (e.key === "ArrowDown" && lista) { pos = Math.min(pos + 1, itens.length - 1); desenhar(); e.preventDefault(); }
    else if (e.key === "ArrowUp" && lista) { pos = Math.max(pos - 1, 0); desenhar(); e.preventDefault(); }
    else if (e.key === "Enter") { e.preventDefault(); if (lista && pos >= 0) escolher(itens[pos]); else if (input.value.trim()) { const v = input.value.trim(); fechar(); input.value = ""; (onLivre || onPick)({nome: v}); } }
    else if (e.key === "Escape") fechar();
  });
  input.addEventListener("blur", () => setTimeout(fechar, 160));
  return wrap;
}
