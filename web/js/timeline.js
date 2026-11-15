montarNav("/ui/timeline");
// Tipos de ficha usam a paleta canônica de /api/vocab; edições mantêm cor própria.
const FAIXAS = [["autores", "Autores", "author", null], ["periodicos", "Periódicos", "periodical", null], ["obras", "Obras", "work", null],
                ["edicoes", "Edições", "work", "#6f93a8"], ["eventos", "Eventos", "event", null], ["instituicoes", "Instituições", "institution", null]];
const ativas = new Set(FAIXAS.map(f => f[0]));
let T = null, V = null, ppy = null, LAY = null;     // LAY: escala usada no desenho (para zoom e «ir para o ano»)
const NS = "http://www.w3.org/2000/svg";
const S = (tag, a = {}, ...k) => { const n = document.createElementNS(NS, tag); for (const [x, v] of Object.entries(a)) if (v != null) n.setAttribute(x, v); k.forEach(c => n.append(c.nodeType ? c : document.createTextNode(c))); return n; };
const corFaixa = (tipo, especifica) => especifica || V?.entidades?.[tipo]?.cor || "#999";

(async function () {
  try { [V, T] = await Promise.all([vocab(), api("/api/timeline")]); } catch (e) { $("#svg").replaceWith(el("p", {class: "erro", style: "padding:1.5rem"}, "Não consegui montar a linha do tempo: " + e.message)); return; }
  barra(); desenhar(true); gestos(); const f = new URLSearchParams(location.search).get("foco"); if (f) setTimeout(() => focar(f), 150);
})();

function barra() {
  const b = $("#barra"); b.innerHTML = "";
  b.append(el("strong", {}, "zoom"));
  [["ajustar", null], ["panorama", 1], ["séculos", 3], ["décadas", 12], ["anos", 40]].forEach(([t, v]) => b.append(el("button", {class: "mini", onclick: () => { ppy = v; desenhar(v == null); }}, t)));
  FAIXAS.forEach(([k, t, tp, cor]) => b.append(el("label", {title: k === "edicoes" ? "ano do exemplar que você tem em mãos (≠ ano da obra)" : ""}, el("input", {type: "checkbox", checked: true, onchange: e => { e.target.checked ? ativas.add(k) : ativas.delete(k); desenhar(false); }}), " ",
    el("span", {class: "dot " + tp, style: `background:${corFaixa(tp, cor)}`}), t)));
  b.append(el("input", {id: "ano-ir", type: "text", placeholder: "ir para o ano…", onkeydown: e => { if (e.key === "Enter") { const n = anoNum(e.target.value); if (n != null) irParaAno(n); } }}));
  b.append(el("span", {class: "muted", style: "font-size:.78rem"}, "Ctrl + roda: zoom · arraste para mover"));
  const sem = ["author", "work", "periodical", "event", "institution"].map(t => [t, (T.total[t] || 0) - (T.com_data[t] || 0)]).filter(x => x[1] > 0);
  $("#aviso-dados").textContent = sem.length ? "sem data, fora da linha: " + sem.map(([t, n]) => `${n} ${n === 1 ? "ficha" : "fichas"} de ${t === "author" ? "autor" : t === "work" ? "obra" : t === "periodical" ? "periódico" : t === "institution" ? "instituição" : "evento"}`).join(" · ") + ". Datas aceitam «1899», «c. 800 a.C.», «séc. V a.C.»…" : "";
}

function itens() {
  const L = {};
  L.autores = T.autores.map(a => ({tipo: "author", id: a.id, nome: a.nome, ini: a.nasc_num, fim: a.morte_num, precisaoIni: a.nascimento_epistemico?.tipo_precisao, precisaoFim: a.morte_epistemico?.tipo_precisao, rot: `${a.nascimento || "?"} – ${a.morte || "?"}`}));
  L.periodicos = T.periodicos.map(p => ({tipo: "periodical", id: p.id, nome: p.nome, ini: p.ini_num, fim: p.fim_num, precisaoIni: p.inicio_epistemico?.tipo_precisao, precisaoFim: p.fim_epistemico?.tipo_precisao, rot: `${p.ano_inicio || "?"} – ${p.ano_fim || "?"}`}));
  L.obras = T.obras.map(o => ({tipo: "work", id: o.id, nome: o.nome, ini: o.num, pt: true, precisaoIni: o.data_epistemica?.tipo_precisao, rot: `${o.autor ? o.autor + " · " : ""}${o.ano}`}));
  L.edicoes = T.edicoes.map(e => ({tipo: "work", id: e.work_id, anchor: e.manifestation_id,
    nome: `${e.nome} · ${e.tipo_aparicao || "manifestação"} ${e.ano}${e.periodico ? " · " + e.periodico : ""}${e.issue_id ? ` · ${e.volume ? "v. " + e.volume + " " : ""}${e.numero ? "n. " + e.numero : ""}` : ""}`,
    ini: e.num, de: e.ano_obra, pt: true,
    precisaoIni: e.data_epistemica?.tipo_precisao, rot: [e.tipo_aparicao || "manifestação", e.editora, e.referencia, e.fonte, e.data_epistemica?.tipo_precisao && e.data_epistemica.tipo_precisao !== "exata" ? `data ${e.data_epistemica.tipo_precisao}` : null].filter(Boolean).join(" · ")}));
  L.eventos = T.eventos.map(e => ({tipo: "event", id: e.id, nome: e.nome, ini: e.num, pt: true, precisaoIni: e.data_epistemica?.tipo_precisao, rot: e.ano}));
  L.instituicoes = T.instituicoes.map(i => ({tipo: "institution", id: i.id, nome: i.nome, ini: i.ini_num, fim: i.fim_num, precisaoIni: i.inicio_epistemico?.tipo_precisao, precisaoFim: i.fim_epistemico?.tipo_precisao, rot: `${i.fundacao || "?"} – ${i.extincao || "?"}`}));
  return L;
}

function desenhar(ajustar) {
  const L = itens(), todos = [];
  FAIXAS.forEach(([k]) => { if (ativas.has(k)) L[k].forEach(i => [i.ini, i.fim, i.de].forEach(v => v != null && todos.push(v))); });
  const svg = $("#svg"); svg.innerHTML = ""; $("#faixas").innerHTML = "";
  if (!todos.length) { svg.setAttribute("height", 80); svg.append(S("text", {x: 20, y: 40}, "Nenhuma ficha com data ainda. Preencha nascimento, ano da obra, início do periódico ou data do evento.")); return; }
  const min = Math.min(...todos) - 8, max = Math.max(...todos) + 8, M = 110, W0 = $("#rolagem").clientWidth;
  if (ajustar || !ppy) ppy = Math.max(0.2, Math.min(40, (W0 - M - 380) / (max - min)));
  const x = y => M + (y - min) * ppy, larg = t => t.length * 6.2 + 14; LAY = {min, max, M, x};
  let y0 = 34; const linhas = [];
  FAIXAS.forEach(([k, titulo, tp, especifica]) => {
    const cor = corFaixa(tp, especifica);
    if (!ativas.has(k) || !L[k].length) return;
    const rows = [];                                            // empacotamento: cada item na primeira linha livre
    const ordenados = [...L[k]].sort((a, b) => (a.ini ?? a.fim) - (b.ini ?? b.fim));
    ordenados.forEach(i => {
      const a = i.ini ?? i.fim, b = i.fim ?? i.ini;
      let xa = x(Math.min(a, i.de ?? a)), xb = i.pt ? x(Math.max(a, i.de ?? a)) + 9 : (i.ini != null && i.fim != null ? x(b) : x(a) + 40 * ppy);
      const fim = xb + 6 + larg(i.nome); let r = rows.findIndex(f => f < xa - 6); if (r < 0) { r = rows.length; rows.push(0); } rows[r] = fim; i._r = r; i._xa = xa; i._xb = xb;
    });
    linhas.push({k, titulo, cor, tp, y: y0, n: rows.length, itens: ordenados}); y0 += rows.length * 22 + 34;
  });
  const H = y0 + 24, Wt = Math.max(x(max) + 420, W0); svg.setAttribute("width", Wt); svg.setAttribute("height", H);
  // eixo
  const passos = [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000]; const passo = passos.find(p => p * ppy >= 70) || 2000;
  for (let a = Math.ceil(min / passo) * passo; a <= max; a += passo) {
    svg.append(S("line", {x1: x(a), x2: x(a), y1: 22, y2: H - 10, stroke: "#ece5d4"}));
    svg.append(S("text", {x: x(a) + 3, y: 14, class: "eixo"}, rotuloAno(a)));
  }
  if (min < 0 && max > 0) { svg.append(S("line", {x1: x(0), x2: x(0), y1: 18, y2: H - 10, stroke: "#b9a88a", "stroke-dasharray": "4 3"})); svg.append(S("text", {x: x(0) + 4, y: H - 4, class: "eixo"}, "a.C. ◂ ▸ d.C.")); }
  linhas.forEach(l => {
    $("#faixas").append(el("div", {class: "rot-faixa", style: `top:${l.y + 2}px;color:${l.cor}`, title: l.k === "edicoes" ? "ano do exemplar que você tem em mãos" : ""}, l.titulo));
    l.itens.forEach(i => {
      const yy = l.y + i._r * 22; const g = S("g", {class: "item", "data-k": `${i.tipo}:${i.id}`}); let moveu = false;
      g.addEventListener("click", () => { if (!JA_ARRASTOU) location.href = urlFicha(i.tipo, i.id) + (i.anchor ? `#manifestation-${i.anchor}` : ""); });
      g.addEventListener("mouseenter", ev => { svg.classList.add("foco"); document.querySelectorAll(`.item[data-k="${i.tipo}:${i.id}"]`).forEach(n => n.classList.add("on")); dica(ev, i, l.titulo); });
      g.addEventListener("mousemove", ev => dica(ev, i, l.titulo)); g.addEventListener("mouseleave", () => { svg.classList.remove("foco"); document.querySelectorAll(".item.on").forEach(n => n.classList.remove("on")); $("#dica").style.display = "none"; });
      const a = i.ini ?? i.fim, b = i.fim ?? i.ini;
      if (i.pt) {
        if (i.de != null && i.de !== a) g.append(S("line", {x1: x(i.de), x2: x(a), y1: yy + 8, y2: yy + 8, stroke: l.cor, "stroke-dasharray": "3 2"}));
        const cx = x(a), incerta = ["aproximada", "inferida", "incerta", "intervalo"].includes(i.precisaoIni);
        g.append(l.tp === "event" ? S("path", {class: "ponto-i", d: `M${cx},${yy + 1} l7,7 l-7,7 l-7,-7z`, fill: l.cor, stroke: incerta ? l.cor : "none", "stroke-dasharray": incerta ? "2 2" : null, "fill-opacity": incerta ? .55 : 1, style: `animation-delay:${Math.min(i._r * 40, 400)}ms`}) : S("rect", {class: "ponto-i", x: cx - 4, y: yy + 4, width: 9, height: 9, fill: l.cor, stroke: incerta ? l.cor : "none", "stroke-dasharray": incerta ? "2 2" : null, "fill-opacity": incerta ? .55 : 1, style: `animation-delay:${Math.min(i._r * 40, 400)}ms`}));
        g.append(S("text", {x: cx + 9, y: yy + 12}, i.nome));
      } else {
        const completo = i.ini != null && i.fim != null, xa = x(a), xb = completo ? x(b) : xa + 40 * ppy;
        g.append(S("rect", {class: "barra-i", style: `animation-delay:${Math.min(i._r * 60, 500)}ms`, x: xa, y: yy + 3, width: Math.max(xb - xa, 3), height: 11, rx: 3, fill: l.cor, "fill-opacity": completo ? .8 : .3, stroke: l.cor, "stroke-dasharray": (completo && !["aproximada", "inferida", "incerta", "intervalo"].includes(i.precisaoIni) && !["aproximada", "inferida", "incerta", "intervalo"].includes(i.precisaoFim)) ? null : "3 2"}));
        g.append(S("text", {x: Math.max(xb, xa + 3) + 5, y: yy + 12}, i.nome + (i.rot ? "  " + i.rot : "")));
      }
      svg.append(g);
    });
  });
}

/* ---------------- gestos: arrastar, zoom no cursor, cartão flutuante, foco ---------------- */
let JA_ARRASTOU = false;
const anoNum = t => { const m = String(t).match(/-?\d{1,4}/); if (!m) return null; return /a\.?\s*c|^-/i.test(t) ? -Math.abs(+m[0]) : +m[0]; };
function irParaAno(a) { if (!LAY) return; $("#rolagem").scrollTo({left: LAY.x(a) - $("#rolagem").clientWidth / 2, behavior: "smooth"}); }
function dica(ev, i, faixa) {
  const d = $("#dica"); d.style.display = "block"; d.style.left = Math.min(ev.clientX + 14, innerWidth - 300) + "px"; d.style.top = (ev.clientY + 14) + "px";
  d.innerHTML = `<b>${esc(i.nome)}</b><small>${esc(faixa)} · ${esc(i.rot)}</small><small>clique para abrir a ficha</small>`;
}
function focar(k) {
  const g = document.querySelector(`.item[data-k="${k}"]`); if (!g) return; const r = $("#rolagem"), b = g.getBoundingClientRect(), rr = r.getBoundingClientRect();
  r.scrollTo({left: r.scrollLeft + b.left - rr.left - r.clientWidth / 2, top: r.scrollTop + b.top - rr.top - r.clientHeight / 2, behavior: "smooth"}); g.classList.add("achado"); setTimeout(() => g.classList.remove("achado"), 3500);
}
function gestos() {
  const r = $("#rolagem"); let ini = null;
  r.addEventListener("mousedown", e => { if (e.button !== 0) return; ini = {x: e.clientX, y: e.clientY, sl: r.scrollLeft, st: r.scrollTop}; JA_ARRASTOU = false; });
  window.addEventListener("mousemove", e => { if (!ini) return; const dx = e.clientX - ini.x, dy = e.clientY - ini.y;
    if (Math.abs(dx) + Math.abs(dy) > 4) { JA_ARRASTOU = true; r.classList.add("arrastando"); } if (JA_ARRASTOU) { r.scrollLeft = ini.sl - dx; r.scrollTop = ini.st - dy; } });
  window.addEventListener("mouseup", () => { ini = null; r.classList.remove("arrastando"); setTimeout(() => JA_ARRASTOU = false, 30); });
  r.addEventListener("wheel", e => {
    if (e.ctrlKey || e.metaKey || e.altKey) {                      // zoom ancorado no ano sob o cursor
      e.preventDefault(); if (!LAY) return; const box = r.getBoundingClientRect(), px = e.clientX - box.left;
      const ano = LAY.min + (r.scrollLeft + px - LAY.M) / ppy; ppy = Math.max(0.15, Math.min(60, ppy * (e.deltaY < 0 ? 1.18 : 1 / 1.18)));
      desenhar(false); r.scrollLeft = LAY.x(ano) - px;
    } else if ($("#svg").getBoundingClientRect().height <= r.clientHeight + 2) { e.preventDefault(); r.scrollLeft += e.deltaY + e.deltaX; }
  }, {passive: false});
}
