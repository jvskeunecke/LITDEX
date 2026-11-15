montarNav("/ui/fichas");
const Q = new URLSearchParams(location.search);
let TIPO = Q.get("t") || "author", ATUAL = +Q.get("id") || null, V, LISTA = [];
const ATIVOS = new Set(Object.keys({author: 1, work: 1, periodical: 1, event: 1, media: 1, institution: 1}));   // todos à vista, ao mesmo tempo
const CARTOES = {};                                                                         // sugestões online por ficha
const lateral = $("#lateral"), principal = $("#principal");
const NOME = {author: "nome", work: "titulo", periodical: "titulo", event: "nome", media: "nome", institution: "nome"};

(async function iniciar() {
  V = await vocab(); desenharLateral(); await carregarLista(); if (ATUAL) abrir(TIPO, ATUAL);
  else principal.innerHTML = '<div class="vazio">Escolha uma ficha à esquerda — ou crie uma nova.</div>';
})();

/* ---------------- lateral: TODAS as fichas de uma vez ---------------- */
function desenharLateral() {
  lateral.innerHTML = "";
  const filtro = el("input", {id: "filtro", placeholder: "buscar em todas as fichas…"}); let t0;
  filtro.oninput = () => { clearTimeout(t0); t0 = setTimeout(carregarLista, 180); };
  const chips = el("div", {class: "filtros", id: "chips"});
  const novo = el("div", {class: "novo-menu"}, el("span", {class: "muted", style: "font-size:.78rem;align-self:center"}, "＋ nova:"),
    Object.entries(V.entidades).map(([t, e]) => el("button", {class: "mini", onclick: () => nova(t)}, e.rotulo.toLowerCase())));
  lateral.append(filtro, chips, novo, el("div", {id: "lista"}));
}
function desenharChips(contagem) {
  const box = $("#chips"); box.innerHTML = "";
  Object.entries(V.entidades).forEach(([t, e]) => box.append(el("button", {class: ATIVOS.has(t) ? "on" : "", onclick: () => { ATIVOS.has(t) ? ATIVOS.delete(t) : ATIVOS.add(t); carregarLista(); }},
    el("span", {class: "dot " + t}), `${e.plural} ${contagem[t] ?? 0}`)));
}
async function carregarLista() {
  const q = $("#filtro")?.value || "";
  const todas = await api(`/api/fichas?q=${encodeURIComponent(q)}`);
  const cont = {}; todas.forEach(x => cont[x.tipo] = (cont[x.tipo] || 0) + 1); desenharChips(cont);
  LISTA = todas.filter(x => ATIVOS.has(x.tipo));
  const box = $("#lista"); box.innerHTML = "";
  if (!LISTA.length) box.append(el("p", {class: "muted", style: "font-style:italic"}, Perfil.id ? "nada neste perfil ainda." : "nada ainda — catalogue um arquivo no Catálogo."));
  let ultimo = null;
  LISTA.forEach(x => {
    if (x.tipo !== ultimo) { ultimo = x.tipo; box.append(el("div", {class: "grupo-t"}, el("span", {class: "dot " + x.tipo}), V.entidades[x.tipo].plural)); }
    box.append(el("div", {class: "item" + (x.tipo === TIPO && x.id === ATUAL ? " on" : ""), "data-k": x.tipo + ":" + x.id, onclick: () => abrir(x.tipo, x.id)},
      anel(x.pct, 30, 4), el("div", {class: "t"}, x.nome, x.sub ? el("small", {}, x.sub) : "")));
  });
}
async function nova(tipo) {
  const n = prompt(`Nome${tipo === "work" || tipo === "periodical" ? " (título)" : ""} da nova ficha de ${V.entidades[tipo].rotulo.toLowerCase()}:`); if (!n) return;
  const r = await api(`/api/entidades/${tipo}`, {method: "POST", body: {[NOME[tipo]]: n}}); ATIVOS.add(tipo); await carregarLista(); abrir(tipo, r.id);
}

/* ---------------- ficha ---------------- */
async function abrir(tipo, id) {
  TIPO = tipo; ATUAL = id; history.replaceState(null, "", urlFicha(tipo, id));
  document.querySelectorAll(".item").forEach(i => i.classList.toggle("on", i.dataset.k === tipo + ":" + id));
  let f; try { f = await api(`/api/entidades/${tipo}/${id}`); } catch (e) { principal.innerHTML = `<div class="vazio">${esc(e.message)}</div>`; return; }
  const comp = LISTA.find(x => x.tipo === tipo && x.id === id) || (await api(`/api/fichas?q=${encodeURIComponent(f._nome)}`)).find(x => x.tipo === tipo && x.id === id);
  await desenhar(f, comp || {pct: 0, faltam: []});
  const item = document.querySelector(`.item[data-k="${tipo}:${id}"]`); item?.scrollIntoView({block: "nearest"});
  if (location.hash.startsWith("#manifestation-")) setTimeout(() => document.getElementById(location.hash.slice(1))?.scrollIntoView({behavior: "smooth", block: "center"}), 80);
}
const salvar = campos => api(`/api/entidades/${TIPO}/${ATUAL}`, {method: "PATCH", body: campos});
const bloco = (t, ...c) => {
  const slug = String(t).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return el("section", {class: "bloco", id: `sec-${slug}`}, el("h3", {}, t), ...c);
};
const recarregar = () => { carregarLista(); abrir(TIPO, ATUAL); };

function campo(rot, chave, valor, {sel, ph, w, parse, salvarFn} = {}) {
  let inp;
  if (sel) { inp = el("select", {}, sel.map(o => new Option(o || "—", o))); if (valor && !sel.includes(valor)) inp.append(new Option(valor, valor)); inp.value = valor || ""; }
  else inp = el("input", {value: valor || "", placeholder: ph || "", style: w ? `width:${w}` : ""});
  const grava = salvarFn || salvar;
  inp.addEventListener(sel ? "change" : "blur", async () => {
    if (!sel && inp.value === (valor || "")) return;
    try { await grava({[chave]: parse ? parse(inp.value) : inp.value}); valor = inp.value; aviso("salvo"); carregarLista(); } catch (e) { aviso(e.message); }
  });
  return el("label", {class: "cp"}, el("span", {class: "rot"}, rot), inp);
}
function mdBloco(valor, onSave) {
  const vista = el("div", {class: "md"}), ta = el("textarea", {value: valor || ""}); ta.style.display = "none";
  const pinta = () => { vista.innerHTML = md2html(valor) || '<em class="muted">clique para escrever (markdown)…</em>'; };
  pinta(); vista.onclick = () => { vista.style.display = "none"; ta.style.display = "block"; ta.focus(); };
  ta.onblur = async () => { try { if (ta.value !== (valor || "")) { await onSave(ta.value); valor = ta.value; aviso("salvo"); carregarLista(); } } catch (e) { aviso(e.message); }
    pinta(); ta.style.display = "none"; vista.style.display = ""; };
  return el("div", {}, vista, ta);
}
const arquivoLink = c => c ? el("a", {href: urlArquivo(c), target: "_blank"}, "abrir arquivo") : el("span", {class: "muted"}, "(sem arquivo)");
const link = (t, id, txt) => el("a", {href: urlFicha(t, id), onclick: e => { e.preventDefault(); abrir(t, id); }}, txt);
const li = (...c) => el("li", {}, ...c);

async function desenhar(f, comp) {
  principal.innerHTML = "";
  const e = V.entidades[TIPO];
  const capa = el("div", {class: "capa", title: "clique para trocar a imagem"}, f.imagem ? el("img", {src: urlArquivo(f.imagem)}) : (TIPO === "work" ? "capa" : "imagem"));
  const arq = el("input", {type: "file", accept: "image/*", style: "display:none"});
  capa.onclick = () => arq.click();
  arq.onchange = async () => { const fd = new FormData(); fd.append("imagem", arq.files[0]); await api(`/api/entidades/${TIPO}/${f.id}/imagem`, {method: "POST", form: fd}); recarregar(); };
  const nome = el("input", {class: "titulo", value: f._nome});
  nome.onblur = async () => { if (nome.value === f._nome) return; try { await salvar({[NOME[TIPO]]: nome.value}); f._nome = nome.value; aviso("salvo"); carregarLista(); } catch (x) { aviso(x.message); nome.value = f._nome; } };
  const faltam = comp.faltam.length ? el("div", {class: "faltam"}, "campos descritivos pendentes: ", comp.faltam.map(x => el("span", {class: "chip falta"}, x))) : el("div", {class: "faltam ok"}, "✓ campos descritivos centrais preenchidos");
  const documentacao = comp.documentacao ? el("div", {class: "faltam", title: "Mede apenas se os registros associados têm fonte identificável; não avalia a veracidade da fonte."},
    comp.documentacao.registros_associados
      ? `rastreabilidade documental: ${comp.documentacao.registros_com_fonte}/${comp.documentacao.registros_associados} registro(s) com fonte identificada`
      : "rastreabilidade documental: ainda não há registros de evidência associados") : "";
  const enriquecimento = comp.faltam_enriquecimento?.length ? el("div", {class: "faltam"}, "enriquecimento opcional: ", comp.faltam_enriquecimento.map(x => el("span", {class: "chip"}, x))) : "";
  principal.append(el("div", {class: "cab subir"}, TIPO !== "media" && TIPO !== "institution" ? el("div", {}, capa, arq) : "",
    el("div", {style: "flex:1;min-width:0"}, el("div", {class: "tipo-tag"}, el("span", {class: "dot " + TIPO}), e.rotulo), nome, faltam, documentacao, enriquecimento,
      el("div", {style: "margin:.5rem 0;display:flex;gap:.5rem;align-items:center;flex-wrap:wrap"}, perfilBtn(f), TIPO === "media" ? "" : el("a", {href: `/ui/grafo?foco=${TIPO}:${f.id}`}, el("button", {class: "mini"}, "ver no grafo")))),
    anel(comp.pct, 76, 8)));
  await ({author: fAutor, work: fObra, periodical: fPeriodico, event: fEvento, media: fMidia, institution: fInstituicao})[TIPO](f);
  principal.append(await blocoEvidencias(f));
  principal.append(blocoOnline(f));
  if (TIPO !== "media") principal.append(blocoLugares(f));
  principal.append(blocoTags(f));
  const relBloco = bloco("Relações"); principal.append(relBloco);
  painelRelacoes(TIPO, f.id, () => carregarLista()).then(p => relBloco.append(p));
  if (TIPO !== "media" && TIPO !== "institution") principal.append(blocoGaleria(f));
  const destrutivo = Perfil.id
    ? "Excluir definitivamente do acervo geral"
    : "Excluir esta ficha do acervo geral";
  principal.append(el("section", {class: "bloco"},
    el("p", {class: "teoria"}, Perfil.id ? "A ficha pertence ao acervo geral e pode aparecer em vários perfis. Removê-la daqui não deve apagar os dados compartilhados." : "A exclusão global remove esta ficha, suas relações e seus vínculos; obras de um autor permanecem no acervo sem autor."),
    el("button", {class: "perigo", onclick: () => excluir(f)}, destrutivo)));
  if (TIPO === "work") adicionarNavegacaoLocal();
}
function adicionarNavegacaoLocal() {
  const grupos = [
    {rotulo: "Identificação", ids: ["sec-identificacao", "sec-generos-e-subgeneros-nao-excludentes", "sec-midias", "sec-notas"]},
    {rotulo: "Manifestações e arquivos", ids: ["sec-manifestacoes-versoes-e-arquivos"]},
    {rotulo: "Agentes e relações", ids: ["sec-agentes-e-papeis", "sec-relacoes"]},
    {rotulo: "Lugares e classificação", ids: ["sec-lugar", "sec-tags", "sec-imagens"]}
  ];
  const nav = el("nav", {id: "nav-ficha", "aria-label": "Navegação nesta ficha"});
  nav.append(el("span", {class: "nav-ficha-titulo"}, "Nesta ficha"));
  grupos.forEach(g => {
    const alvo = g.ids.map(id => document.getElementById(id)).find(Boolean);
    if (!alvo) return;
    nav.append(el("a", {href: `#${alvo.id}`, onclick: ev => { ev.preventDefault(); alvo.scrollIntoView({behavior: "smooth", block: "start"}); history.replaceState(null, "", `${location.pathname}${location.search}#${alvo.id}`); }}, g.rotulo));
  });
  principal.prepend(nav);
}
function perfilBtn(f) {
  if (!Perfil.id) return "";
  const dentro = (f.perfis || []).includes(Perfil.id);
  return dentro ? [el("span", {class: "ok"}, "✓ neste perfil"), el("button", {class: "mini", onclick: async () => {
      if (!confirm(`Remover «${f._nome}» apenas do perfil ativo? A ficha e seus dados continuarão no acervo geral e nos demais perfis.`)) return;
      await api(`/api/perfis/${Perfil.id}/itens/${TIPO}/${f.id}`, {method: "DELETE"});
      ATUAL = null; history.replaceState(null, "", "/ui/fichas");
      principal.innerHTML = '<div class="vazio">Ficha removida deste perfil; o registro geral foi preservado.</div>';
      await carregarLista();
    }}, "remover apenas deste perfil")]
    : el("button", {class: "mini", onclick: async () => { await api(`/api/perfis/${Perfil.id}/itens`, {method: "POST", body: {tipo: TIPO, id: f.id}}); recarregar(); }}, "＋ anexar ao perfil ativo");
}
async function excluir(f) {
  const extra = TIPO === "author" ? "\nAs obras ficam no acervo, sem autor." : TIPO === "work" ? "\nOs arquivos vão para a lixeira (data/_trash)." : "";
  if (!confirm(`Excluir «${f._nome}»?\nAs relações com esta ficha também somem.${extra}`)) return;
  const r = await api(`/api/entidades/${TIPO}/${f.id}`, {method: "DELETE"});
  aviso(r.obras_sem_autor ? `${r.obras_sem_autor} obra(s) ficaram sem autor` : "excluída");
  ATUAL = null; history.replaceState(null, "", "/ui/fichas"); principal.innerHTML = '<div class="vazio">Ficha excluída.</div>'; carregarLista();
}

/* ---------------- por tipo ---------------- */
function fAutor(f) {
  principal.append(el("div", {class: "campos"},
    campo("Nascimento", "nascimento", f.nascimento, {w: "11em", ph: "1839-06-21 · c. 800 a.C."}), campo("Morte", "morte", f.morte, {w: "11em"}),
    campo("Também aparece como (separe por vírgula)", "variantes", JSON.parse(f.variantes || "[]").join(", "), {w: "24em", ph: "apelidos e grafias — ensinam o scanner a reconhecer este autor",
      parse: v => v.split(",").map(x => x.trim()).filter(Boolean)})));
  principal.append(bloco("Dados biográficos", mdBloco(f.bio, v => salvar({bio: v}))));
  const ul = el("ul", {class: "lista"});
  f.obras.forEach(o => ul.append(li(link("work", o.id, o.titulo), el("span", {class: "muted"}, [o.genero, o.tipo, o.ano].filter(Boolean).join(" · ")), o.arquivo ? el("a", {href: urlArquivo(o.arquivo), target: "_blank"}, "abrir arquivo") : "")));
  if (!f.obras.length) ul.append(li(el("em", {class: "muted"}, "nenhuma obra — use o Catálogo (scanner) ou o botão abaixo")));
  principal.append(bloco("Obras", ul, el("button", {class: "mini", onclick: async () => {
    const t = prompt("Título da obra:"); if (!t) return;
    const r = await api("/api/entidades/work", {method: "POST", body: {titulo: t, author_id: f.id}}); await carregarLista(); abrir("work", r.id); }}, "+ obra sem arquivo")));
  const nomesPapel = {tradutor: "tradutor(a)", organizador: "organizador(a)", ilustrador: "ilustrador(a)", prefaciador: "prefaciador(a)", entrevistador: "entrevistador(a)", entrevistado: "entrevistado(a)"};
  const pap = (f.participacoes || []).filter(p => !["autor_principal", "coautor"].includes(p.papel));
  const pbox = el("ul", {class: "lista"});
  pap.forEach(p => pbox.append(li(link("work", p.work_id, p.titulo), el("span", {class: "muted"}, nomesPapel[p.papel] || p.papel), p.ano ? el("span", {class: "meta"}, " · " + p.ano) : "", p.fonte ? el("span", {class: "meta"}, " · fonte: " + p.fonte) : "")));
  if (!pap.length) pbox.append(li(el("span", {class: "muted"}, "nenhum papel adicional registrado no nível da obra")));
  principal.append(bloco("Outras participações em obras", pbox));
  const mb = el("ul", {class: "lista"});
  (f.participacoes_manifestacoes || []).forEach(p => mb.append(li(link("work", p.work_id, p.titulo), el("span", {class: "muted"}, nomesPapel[p.papel] || p.papel), el("span", {class: "meta"}, [p.tipo_aparicao, p.ano_edicao, p.periodico, p.referencia].filter(Boolean).join(" · ")))));
  if (!mb.children.length) mb.append(li(el("span", {class: "muted"}, "nenhum papel registrado numa manifestação específica")));
  principal.append(bloco("Participações em manifestações", mb));
}

const ROTULO_PAPEL = {autor_principal: "autor principal", coautor: "coautor", tradutor: "tradução",
  organizador: "organização", ilustrador: "ilustração", prefaciador: "prefácio",
  entrevistador: "entrevistador", entrevistado: "entrevistado"};
const PAPEIS_OBRA = ["autor_principal", "coautor", "tradutor", "organizador", "ilustrador",
  "prefaciador", "entrevistador", "entrevistado"];
const PAPEIS_EDICAO = ["tradutor", "organizador", "ilustrador", "prefaciador", "entrevistador",
  "entrevistado", "autor_principal", "coautor"];
const ESTADO_EVIDENCIA = {vigente: "vigente", revisao_necessaria: "revisar", nao_sustenta: "não sustenta"};

/* Editor de papéis — o mesmo componente para a obra e para cada edição.
   Grava sempre no registro canônico (work_agents / manifestation_agents). */
function editorAgentes(escopo, alvo, agentes, papeis) {
  const base = escopo === "obra" ? `/api/obras/${alvo}/agentes` : `/api/manifestacoes/${alvo}/agentes`;
  const caixa = el("div", {class: "agentes"});
  if (!agentes.length) caixa.append(el("p", {class: "muted"}, "nenhum agente registrado"));
  agentes.forEach(a => caixa.append(el("div", {class: "agente-linha"},
    el("span", {class: "rot"}, ROTULO_PAPEL[a.papel] || a.papel),
    link("author", a.author_id, a.nome),
    a.ano ? el("span", {class: "meta"}, a.ano) : "",
    a.fonte ? el("span", {class: "meta"}, "fonte: " + a.fonte) : "",
    a.notas ? el("span", {class: "meta"}, a.notas) : "",
    el("button", {class: "x", title: "remover este papel", onclick: async () => {
      if (!confirm(`Remover ${a.nome} como ${ROTULO_PAPEL[a.papel] || a.papel}? A evidência ligada será reaberta.`)) return;
      try { await api(`${base}/${a.id}`, {method: "DELETE"}); recarregar(); } catch (e) { aviso(e.message); }
    }}, "×"))));

  const sel = el("select", {}, papeis.map(p => new Option(ROTULO_PAPEL[p], p)));
  const escolhida = el("span", {class: "muted"}, "ninguém escolhido");
  const inp = el("input", {placeholder: "buscar pessoa…", style: "width:13em"});
  let alvoAutor = null;
  const wrap = buscaEntidade(inp, {tipos: ["author"], onPick: async it => {
    alvoAutor = await resolverEntidade(it); escolhida.textContent = alvoAutor.nome;
  }});
  const ano = el("input", {placeholder: "ano", style: "width:5em"});
  const fonte = el("input", {placeholder: "fonte", style: "width:10em"});
  const add = el("button", {class: "mini", onclick: async () => {
    if (!alvoAutor) return aviso("escolha a pessoa");
    try {
      const corpo = {author_id: alvoAutor.id, papel: sel.value, fonte: fonte.value || null};
      if (escopo === "obra" && ano.value.trim()) corpo.ano = ano.value.trim();
      await api(base, {method: "POST", body: corpo});
      recarregar();
    } catch (e) { aviso(e.message); }
  }}, "adicionar papel");
  return el("div", {}, caixa,
    el("div", {class: "linha"}, sel, wrap, escolhida, escopo === "obra" ? ano : "", fonte, add));
}

async function blocoEvidencias(f) {
  const fontes = await api("/api/fontes").catch(() => []);
  const lista = el("div", {class: "evidencias"});
  const todas = [...(f.evidencias || []), ...(f.evidencias_manifestacoes || [])];
  if (!todas.length) lista.append(el("p", {class: "muted"}, "nenhuma evidência registrada"));
  todas.forEach(ev => lista.append(el("div", {class: "evidencia"},
    el("span", {class: "chip " + (ev.estado === "vigente" ? "ok" : "falta")}, ESTADO_EVIDENCIA[ev.estado] || ev.estado),
    el("strong", {}, ev.afirmacao), " ",
    el("span", {class: "teoria"}, [
      ev.fonte_titulo ? "fonte: " + ev.fonte_titulo : "sem fonte",
      ev.localizador ? " · " + ev.localizador : "",
      ev.manifestacao_id ? " · manifestação #" + ev.manifestacao_id : ""].join("")),
    ev.trecho ? el("blockquote", {class: "teoria"}, "«" + ev.trecho + "»") : "",
    ev.motivo_revisao ? el("div", {class: "teoria"}, "⚠ " + ev.motivo_revisao) : "",
    el("div", {class: "linha"},
      el("button", {class: "mini", onclick: async () => {
        await api(`/api/evidencias/${ev.id}`, {method: "PATCH",
          body: {estado: ev.estado === "vigente" ? "nao_sustenta" : "vigente"}}); recarregar();
      }}, ev.estado === "vigente" ? "marcar como não sustenta" : "confirmar como vigente"),
      el("button", {class: "x", title: "excluir evidência", onclick: async () => {
        if (!confirm("Excluir esta evidência? A fonte continua no catálogo.")) return;
        await api(`/api/evidencias/${ev.id}`, {method: "DELETE"}); recarregar();
      }}, "×")))));

  const selFonte = el("select", {style: "max-width:20em"}, new Option("— sem fonte —", ""), fontes.map(s => new Option(s.titulo, s.id)));
  const afirmacao = el("input", {placeholder: "o que esta evidência sustenta", style: "width:100%"});
  const trecho = el("input", {placeholder: "trecho transcrito (opcional)", style: "width:100%"});
  const loc = el("input", {placeholder: "página / localizador", style: "width:12em"});
  const add = el("button", {class: "mini", onclick: async () => {
    if (!afirmacao.value.trim()) return aviso("descreva a afirmação");
    try {
      await api("/api/evidencias", {method: "POST", body: {
        entidade_tipo: TIPO, entidade_id: f.id, afirmacao: afirmacao.value.trim(),
        trecho: trecho.value.trim() || null, localizador: loc.value.trim() || null,
        source_id: selFonte.value ? +selFonte.value : null}});
      recarregar();
    } catch (e) { aviso(e.message); }
  }}, "registrar evidência");
  return bloco("Evidências",
    el("p", {class: "teoria"}, "Cada evidência liga uma fonte e um trecho a uma afirmação. Mudar a prova reabre a revisão; excluir a ficha não apaga o trecho."),
    lista, el("div", {class: "linha"}, selFonte, loc), afirmacao, trecho, el("div", {class: "linha"}, add));
}

async function fObra(f) {
  const autores = await api("/api/entidades/author?todos=1");
  const selA = el("select", {}, new Option("— sem autor —", ""), autores.map(a => new Option(a.nome, a.id))); selA.value = f.author_id || "";
  selA.onchange = async () => { await salvar({author_id: selA.value ? +selA.value : null}); aviso("salvo"); recarregar(); };
  principal.append(el("div", {id: "sec-identificacao", class: "campos"}, el("label", {class: "cp"}, el("span", {class: "rot"}, "Autor principal"), selA),
    campo("Ano da obra", "ano", f.ano, {w: "10em", ph: "publicação original"}), campo("Categoria ampla", "genero", f.genero, {sel: ["", "prosa", "verso"]}),
    campo("Tipo / forma", "tipo", f.tipo, {w: "12em", ph: "romance, soneto, artigo…"})));

  // Atribuições de gênero são múltiplas; a categoria ampla antiga (prosa/verso) continua compatível.
  const termosGenero = await api("/api/generos");
  const caixaGenero = el("div", {class: "campos-ap"});
  f.generos_especificos.forEach(g => caixaGenero.append(el("span", {class: "chip"}, g.caminho,
    el("button", {class: "x", title: "retirar este gênero desta obra", onclick: async () => {
      await api(`/api/works/${f.id}/generos/${g.id}`, {method: "DELETE"}); recarregar();
    }}, "×"))));
  const inputGenero = el("input", {placeholder: "+ gênero ou subgênero (Enter)", list: `lista-generos-${f.id}`, style: "width:16em"});
  const dlGenero = el("datalist", {id: `lista-generos-${f.id}`}, termosGenero.map(g => new Option(g.nome)));
  const paiGenero = el("select", {style: "max-width:16em"}, new Option("sem gênero superior", ""), termosGenero.map(g => new Option(g.caminho, g.id)));
  inputGenero.onkeydown = async e => {
    if (e.key !== "Enter" || !inputGenero.value.trim()) return;
    e.preventDefault();
    try {
      const termoExistente = termosGenero.find(g => String(g.nome).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase() === String(inputGenero.value.trim()).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase());
      await api(`/api/works/${f.id}/generos`, {method: "POST", body: termoExistente
        ? {genre_id: termoExistente.id}
        : {nome: inputGenero.value.trim(), parent_id: paiGenero.value || null}});
      recarregar();
    } catch (e2) { aviso(e2.message); }
  };
  principal.append(bloco("Gêneros e subgêneros (não excludentes)",
    el("p", {class: "teoria"}, "Uma obra pode receber vários gêneros. O gênero superior organiza a árvore; não impede a atribuição simultânea de outros termos."),
    caixaGenero, el("div", {class: "linha"}, inputGenero, paiGenero, dlGenero)));

  const caixa = el("div"), novaM = el("input", {placeholder: "+ mídia (Enter)", list: "dl-m", style: "width:12em"});
  const dl = el("datalist", {id: "dl-m"}, V.midias_sugeridas.map(m => new Option(m)));
  f.midias.forEach(m => caixa.append(el("span", {class: "chip"}, el("span", {class: "dot media"}), link("media", m.id, m.nome),
    el("button", {class: "x", onclick: async () => { await api(`/api/works/${f.id}/midias/${m.id}`, {method: "DELETE"}); recarregar(); }}, "×"))));
  if (f.midias.length > 1) caixa.append(el("div", {class: "teoria"}, "plurimidialidade — combinação de mídias no mesmo artefato (Rajewsky, 2015)"));
  novaM.onkeydown = async e => { if (e.key === "Enter" && novaM.value.trim()) { await api(`/api/works/${f.id}/midias`, {method: "POST", body: {nome: novaM.value}}); recarregar(); } };
  principal.append(bloco("Mídias", caixa, novaM, dl), bloco("Notas", mdBloco(f.notas, v => salvar({notas: v}))));
  const partes = (f.relacoes || []).filter(r => r.tipo === "parte_de" && r.sentido === "entrando");
  const continentes = (f.relacoes || []).filter(r => r.tipo === "parte_de" && r.sentido === "saindo");
  const gaveta = el("div", {class:"gaveta-obras"});
  if (continentes.length) gaveta.append(el("p", {class:"teoria"}, "Esta obra é parte de: "), ...continentes.map(r=>el("div",{class:"chip"},link("work",r.outro.id,r.outro.nome))));
  if (partes.length) {
    const listaPartes=el("div",{class:"gaveta-itens"});
    partes.forEach(r=>listaPartes.append(el("div",{class:"gaveta-item"},el("span",{},"↳"),link("work",r.outro.id,r.outro.nome),el("span",{class:"muted"},"obra integrante"))));
    const abrirGaveta=el("button",{class:"mini",onclick:()=>{const aberta=listaPartes.style.display!=="none";listaPartes.style.display=aberta?"none":"grid";abrirGaveta.textContent=aberta?`▸ abrir gaveta (${partes.length})`:`▾ fechar gaveta (${partes.length})`;}},`▸ abrir gaveta (${partes.length})`);
    listaPartes.style.display="none"; gaveta.append(abrirGaveta,listaPartes);
  } else gaveta.append(el("p",{class:"muted"},"Nenhuma obra integrante registrada. Use Relações → «é parte de» para organizar capítulos, poemas e textos contidos nesta obra."));
  principal.append(bloco("Gaveta de obras integrantes",gaveta));

  const periodicos = await api("/api/entidades/periodical?todos=1");
  const obrasContinente = (await api("/api/entidades/work?todos=1")).filter(o => o.id !== f.id);
  const manifestacoesParaConteiner = (await api("/api/manifestacoes?todos=1")).filter(m => m.work_id !== f.id);
  const rotuloManifestacao = m => [m.obra, m.tipo_aparicao || "manifestação", m.ano_edicao,
    m.periodico, m.fasciculo_volume && `v. ${m.fasciculo_volume}`, m.fasciculo_numero && `n. ${m.fasciculo_numero}`,
    m.referencia].filter(Boolean).join(" · ");
  const eds = bloco("Manifestações, versões e arquivos",
    el("p", {class: "teoria", style: "margin:.2rem 0"}, "A obra é a unidade intelectual; cada manifestação registra uma versão, edição ou aparição concreta. Para um soneto publicado num livro e num periódico, mantenha uma ficha para o soneto, registre «parte de» na relação com o livro e crie uma manifestação por aparição, indicando o veículo concreto. O estatuto de fonte primária/secundária depende do foco da investigação: a ficha guarda evidência e contexto, não uma classificação absoluta."));
  for (const ed of f.edicoes) {
    const grava = c => api(`/api/edicoes/${ed.id}`, {method: "PATCH", body: c});
    const selP = el("select", {}, new Option("— sem periódico específico —", ""), periodicos.map(p => new Option(p.nome, p.id)));
    selP.value = ed.periodical_id || "";
    const selI = el("select", {}, new Option("— fascículo não identificado —", ""));
    async function carregarFasciculos() {
      selI.innerHTML = ""; selI.append(new Option("— fascículo não identificado —", ""));
      if (selP.value) {
        const fasciculos = await api(`/api/periodicals/${selP.value}/fasciculos`);
        fasciculos.forEach(i => {
          const partes = [i.volume ? `v. ${i.volume}` : "", i.numero ? `n. ${i.numero}` : "", i.data || "", i.titulo || ""].filter(Boolean);
          selI.append(new Option(partes.join(" · ") || `Fascículo ${i.id}`, i.id));
        });
      }
      selI.value = ed.issue_id || "";
    }
    await carregarFasciculos();
    selP.onchange = async () => { try {
      const payload = {periodical_id: selP.value || null};
      if (ed.issue_id) payload.issue_id = null;
      await grava(payload); ed.issue_id = null; await carregarFasciculos(); aviso("salvo"); recarregar();
    } catch (e) { aviso(e.message); selP.value = ed.periodical_id || ""; } };
    selI.onchange = async () => { try { await grava({issue_id: selI.value || null}); aviso("fascículo salvo"); recarregar(); } catch (e) { aviso(e.message); } };
    const selC = el("select", {}, new Option("— sem obra continente —", ""), obrasContinente.map(o => new Option(o.nome, o.id)));
    selC.value = ed.container_work_id || "";
    const selCM = el("select", {}, new Option("— edição concreta não identificada —", ""),
      manifestacoesParaConteiner.map(m => new Option(rotuloManifestacao(m), m.id)));
    selCM.value = ed.container_manifestation_id || "";
    selC.onchange = async () => { try {
      await grava({container_work_id: selC.value || null, container_manifestation_id: null});
      selCM.value = ""; aviso("obra continente salva; edição específica removida"); recarregar();
    } catch (e) { aviso(e.message); selC.value = ed.container_work_id || ""; } };
    selCM.onchange = async () => { try {
      const m = manifestacoesParaConteiner.find(x => String(x.id) === selCM.value);
      if (m) selC.value = String(m.work_id);
      await grava({container_manifestation_id: selCM.value || null}); aviso("edição continente salva"); recarregar();
    } catch (e) { aviso(e.message); selCM.value = ed.container_manifestation_id || ""; } };
    eds.append(el("div", {class: "ed", id: `manifestation-${ed.id}`}, el("div", {}, arquivoLink(ed.caminho), " ",
      ed.formato ? el("span", {class: "muted"}, ed.formato + (ed.paginas ? ` · ${ed.paginas} p.` : "")) : "",
      ed.periodico_titulo ? el("span", {class: "meta"}, " · em periódico: ", link("periodical", ed.periodical_id, ed.periodico_titulo)) : "",
      ed.fasciculo_numero || ed.fasciculo_volume ? el("span", {class: "meta"}, ` · fascículo ${ed.fasciculo_volume ? "v. " + ed.fasciculo_volume : ""}${ed.fasciculo_numero ? " n. " + ed.fasciculo_numero : ""}${ed.fasciculo_data ? " · " + ed.fasciculo_data : ""}`) : "",
      ed.obra_continente_titulo ? el("span", {class: "meta"}, " · incluída em: ", link("work", ed.container_work_id, ed.obra_continente_titulo)) : "",
      el("button", {class: "x", style: "float:right", title: "excluir manifestação", onclick: async () => {
        if (confirm("Excluir esta manifestação? O arquivo vai para a lixeira; a obra permanece.")) { await api(`/api/edicoes/${ed.id}`, {method: "DELETE"}); recarregar(); } }}, "×")),
      el("div", {class: "campos"}, campo("Tipo de aparição", "tipo_aparicao", ed.tipo_aparicao || "edição", {salvarFn: grava, sel: ["edição", "publicação em periódico", "incluído em livro", "manuscrito", "versão digital", "reedição", "tradução", "outro"]}),
        el("label", {class: "cp"}, el("span", {class: "rot"}, "Periódico / veículo"), selP),
        el("label", {class: "cp"}, el("span", {class: "rot"}, "Fascículo específico"), selI),
        el("label", {class: "cp"}, el("span", {class: "rot"}, "Obra continente (sem edição específica)"), selC),
        el("label", {class: "cp"}, el("span", {class: "rot"}, "Edição concreta que contém esta aparição"), selCM),
        campo("Referência, volume, número, páginas", "referencia", ed.referencia, {salvarFn: grava, w: "18em"}),
        campo("Editora", "editora", ed.editora, {salvarFn: grava, w: "13em"}), campo("Local", "local", ed.local, {salvarFn: grava, w: "9em"}),
        campo("Ano desta manifestação", "ano_edicao", ed.ano_edicao, {salvarFn: grava, w: "7em"}), campo("Idioma", "idioma", ed.idioma, {salvarFn: grava, w: "8em"}),
      campo("Nota da manifestação", "notas", ed.notas, {salvarFn: grava, w: "14em"}), campo("Fonte", "fonte", ed.fonte, {salvarFn: grava, w: "14em"})),
      el("div", {class: "creditos"},
        el("div", {class: "rot"}, "Créditos desta edição (tradução, organização, ilustração…)"),
        editorAgentes("manifestacao", ed.id,
          (f.agentes_manifestacao || []).filter(a => a.manifestation_id === ed.id), PAPEIS_EDICAO))));
  }
  const selNovaObraContinente = el("select", {name: "container_work_id"}, new Option("— sem obra continente —", ""), obrasContinente.map(o => new Option(o.nome, o.id)));
  const selNovaManifestacaoContinente = el("select", {name: "container_manifestation_id"}, new Option("— edição concreta não identificada —", ""),
    manifestacoesParaConteiner.map(m => new Option(rotuloManifestacao(m), m.id)));
  selNovaManifestacaoContinente.onchange = () => {
    const m = manifestacoesParaConteiner.find(x => String(x.id) === selNovaManifestacaoContinente.value);
    if (m) selNovaObraContinente.value = String(m.work_id);
  };
  selNovaObraContinente.onchange = () => {
    const m = manifestacoesParaConteiner.find(x => String(x.id) === selNovaManifestacaoContinente.value);
    if (m && String(m.work_id) !== selNovaObraContinente.value) selNovaManifestacaoContinente.value = "";
  };
  const fd = el("form", {class: "ed", onsubmit: async e => { e.preventDefault(); try { await api(`/api/works/${f.id}/edicoes`, {method: "POST", form: new FormData(fd)}); recarregar(); } catch (x) { aviso(x.message); } }},
    el("strong", {class: "muted"}, "+ nova manifestação "), el("input", {type: "file", name: "arquivo", accept: ".pdf,.docx,.txt,.md"}),
    el("div", {class: "campos"},
      el("label", {class: "cp"}, el("span", {class: "rot"}, "Tipo de aparição"), el("select", {name: "tipo_aparicao"}, ["edição", "publicação em periódico", "incluído em livro", "manuscrito", "versão digital", "reedição", "tradução", "outro"].map(x => new Option(x, x)))),
      el("label", {class: "cp"}, el("span", {class: "rot"}, "Periódico / veículo"), el("select", {name: "periodical_id"}, new Option("— nenhum —", ""), periodicos.map(p => new Option(p.nome, p.id)))),
      el("label", {class: "cp"}, el("span", {class: "rot"}, "Obra continente"), selNovaObraContinente),
      el("label", {class: "cp"}, el("span", {class: "rot"}, "Edição concreta continente"), selNovaManifestacaoContinente),
      ...[["referencia", "Referência / páginas"], ["volume", "Volume do periódico"], ["numero", "Número do fascículo"], ["data_fasciculo", "Data do fascículo"], ["titulo_fasciculo", "Título do fascículo"], ["editora", "Editora"], ["local", "Local"], ["ano_edicao", "Ano da manifestação"], ["idioma", "Idioma"], ["notas", "Nota"], ["fonte", "Fonte"]]
        .map(([n, r]) => el("label", {class: "cp"}, el("span", {class: "rot"}, r), el("input", {name: n, style: "width:11em"})))),
    el("button", {}, "adicionar manifestação"));
  eds.append(fd); principal.append(eds);

  principal.append(bloco("Agentes e papéis",
    el("p", {class: "teoria"}, "Quem fez o quê nesta obra. O papel principal é único; tradução e organização registradas aqui valem para a obra, não para uma edição específica."),
    editorAgentes("obra", f.id, f.agentes || [], PAPEIS_OBRA)));
}

function fPeriodico(f) {
  principal.append(el("div", {class: "campos"}, campo("Tipo", "tipo", f.tipo, {sel: ["", ...V.tipos_periodico]}), campo("ISSN", "issn", f.issn, {w: "9em"}),
    campo("Início", "ano_inicio", f.ano_inicio, {w: "8em", ph: "1922"}), campo("Fim", "ano_fim", f.ano_fim, {w: "8em"})),
    bloco("Notas", mdBloco(f.notas, v => salvar({notas: v}))));
  const ul = el("ul", {class: "lista"});
  f.obras.forEach(o => ul.append(li(link("work", o.id, o.titulo), el("span", {class: "muted"}, [o.autor, o.ano_pub || o.ano, o.issue_id ? [o.fasciculo_volume && `v. ${o.fasciculo_volume}`, o.fasciculo_numero && `n. ${o.fasciculo_numero}`, o.fasciculo_data].filter(Boolean).join(" · ") : "", o.referencia, o.agentes_manifestacao].filter(Boolean).join(" · ")))));
  if (!f.obras.length) ul.append(li(el("em", {class: "muted"}, "nenhuma manifestação publicada registrada — na ficha da obra, adicione uma manifestação e vincule o periódico")));
  const col = el("ul", {class: "lista"}), papel = {colaborou_em: "colaborou", editou: "editou / dirigiu", fundou: "fundou"};
  f.colaboradores.forEach(c => col.append(li(link("author", c.id, c.nome), el("span", {class: "muted"}, papel[c.papel]))));
  if (!f.colaboradores.length) col.append(li(el("em", {class: "muted"}, "sem colaboradores registrados")));
  const fi = el("ul", {class: "lista"});
  (f.fasciculos || []).forEach(i => {
    const detalhes = el("details", {class: "ed"}, el("summary", {}, "editar fascículo"));
    const form = el("form", {class: "campos", onsubmit: async e => {
      e.preventDefault(); const data = Object.fromEntries(new FormData(form).entries());
      try { await api(`/api/fasciculos/${i.id}`, {method: "PATCH", body: data}); aviso("fascículo salvo"); recarregar(); }
      catch (x) { aviso(x.message); }
    }}, ...[["volume", "Volume", i.volume], ["numero", "Número", i.numero], ["data", "Data", i.data],
      ["titulo", "Título", i.titulo], ["referencia", "Referência", i.referencia], ["notas", "Notas", i.notas]]
      .map(([n, r, v]) => el("label", {class: "cp"}, el("span", {class: "rot"}, r), el("input", {name: n, value: v || "", style: "width:11em"}))),
      el("button", {type: "submit", class: "mini"}, "salvar fascículo"),
      el("button", {type: "button", class: "mini", onclick: async () => {
        if (!confirm("Excluir este fascículo? Só é possível quando nenhuma manifestação estiver vinculada.")) return;
        try { await api(`/api/fasciculos/${i.id}`, {method: "DELETE"}); recarregar(); } catch (x) { aviso(x.message); }
      }}, "excluir fascículo"));
    detalhes.append(form);
    fi.append(li(el("span", {}, [i.volume && `v. ${i.volume}`, i.numero && `n. ${i.numero}`, i.data, i.titulo].filter(Boolean).join(" · ") || `Fascículo ${i.id}`),
      el("span", {class: "muted"}, `${i.manifestacoes} manifestação(ões)`), i.referencia ? el("span", {class: "meta"}, i.referencia) : "", detalhes));
  });
  if (!fi.children.length) fi.append(li(el("span", {class: "muted"}, "sem fascículos identificados; as referências textuais continuam preservadas")));
  const novoF = el("form", {class: "ed", onsubmit: async e => {
    e.preventDefault(); const data = Object.fromEntries(new FormData(novoF).entries());
    try { await api(`/api/periodicals/${f.id}/fasciculos`, {method: "POST", body: data}); aviso("fascículo cadastrado"); recarregar(); }
    catch (x) { aviso(x.message); }
  }}, el("strong", {class: "muted"}, "+ cadastrar fascículo"),
  ...[["volume", "Volume"], ["numero", "Número"], ["data", "Data"], ["titulo", "Título"], ["referencia", "Referência"], ["notas", "Notas"]]
    .map(([n, r]) => el("label", {class: "cp"}, el("span", {class: "rot"}, r), el("input", {name: n, style: "width:11em"}))),
  el("button", {type: "submit", class: "mini"}, "adicionar fascículo"));
  principal.append(bloco("Fascículos identificados", fi, novoF), bloco("Obras publicadas", ul), bloco("Quem colaborou", col));
}
function fEvento(f) {
  principal.append(el("div", {class: "campos"}, campo("Tipo", "tipo", f.tipo, {sel: ["", ...V.tipos_evento]}), campo("Quando", "ano", f.ano, {w: "10em", ph: "1922"})),
    bloco("Descrição", mdBloco(f.notas, v => salvar({notas: v}))));
  const p = el("ul", {class: "lista"}); f.participantes.forEach(a => p.append(li(link("author", a.id, a.nome))));
  if (!f.participantes.length) p.append(li(el("em", {class: "muted"}, "sem participantes registrados")));
  const o = el("ul", {class: "lista"}); f.obras.forEach(w => o.append(li(link("work", w.id, w.titulo))));
  principal.append(bloco("Participantes", p)); if (f.obras.length) principal.append(bloco("Obras apresentadas", o));
}
function fInstituicao(f) {
  principal.append(el("div", {class:"campos"}, campo("Tipo de instituição", "tipo", f.tipo, {sel:["", "universidade", "faculdade", "livraria", "editora", "academia", "sociedade", "órgão público", "outra"]}), campo("Fundação", "fundacao", f.fundacao, {ph:"ano ou data"}), campo("Extinção", "extincao", f.extincao, {ph:"se aplicável"}), campo("Local", "local", f.local, {ph:"cidade, país"})), bloco("Notas", mdBloco(f.notas, v=>salvar({notas:v}))));
}
function fMidia(f) {
  principal.append(bloco("Notas", mdBloco(f.notas, v => salvar({notas: v}))));
  const u = el("ul", {class: "lista"}); f.obras.forEach(w => u.append(li(link("work", w.id, w.titulo), el("span", {class: "muted"}, w.autor || ""))));
  if (!f.obras.length) u.append(li(el("em", {class: "muted"}, "nenhuma obra tem esta mídia")));
  const r = el("ul", {class: "lista"}); f.referenciada_em.forEach(w => r.append(li(link("work", w.id, w.titulo), el("span", {class: "muted"}, V.relacoes[w.tipo]?.direta || w.tipo))));
  principal.append(bloco("Obras nesta mídia", u)); if (f.referenciada_em.length) principal.append(bloco("Referências intermidiáticas a ela", r));
}

/* ---------------- reconhecimento e preenchimento ONLINE (opcional) — em todas as fichas ---------------- */
const ROTULO_CAMPO = {nascimento: "nascimento", morte: "morte", ano: "ano", issn: "ISSN", tipo: "tipo", ano_inicio: "início", ano_fim: "fim", notas: "notas"};
function blocoOnline(f) {
  const chave = TIPO + ":" + f.id, caixa = el("div");
  const btn = el("button", {class: "mini", onclick: async () => {
    const cfg = await api("/api/config");
    if (!cfg.online) { if (!confirm("O módulo online consulta Wikidata, Open Library e Crossref pela internet.\nSó o nome/título da ficha é enviado — nunca arquivos.\nNada é gravado sem a sua confirmação.\n\nLigar?")) return;
      await api("/api/config", {method: "POST", body: {online: true}}); }
    btn.disabled = true; btn.textContent = "consultando…";
    try { CARTOES[chave] = await api("/api/online/ficha", {method: "POST", body: {tipo: TIPO, id: f.id}}); pinta(); } catch (e) { aviso(e.message); }
    btn.disabled = false; btn.textContent = "🔎 pesquisar online";
  }}, "🔎 pesquisar online");
  function pinta() {
    caixa.innerHTML = ""; const cs = CARTOES[chave]; if (!cs) return;
    if (!cs.length) { caixa.append(el("p", {class: "muted"}, "nada encontrado online para este nome.")); return; }
    cs.forEach(c => {
      const ap = (txt, fn) => el("button", {class: "mini", onclick: async ev => { try { await fn(); ev.target.remove(); aviso("aplicado"); recarregar(); } catch (e) { aviso(e.message); } }}, txt);
      const btns = [];
      Object.entries(c.campos).forEach(([k, v]) => btns.push(ap(`${ROTULO_CAMPO[k] || k}: ${v.length > 40 ? v.slice(0, 38) + "…" : v}`, () => salvar({[k]: k === "notas" && f.notas ? f.notas + "\n\n" + v : v}))));
      c.lugares.forEach(l => btns.push(ap("＋ lugar: " + l.nome, () => api(`/api/entidades/${TIPO}/${f.id}/lugares`, {method: "POST", body: l}))));
      c.tags.forEach(t => btns.push(ap("＋ tag: " + t, () => api(`/api/entidades/${TIPO}/${f.id}/tags`, {method: "POST", body: {nome: t}}))));
      if (TIPO === "work" && Object.keys(c.edicao).length) btns.push(ap("＋ edição: " + Object.values(c.edicao).join(" · "), () => { const fd = new FormData(); Object.entries(c.edicao).forEach(([k, v]) => fd.append(k, v)); fd.append("fonte", c.fonte); return api(`/api/works/${f.id}/edicoes`, {method: "POST", form: fd}); }));
      caixa.append(el("div", {class: "cartao"}, el("strong", {}, c.titulo), el("span", {class: "muted"}, c.descricao ? " — " + c.descricao : ""), el("br"), el("small", {class: "muted"}, c.fonte), el("div", {class: "campos-ap"}, btns)));
    });
  }
  pinta();
  return bloco("Pesquisa online (opcional)", el("p", {class: "teoria", style: "margin:.1rem 0 .4rem"}, "traz sugestões com a fonte — você escolhe o que aplicar."), btn, caixa);
}

/* ---------------- lugares (opcionais), tags, galeria ---------------- */
function blocoLugares(f) {
  const box = el("div"), campoLugar = el("input", {placeholder: "+ lugar: país, estado ou cidade (Enter)", style: "width:21em"});
  const papel = el("select", {style: "font-size:.85rem"}, ["", "nascimento", "morte", "atuação", "publicação", "ocorrência"].map(p => new Option(p || "papel (opcional)", p)));
  f.lugares.forEach((l, i) => {
    const editor = el("div", {class: "editor-lugar", style: "display:none;flex-basis:100%;padding:.6rem;margin:.3rem 0;border:1px solid var(--rule);border-radius:8px"});
    const selectPai = el("select", {style: "min-width:15rem;max-width:100%"}, new Option("— sem lugar superior —", ""));
    const lat = el("input", {placeholder: "latitude", value: l.lat ?? "", style: "width:7rem"});
    const lon = el("input", {placeholder: "longitude", value: l.lon ?? "", style: "width:7rem"});
    const situacao = el("span", {class: "muted"});
    api("/api/lugares").then(lugares => {
      lugares.filter(p => p.id !== l.id).forEach(p => selectPai.append(new Option(p.caminho || p.nome, p.id)));
      selectPai.value = l.parent_id ?? "";
    }).catch(() => {});
    const salvar = el("button", {class: "mini", onclick: async () => {
      try { await api(`/api/lugares/${l.id}`, {method: "PATCH", body: {lat: lat.value || null, lon: lon.value || null, parent_id: selectPai.value || null}}); situacao.textContent = "salvo"; recarregar(); }
      catch (e) { situacao.textContent = e.message; }
    }}, "salvar lugar");
    editor.append(el("label", {}, "Lugar superior ", selectPai), el("div", {class: "linha", style: "margin-top:.4rem"}, lat, lon, salvar, situacao), el("p", {class: "teoria"}, "A hierarquia evita duplicar conceitos geográficos: cidade → estado → país. Coordenadas posicionam o lugar no mapa."));
    box.append(el("div", {class: "linha chip-lugar", style: "flex-wrap:wrap"}, i === 0 ? el("strong", {title: "lugar principal: fixa a ficha no mapa"}, "★") : el("button", {class: "x", title: "tornar principal", onclick: async () => {
        await api(`/api/entidades/${TIPO}/${f.id}/lugares/${l.id}/principal?papel=${encodeURIComponent(l.papel || "")}`, {method: "POST"}); recarregar(); }}, "☆"),
      el("span", {}, l.nome), el("span", {class: "muted"}, [l.caminho && l.caminho !== l.nome ? l.caminho : l.contexto, l.papel].filter(Boolean).join(" · ")),
      l.lat == null || l.lon == null ? el("span", {class: "muted", title: "sem coordenada: posicione no mapa"}, "· sem coordenadas") : "",
      el("button", {class: "x", title: "editar hierarquia e coordenadas", onclick: () => { editor.style.display = editor.style.display === "none" ? "block" : "none"; }}, "✎"),
      el("button", {class: "x", title: "desvincular lugar desta ficha", onclick: async () => { await api(`/api/entidades/${TIPO}/${f.id}/lugares/${l.id}?papel=${encodeURIComponent(l.papel || "")}`, {method: "DELETE"}); recarregar(); }}, "×")), editor);
  });
  const adicionar = async lugar => { try { await api(`/api/entidades/${TIPO}/${f.id}/lugares`, {method: "POST", body: {...lugar, papel: papel.value || null}}); recarregar(); } catch (e) { aviso(e.message); } };
  const obrig = {periodical: "o lugar de publicação posiciona o periódico no mapa", event: "o lugar do evento o posiciona no mapa"}[TIPO];
  const dica = obrig || "opcional: o primeiro (★) posiciona a ficha no mapa; os demais são informativos. Hierarquias geográficas podem ser editadas para ligar cidade, estado e país.";
  return bloco(TIPO === "author" ? "Nacionalidade e lugares (opcional)" : "Lugar", box, el("div", {style: "display:flex;gap:.4rem;flex-wrap:wrap;align-items:center"}, buscaLugar(campoLugar, {onPick: adicionar}), papel),
    el("p", {class: "teoria", style: "margin:.3rem 0"}, dica));
}
function blocoTags(f) {
  const box = el("div"), novo = el("input", {placeholder: "+ tag (Enter)", list: "dl-t", style: "width:11em"}), dl = el("datalist", {id: "dl-t"});
  api("/api/tags").then(ts => ts.forEach(t => dl.append(new Option(t.nome))));
  f.tags.forEach(t => box.append(el("span", {class: "chip"}, t.nome, el("button", {class: "x", onclick: async () => { await api(`/api/entidades/${TIPO}/${f.id}/tags/${t.id}`, {method: "DELETE"}); recarregar(); }}, "×"))));
  novo.onkeydown = async e => { if (e.key === "Enter" && novo.value.trim()) { await api(`/api/entidades/${TIPO}/${f.id}/tags`, {method: "POST", body: {nome: novo.value}}); recarregar(); } };
  return bloco("Tags", box, novo, dl, el("p", {class: "teoria", style: "margin:.3rem 0"}, "tags colorem e filtram o mapa e formam «platôs» no grafo."));
}
function blocoGaleria(f) {
  const g = el("div", {class: "galeria"});
  f.assets.forEach(a => g.append(el("figure", {}, el("a", {href: urlArquivo(a.caminho), target: "_blank"}, el("img", {src: urlArquivo(a.caminho)})),
    el("figcaption", {}, a.legenda || "", el("button", {class: "x", onclick: async () => { await api(`/api/assets/${a.id}`, {method: "DELETE"}); recarregar(); }}, "×")))));
  const arq = el("input", {type: "file", accept: "image/*", style: "display:none"}), leg = el("input", {placeholder: "legenda", style: "width:12em"});
  arq.onchange = async () => { const fd = new FormData(); fd.append("arquivo", arq.files[0]); fd.append("legenda", leg.value);
    await api(`/api/entidades/${TIPO}/${f.id}/assets`, {method: "POST", form: fd}); recarregar(); };
  return bloco("Imagens", g, el("div", {style: "margin-top:.5rem"}, leg, " ", el("button", {class: "mini", onclick: () => arq.click()}, "+ imagem"), arq));
}
