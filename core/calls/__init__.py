"""Real sales calls the learner uploads: read the transcript, find the rep, profile the prospect.

Reading is pure logic, no AI and no I/O beyond config/calls.yaml: the same transcript always reads the same way.
The one AI step is audio.py, and only for a recording: it labels who said each piece, and its output is plain text
the learner checks before it is read like any transcript.
It knows nothing about sell mode; the route turns a profile into a sell-mode buyer.

  transcript.py  text -> speaker turns (one parser per export format; add a format = add a parser)
  roles.py       which speaker is the rep, which is the prospect
  profile.py     the prospect's profile (needs, pains, budget, objections, difficulty) with evidence
  reader.py      the one entry point: read_call(text, rep=None) -> CallReading
  audio.py       a recording's timed segments -> "[m:ss] Speaker A: ..." text (AI labels who spoke)
"""
