#!/usr/bin/env python3
"""Gera PDFs de teste a partir de textos de domínio público do Projeto Gutenberg (via GITenberg, no GitHub).
Uso: python tools/gerar_pdfs.py <pasta_de_saida>
Preserva o cabeçalho do Gutenberg e a folha de rosto ORIGINAL da edição — é o que o scanner lê.
Requer: pip install reportlab   e acesso a codeload.github.com."""
import io, re, sys, urllib.request, zipfile
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer

LIVROS = {   # nome do arquivo -> (repositório GITenberg, arquivo de texto)
    "dom_casmurro.pdf": ("Dom-Casmurro_55752", "55752-8.txt"),
    "iracema.pdf":      ("Iracema-com-uma-noticia-biographica-do-auctor_67740", "67740-0.txt"),
    "o_cortico.pdf":    ("O-Cortico_69187", "69187-0.txt"),
}
FONTES = ["/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", "C:/Windows/Fonts/times.ttf", "C:/Windows/Fonts/georgia.ttf",
          "/Library/Fonts/Times New Roman.ttf", "/System/Library/Fonts/Supplemental/Times New Roman.ttf"]      # primeira que existir

def baixar(repo, arq):
    url = f"https://codeload.github.com/GITenberg/{repo}/zip/refs/heads/master"
    with urllib.request.urlopen(url, timeout=60) as r: z = zipfile.ZipFile(io.BytesIO(r.read()))
    b = z.read(f"{repo}-master/{arq}")
    try: return b.decode("utf-8").lstrip("\ufeff")
    except UnicodeDecodeError: return b.decode("latin-1")

def gerar(texto, destino):
    fonte = next((f for f in FONTES if Path(f).exists()), None)
    if not fonte: sys.exit("Nenhuma fonte serifada encontrada: edite FONTES em tools/gerar_pdfs.py")
    pdfmetrics.registerFont(TTFont("Serif", fonte))
    ini = texto.find("*** START"); fim = texto.find("*** END")
    cabeca = texto[:texto.index("\n", ini)] if ini > 0 else ""
    corpo = texto[texto.index("\n", ini):fim] if ini > 0 and fim > 0 else texto
    texto = (cabeca + "\n" + corpo).replace("\r", "")
    estilo = ParagraphStyle("p", fontName="Serif", fontSize=9.3, leading=12.6, spaceAfter=5.5, alignment=0)
    doc = BaseDocTemplate(str(destino), pagesize=A5, leftMargin=1.7*cm, rightMargin=1.7*cm, topMargin=1.6*cm, bottomMargin=1.7*cm, author="", title="")
    quadro = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="q")
    def rodape(c, d):
        c.setFont("Serif", 7.5); c.drawCentredString(A5[0] / 2, 0.9*cm, str(d.page))
    doc.addPageTemplates([PageTemplate(id="p", frames=[quadro], onPage=rodape)])
    historia = []
    for bloco in re.split(r"\n\s*\n", texto):
        linhas = [l.strip() for l in bloco.split("\n") if l.strip()]
        if not linhas: continue
        historia.append(Paragraph(escape(" ".join(linhas)), estilo))
    doc.build(historia)

if __name__ == "__main__":
    saida = Path(sys.argv[1]); saida.mkdir(parents=True, exist_ok=True)
    for nome, (repo, arq) in LIVROS.items():
        gerar(baixar(repo, arq), saida / nome); print(nome, round((saida / nome).stat().st_size / 1e6, 2), "MB")
