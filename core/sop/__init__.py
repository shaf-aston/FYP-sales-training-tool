"""A team's sales SOP (standard operating procedure): read it, check it covers what a good call needs, and check a
call against it.

No AI: meaning is matched with the local embedding model, passed in as `embed(texts) -> vectors` so this package
never imports a mode (the route hands it the shared embedder; the maths is core/infra/similarity.py). Nothing is stored.

  document.py   file bytes (txt, md, docx, pdf) -> blocks: headings and lines
  outline.py    blocks -> stages and steps
  checklist.py  does the SOP cover each element of a good call (config/sop.yaml)?
  adherence.py  which SOP steps a call's rep lines carried out, and in what order
  spoken.py     a step as the rep says it ("Ask what they want" -> "What do you want?"), for buy mode's rep's words
"""
