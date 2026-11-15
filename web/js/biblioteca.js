montarNav("/ui/biblioteca");
let D = null, autorSel = undefined;     // undefined = todos; null = sem autor; número = id
const PALETAS = [["#8b3a1f", "#c9743a"], ["#2f6f8f", "#5ea0bf"], ["#5d8a2f", "#98bd5c"], ["#7a4fa3", "#b28bd1"], ["#a8553a", "#d9946b"], ["#3d5a73", "#7396b3"], ["#8a6a1c", "#d0a947"], ["#6b3a58", "#b6769c"]];
const paleta = txt => { let h = 0; for (const ch of txt || "") h = (h * 31 + ch.charCodeAt(0)) >>> 0; return PALETAS[h % PALETAS.length]; };
const estilo = txt => { const [a, b] = paleta(txt); return `--c1:${a};--c2:${b};--lombada:${a}`; };
const iniciais = n => (n || "?").split(/\s+/).filter(x => x.length > 2 || /^[A-Z]/.test(x)).slice(0, 2).map(x => x[0]).join("").toUpperCase();

["#q", "#f-genero", "#f-midia", "#f-tag"].forEach(s => $(s).addEventListener("input", () => (s === "#q" ? atrasar : desenhar)()));
let _t; const atrasar = () => { clearTimeout(_t); _t = setTimeout(carregar, 220); };
async function carregar() {
  D = await api("/api/biblioteca?q=" + encodeURIComponent($("#q").value.trim()));
  const opc = (sel, rot, lista) => { const v = sel.value; sel.innerHTML = ""; sel.append(new Option(rot, "")); lista.forEach(x => sel.append(new Option(x, x))); sel.value = lista.includes(v) ? v : ""; };
  opc($("#f-genero"), "todos os gêneros", D.filtros.generos); opc($("#f-midia"), "todas as mídias", D.filtros.midias); opc($("#f-tag"), "todas as tags", D.filtros.tags);
  desenhar();
}
const passa = o => (!$("#f-genero").value || (o.generos || (o.genero ? [o.genero] : [])).includes($("#f-genero").value)) && (!$("#f-midia").value || o.midias.includes($("#f-midia").value)) && (!$("#f-tag").value || o.tags.includes($("#f-tag").value));

function desenhar() {
  const est = D.estantes.map(e => ({...e, obras: e.obras.filter(passa)})).filter(e => e.obras.length);
  $("#total").textContent = `${est.reduce((n, e) => n + e.obras.length, 0)} de ${D.total} obras`;
  const lado = $("#estante"); lado.innerHTML = "";
  const linha = (id, nome, n, autor) => el("div", {class: "autor" + (autorSel === id ? " on" : ""), onclick: () => { autorSel = autorSel === id ? undefined : id; desenhar(); }},
    el("div", {class: "avatar", style: estilo(nome)}, autor?.imagem ? el("img", {src: urlArquivo(autor.imagem)}) : iniciais(nome)),
    el("div", {}, el("div", {}, nome), el("small", {}, `${n} obra(s)`)), autor ? anel(autor.pct, 34, 4) : "");
  lado.append(el("div", {class: "kicker", style: "margin:.2rem .3rem .4rem"}, "Estantes"));
  if (!est.length) lado.append(el("div", {class: "muted", style: "padding:.6rem"}, "nenhuma estante"));
  est.forEach(e => lado.append(linha(e.autor ? e.autor.id : null, e.autor ? e.autor.nome : "Sem autoria principal registrada", e.obras.length, e.autor)));
  const parede = $("#livros"); parede.innerHTML = "";
  const mostrar = autorSel === undefined ? est : est.filter(e => (e.autor ? e.autor.id : null) === autorSel);
  if (!mostrar.length) { parede.append(el("div", {class: "vazio"}, D.total ? "Nenhuma obra com esses filtros." : "A biblioteca está vazia: catalogue um arquivo na página inicial e ele aparece aqui.")); return; }
  let i = 0;
  mostrar.forEach(e => {
    const bloco = el("div", {class: "prateleira"}, el("h2", {}, e.autor ? e.autor.nome : "Sem autoria principal registrada", el("small", {}, [e.autor?.nascimento, e.autor?.morte].filter(Boolean).join(" – ")))), grade = el("div", {class: "parede"});
    e.obras.forEach(o => grade.append(livro(o, e.autor, i++))); bloco.append(grade); parede.append(bloco);
  });
}
function livro(o, autor, i) {
  const ed = o.edicoes.find(e => e.caminho) || null, primeira = o.edicoes[0];
  const capa = el("div", {class: "capa"}, o.imagem ? el("img", {src: urlArquivo(o.imagem), loading: "lazy", alt: o.titulo}) : [el("div", {class: "t"}, o.titulo), autor ? el("div", {class: "a"}, autor.nome) : ""], anel(o.pct, 34, 4));
  const info = primeira ? [primeira.editora, primeira.local, primeira.ano_edicao,
    primeira.periodico, primeira.fasciculo_volume && `v. ${primeira.fasciculo_volume}`,
    primeira.fasciculo_numero && `n. ${primeira.fasciculo_numero}`, primeira.fasciculo_data,
    primeira.referencia].filter(Boolean).join(" · ") : "";
  const creditosObra = (o.agentes || []).filter(a => a.papel !== "autor_principal")
    .map(a => `${a.nome} (${a.papel === "coautor" ? "coautoria" : a.papel})`);
  const creditosManifestacoes = (o.edicoes || []).filter(e => e.creditos_manifestacao)
    .map(e => `${e.ano_edicao || "data não indicada"}: ${e.creditos_manifestacao}`);
  return el("article", {class: "livro", style: estilo(o.titulo) + `;animation-delay:${Math.min(i, 14) * 45}ms`}, capa,
    el("div", {class: "corpo"}, el("h3", {}, el("a", {href: urlFicha("work", o.id)}, o.titulo)),
      el("div", {class: "meta"}, [autor?.nome, o.ano].filter(Boolean).join(" · ")),
      creditosObra.length ? el("div", {class: "meta"}, "Participações na obra: " + creditosObra.join("; ")) : "",
      creditosManifestacoes.length ? el("div", {class: "meta"}, "Créditos por manifestação: " + creditosManifestacoes.join(" · ")) : "",
      el("div", {class: "badges"}, [...(o.generos || (o.genero ? [o.genero] : [])), o.tipo, ...o.midias.filter(m => m !== "texto verbal")].filter(Boolean).map(b => el("span", {class: "badge"}, b))),
      o.edicoes.length ? el("div", {class: "ed"}, `${o.edicoes.length} edição(ões)`, info ? ` — ${info}` : "", ed && ed.paginas ? ` · ${ed.paginas} p.` : "") : el("div", {class: "ed muted"}, "sem edições registradas"),
      el("div", {class: "acoes"}, ed ? el("a", {href: urlArquivo(ed.caminho), target: "_blank", title: ed.fonte || ""}, el("button", {class: "primario"}, "abrir " + (ed.formato || "arquivo"))) : el("span", {class: "muted meta"}, "sem arquivo"),
        el("a", {href: urlFicha("work", o.id)}, el("button", {}, "ficha")))));
}
carregar();
