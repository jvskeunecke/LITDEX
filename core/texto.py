"""Utilitários de texto."""
import re, unicodedata

def sem_acento(s):
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c))

def normalizar(s):
    s = sem_acento(s).lower()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s)).strip()

def limpar(s):
    return re.sub(r"\s+", " ", s or "").strip()

def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", sem_acento(s or "").lower()).strip("-") or "x"
