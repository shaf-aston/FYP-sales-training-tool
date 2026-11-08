"""What one prospect reply was heard as, before anything is said back: one `Verdict` per turn."""

import re
from dataclasses import dataclass, replace
from itertools import dropwhile

from core.buy_mode.script_engine.engine import (
    asked_line,
    hear_ahead,
    question_of,
    questions_of,
    ready_open,
)
from core.buy_mode.script_engine.hear.reply import Part, Reader, break_pattern, clauses
from core.buy_mode.script_engine.method import ANY
from core.infra.utils import tokenize


@dataclass(frozen=True)
class Verdict:
    kind: str           # nudge | says_nothing | ready | sense | objection | fact | question | answer
    name: str = ""      # which sense, objection or fact
    text: str = ""      # what they meant (reply.py): no nudge on its end, no hedge; an answer's content only
    asking: bool = False
    ahead: object = None  # the state with answers to later steps kept ("I want 5k a month"), else None
    side: str = ""      # an answer with a question beside it: how the question was heard ("fact:price", "question")
    asked: str = ""     # that question's words

    @property
    def heard_as(self):
        heard = f"{self.kind}:{self.name}" if self.name else self.kind
        return f"{heard}+{self.side}" if self.side else heard


def answer_labels(step):
    """The step's labelled answers: {label: [example, ...]}; empty when any reply is its answer."""
    return {r.label: list(r.examples) for r in step.listen if r.examples}


class Ear:
    """Hears a reply against the call so far, from its parts (reply.py). Order matters and lives here only: a
    nudge on its own; an answer with a question beside it (both kept); then a shrug, an interruption that
    clearly beats an answer, a question the step's own answers don't cover, else an answer."""

    def __init__(self, cfg, method, offer, sense, listener, shrugs, judge):
        """`judge(reply, {name: [examples]})`: the AI's pick of one name, or VAGUE."""
        self.cfg, self.method, self.offer, self.sense = cfg, method, offer, sense
        self._listener, self._shrugs, self._judge = listener, shrugs, judge
        self.reader = Reader(cfg, sense.nudges, shrugs.hedges)
        self._breaks = break_pattern(cfg)
        self._captures = {}  # slot: the first step that saves it
        for s in method.steps.values():
            if s.capture:
                self._captures.setdefault(s.capture, s)

    def hear(self, text, state, opened):
        step = self.method.steps[state.step]
        reply = self._unecho(self.reader.read(text), state).settle(lambda part: self._rises(part, step))
        if reply.nudged and not tokenize(reply.unnudged):
            return Verdict("nudge", text=text)  # "what's next?": no answer
        fixed, rest = self._correction(text, state)
        if fixed:
            fixed_state = replace(state, slots={**state.slots, fixed.name: fixed.text})
            then = self.hear(rest, fixed_state, opened) if rest else None
            if then and then.kind == "answer":  # "I meant 3k, and a year": the 3k fixed, "and a year" this step's answer
                return replace(then, ahead=then.ahead or fixed_state)
            return fixed
        asking = bool(reply.asked)
        if self._what_alone(text) or self._word_back(text, state) or (asking and not reply.said and self._asked_back(reply.asked, state)):
            return Verdict("sense", "clarify", text, asking)
        if asking and reply.said:
            both = self._with_side(reply, step, state, opened)
            if both:
                return both
        text = reply.said if reply.said and not asking else reply.meant  # "dunno, a year?" -> "a year"
        nothing = self._shrugs.blank(text) or (not self._yes_or_no(state) and self._shrugs.says_nothing(text, step, asking))
        if not state.waiting and nothing and not self._ready(text, state):  # "yes I'm in" is a shrug's words, but it says they're in
            return Verdict("says_nothing", text=text, asking=asking)  # an answer only: never an interruption
        ahead, text = (None, text) if asking else self._ahead(text, step, state)  # "do I need 5k?" is not their goal
        kind, name = (None, "") if self._shrugs.plain_no(text) else self._interrupt(text, step, ahead or state, opened, asking)
        if kind == "objection" and not opened and not asking:
            beside = self._beside_worry(text, step, state, name)
            if beside:
                return beside
        if kind == "sense" and not asking:
            beside = self._beside_sense(text, step, state, name)
            if beside:
                return beside
            if self._over(text, name):
                return Verdict("says_nothing", text=text)  # "sorry, was driving": back, so the step is asked again
        if kind == "sense" and self._paused_again(name, state):
            return Verdict("says_nothing", asking=asking)  # no words to ask about: never "What do you mean by brb?"
        if kind == "sense" and not asking and self._said_again(name, state):
            return Verdict("says_nothing")  # "ok, thank you" once "You're welcome." was said: heard as "ok"
        if kind:
            return Verdict(kind, name, text, asking, ahead)
        if asking and not self._answers(text, step):
            return Verdict("question", text=text, asking=asking, ahead=ahead)
        return Verdict("answer", text=text if asking else self._unbroken(text, step, state), asking=asking, ahead=ahead)

    def _unecho(self, reply, state):
        """The question said back before their answer ("how long? about 2 years", "achieve? quit my job", "what
        do I want? more money") is talk, not a question: it never picks an answer ("how long?" is near "not
        long") and is never asked about. With an answer after it, it needs fewer of the question's words
        (`asked_back_share_with_answer`: "what am I hoping to achieve? more money"). Said back alone, it still
        asks for the question put another way."""
        parts = list(reply.parts)
        for i, part in enumerate(parts):
            if part.act not in ("asks", "rise") or not (self._word_back(part.text, state) or self._asked_back(part.text, state, "asked_back_share_with_answer")):
                break
            parts[i] = Part(part.text, "tag")
        if not any(p.act in ("said", "rise", "asks") for p in parts):
            return reply  # all of it said back: "how long?" alone
        return replace(reply, parts=tuple(parts))

    def _ahead(self, text, step, state):
        """(the state with answers to later steps kept, else None; this step's words). Each part is heard too:
        "more money, about 2k a month" keeps the 2k for the income step, and a part that answers only a later
        step is left out of this step's answer, so "more money" alone is said back (round 27 callers: "about
        2k a month" was said back, and the income was asked again)."""
        ahead = hear_ahead(self.method, state, text)
        parts = clauses(text, self._breaks)
        kept = []
        for part in parts if len(parts) > 1 else ():
            alone = hear_ahead(self.method, state, part)
            if alone is state:
                kept.append(part)
            else:
                ahead = replace(ahead, slots={**alone.slots, **ahead.slots})
        rest = ", ".join(kept)
        if kept and len(kept) < len(parts) and self._answers_step(rest, step, state):
            text = rest
        return (None if ahead is state else ahead), text

    def _said_again(self, name, state):
        """A remark marked `once`, said again once its reply was said this call ("ok, thank you" after "You're
        welcome."): nothing new to answer. Round 27 callers: a second thank-you got "Like I said a moment ago."
        on its own, and "You're welcome." every turn."""
        said = self.sense.interruptions[name]
        return said.once and said.reply in state.spoken

    def _paused_again(self, name, state):
        """A third pause in a row (the last line was `wait_again`, said only to a second one) says nothing: the
        step is asked again, which spends an ask, so a call never waits forever ("sorry" 20 times did)."""
        wait_again = self.sense.wait_again
        return bool(wait_again) and self.sense.interruptions[name].after == "wait" and state.last == wait_again

    def _what_alone(self, text):
        """A reply of only "what?" (`asked_back_what`, maybe with `what_alone_with`: "sorry, what?") wants the
        question put another way: it is near "say that again" and "why do you ask" alike, so no score settles it."""
        words = set(tokenize(text))
        return bool(words & set(self.cfg["asked_back_what"])) and words <= {*self.cfg["asked_back_what"], *self.cfg["what_alone_with"]}

    def _word_back(self, text, state):
        """A word or two lifted from the question just asked, said back with a "?" ("a month?" to "How much would
        you need to be making each month...?", "achieve?") checks what it means: put it another way. Not when the
        question offers a choice ("Credit or debit?": "debit?" picks one) or the reply holds a question word ("why?")."""
        if not text.rstrip().endswith("?"):
            return False
        asked = set(tokenize(" ".join(q for line in asked_line(self.method, state) for q in questions_of(line))))
        words = [w for w in tokenize(text) if w not in self.cfg["stop_words"]]
        if "or" in asked or not 0 < len(words) <= self.cfg["word_back_words"] or set(words) & set(self.cfg["question_words"]):
            return False
        return all(w in asked or w + "s" in asked or (w.endswith("s") and w[:-1] in asked) for w in words)

    def _asked_back(self, text, state, share="asked_back_share"):
        """Their reply is the question just asked, said back about themselves ("what do I want to achieve?" to
        "What do you want to specifically achieve...?"): they want it put another way. Their I-words are turned
        into you-words (`asked_back`), and `asked_back_share` of their words must be in its questions, not the talk
        around them ("can we do option 2?" picks from the talk: it is not the question said back). A you-word
        of theirs (`asked_back_you`) asks about us ("what do you do?"); one word ("why?") is too few to tell.
        A "what?" tacked on (`asked_back_what`: "how long what?") is not counted unless the question has it too."""
        swap = self.cfg["asked_back"]
        asked = set(tokenize(" ".join(q for line in asked_line(self.method, state) for q in questions_of(line))))
        words = [w for w in tokenize(text) if w in asked or w not in self.cfg["asked_back_what"]]
        if len(words) < self.cfg["asked_back_min_words"] or any(w in self.cfg["asked_back_you"] for w in words):
            return False
        return sum(swap.get(w, w) in asked for w in words) >= self.cfg[share] * len(words)

    def _rises(self, part, step):
        """A part ending in "?" that isn't phrased as a question is the answer said with a rise when it is short
        and has the step's shape ("dunno, a year?" to "how long?") or is about them ("my job?": nothing to ask the
        seller), it opens with a reason ("because money is nice?"), or it is only filler words ("ok?"); else it
        asks ("what's this going to cost me?")."""
        words = tokenize(part)
        if self._reason(part) or self._shrugs.filler(part):  # whole calls: "ok?" got "I'll find out"
            return True
        if len(words) > self.cfg["rise_answer_words"]:
            return False
        return words[0] in self.cfg["prospect_pronouns"] or bool(step.needs) and self.shaped(part, step)  # round 28: "my job?" got "I'll find out"

    def _reason(self, text):
        """The reply opens with a reason ("because...", "cos..."): it gives one, it does not ask or object."""
        words = tokenize(text)
        return bool(words) and words[0] in self.cfg["reason_starts"]

    def _with_side(self, reply, step, state, opened):
        """Content that answers the step, beside a question a one-line reply covers ("i guess 3 years, what
        about you?", "nothing, why do you ask?"): the answer is kept and the question answered in front of the
        next line. A worry in the content leads instead ("5k? that's a lot"), whatever is asked beside it. None, so
        the question leads as it always did, when the question is a worry after the price, "say that again?", a
        shortcut, or itself one of the step's answers beside a "no", after a pause, or when the content is no
        answer. A question that picks one of the step's answers beside a plain one ("yeah I'm in, how do I
        pay?") is that answer, heard alone."""
        if state.waiting:
            return None  # "ok I'm back, where were we" after a pause
        within, about = self._interrupt(reply.said, step, state, opened, False)
        if within == "objection":  # a worry leads, whatever is asked beside it: "5k? that's a lot" is the money,
            return Verdict(within, about, reply.said)  # "I can't afford it, how do I pay?" is not ready to pay
        picked = self._chooses(reply.asked, step)
        if picked:  # "yeah I'm in, how do I pay?": the question is the answer, heard alone, unless the content
            # takes it back ("no, credit?": torn, judged as before) or is a sense ("brb, how do I pay?")
            if within:
                return None
            if self._takes_back(reply.said, picked, step):  # "not yet, how do I pay?": the yes is taken back, so
                kind, name = self._interrupt(reply.meant, step, state, opened, True, answers=False)  # it asks
                return Verdict(kind, name, reply.meant, asking=True) if kind == "fact" else None
            return Verdict("answer", text=reply.asked, asking=True)
        kind, name = self._interrupt(reply.asked, step, state, opened, True)
        if (kind in ("ready", "answer") or (kind == "objection" and opened)
                or (kind == "sense" and not self.sense.interruptions[name].with_answer)):  # "say that again?" leads
            return None
        if within:  # the content is a sense, no answer ("shut up"): it leads only beside a plain question
            return None if kind else Verdict(within, about, reply.said)  # "shut up, what's the price?" wants the price
        if not self._answers_step(reply.said, step, state):
            return None
        ahead = hear_ahead(self.method, state, reply.said)
        return Verdict("answer", text=reply.said, asking=True, ahead=None if ahead is state else ahead,
                       side=f"{kind}:{name}" if kind else "question", asked=reply.asked)

    def _correction(self, text, state):
        """(verdict, rest): their last answer fixed a turn later ("sorry I meant 3k not 2k"): the new words, for
        the slot it was saved in, when they have that step's shape, and what came after them for this step
        ("I meant 3k, and a year" -> "and a year"). (None, "") otherwise: "I meant what I said" fixes nothing."""
        opening = re.match(self.cfg["corrects"], text, re.IGNORECASE)
        if not opening or not state.slots:
            return None, ""
        slot = next(reversed(state.slots))
        value, _, rest = re.sub(self.cfg["corrects_drop"], "", text[opening.end():], flags=re.IGNORECASE).partition(", ")
        value = value.strip(" .!,")
        step = self._captures.get(slot)
        if not value or not step or step.id == state.step or (step.needs and not re.search(step.needs, value, re.IGNORECASE)):
            return None, ""
        return Verdict("corrects", slot, value), rest.strip(" .!,")

    def _beside_worry(self, text, step, state, name):
        """An answer, then a worry before the price ("make money online, but I've been burnt before"): the
        answer is kept and the worry's early line goes in front of the next question, as for a worry asked
        beside an answer. None when the first part is no answer, or the worry is not in the rest alone."""
        head, *rest = clauses(text, self._breaks)
        rest = ", ".join(rest)  # without the "but" that joins them: the worry heard on its own words
        if not rest or self._interrupt(head, step, state, False, False)[0]:
            return None
        if self._interrupt(rest, step, state, False, False) != ("objection", name):
            return None
        if not self._answers_step(head, step, state):
            return None
        ahead = hear_ahead(self.method, state, head)
        return Verdict("answer", text=head, ahead=None if ahead is state else ahead, side=f"objection:{name}")

    def _beside_sense(self, text, step, state, name):
        """A remark that is a sense able to sit beside an answer (`with_answer`), with an answer in the other parts
        ("oh great, another sales call. more money I guess"): the answer is kept and the sense's line goes in
        front of the next question, as when it is asked beside one. A pause or goodbye said in the past sits
        beside one too, with no line ("sorry kids were shouting, 2k": they are back). The answer is the parts
        after the remark ("oh great" before it is talk), else those before it. None when no part alone is that
        sense, or the rest is no answer."""
        said = self.sense.interruptions[name]
        parts = clauses(text, self._breaks)
        for i, part in enumerate(parts):
            if self._interrupt(part, step, state, False, False) != ("sense", name):
                continue
            if not said.with_answer and not self._over(part, name):
                return None
            rest = ", ".join(parts[i + 1:] or parts[:i])
            if not rest or self._interrupt(rest, step, state, False, False)[0] or not self._answers_step(rest, step, state):
                return None
            ahead = hear_ahead(self.method, state, rest)
            side = "" if not said.with_answer or self._said_again(name, state) else f"sense:{name}"  # "You're welcome." once a call
            return Verdict("answer", text=rest, ahead=None if ahead is state else ahead, side=side)
        return None

    def _unbroken(self, text, step, state):
        """The answer without a part that alone is a break already over ("sorry I was in a meeting, more money":
        more money). The break leads or ends the reply: the fewest parts that are one ("sorry, I was out" is two), then
        any part beside it that answers nothing ("more money, sorry, I was out"). Round 34 callers: the answer won,
        so the whole was saved and said back."""
        parts = clauses(text, self._breaks)
        if not set(self.cfg["sense_over_words"]) & set(tokenize(text)):
            return text
        for k in range(1, len(parts)):
            for cut, rest, edge in ((parts[:k], parts[k:], 0), (parts[-k:], parts[:-k], -1)):
                if self._ended(", ".join(cut), step, state):
                    while len(rest) > 1 and not self._answers_step(rest[edge], step, state):
                        rest = rest[1:] if edge == 0 else rest[:-1]
                    return ", ".join(rest)
        return text

    def _ended(self, part, step, state):
        """The part alone is a pause or goodbye said in the past."""
        kind, name = self._interrupt(part, step, state, False, False)
        return kind == "sense" and self._over(part, name)

    def _over(self, text, name):
        """A pause or goodbye said in the past ("sorry, was driving", "the kids were shouting"): the break is
        over and they are back, so it is talk, never "take your time" or the call left (round 33 callers:
        "sorry was driving, 2k" ended the call). `sense_over_after`: the senses it can be; `sense_over_words`:
        the words that put it in the past."""
        return (self.sense.interruptions[name].after in self.cfg["sense_over_after"]
                and any(w in self.cfg["sense_over_words"] for w in tokenize(text)))

    def _chooses(self, question, step):
        """The one label of the step's answers the question surely picks on its own ("how do I pay?" at the
        close), else "": not torn between two ("how much is it anyway" is near two goal levels and picks neither)."""
        labels = answer_labels(step)
        found = self._listener.match(question, labels) if labels else None
        sure = found and found.label and not found.close and found.score >= self.cfg["question_answer_min_score"]
        return found.label if sure and self._names(question, labels[found.label]) else ""

    def _names(self, question, examples):
        """The question names a word of the answer it is near ("can I use paypal?": paypal), or only small words
        ("which one?"). One with words of its own the answer never uses asks about something else (round 34
        callers: "which is better?", 0.81 to "whichever is easier", got "Welcome aboard")."""
        small = {*self.cfg["stop_words"], *self.cfg["question_words"], *self.cfg["closed_question_starts"],
                 *self.cfg["question_subjects"]}
        own = {w for w in tokenize(question) if w not in small}
        return not own or bool(own & {w for e in examples for w in tokenize(e)})

    def _takes_back(self, said, label, step):
        """The content is another of the step's answers, one that says no (`takes_back`: "no", "not yet"):
        beside "how do I pay?" it takes the question back. "yeah I'm in" doesn't."""
        found = self._listener.match(said, answer_labels(step))
        if not (found and found.label) or found.label == label:
            return False
        return next(r for r in step.listen if r.label == found.label).like in self.cfg["takes_back"]

    def _answers_step(self, text, step, state):
        """`text` is an answer the step keeps: its shape, not a shrug, and one of its answers or any reply."""
        if not self.shaped(text, step):
            return False
        if self._shrugs.says_nothing(text, step, False) and not self._yes_or_no(state):
            return False
        labels = answer_labels(step)
        if labels and self._listener.answer(text, labels, list(self.sense.unclear),
                                            {r.label: r.min_score for r in step.listen if r.label}).label:
            return True
        return any(r.label == ANY for r in step.listen)

    @staticmethod
    def shaped(text, step):
        """The reply has the shape the step's answer needs (`needs`: a figure, a span of time), or it needs none."""
        return not step.needs or bool(re.search(step.needs, text, re.IGNORECASE))

    def _yes_or_no(self, state):
        """The step was last asked as a yes-or-no question ("Is there anything you've tried?"): "yes" answers it.
        Any part of it (between commas) opening with a helper verb, past lead-ins ("so", "and", "okay"): "So if
        your partner isn't on board, would you still go ahead?", "Okay, And do you want...", "..., aren't you?"."""
        leads = self.cfg["question_lead_words"]
        for part in question_of(asked_line(self.method, state)[0]).split(","):
            words = list(dropwhile(leads.__contains__, tokenize(part)))
            if words and words[0] in self.cfg["closed_question_starts"]:
                return True
        return False

    def _open(self, step_id):
        """{name: Ready} for the shortcuts open at this step."""
        return {k: r for k, r in self.method.shortcuts.items() if ready_open(self.method, step_id, r)}

    def _ready(self, text, state):
        """The reply takes a shortcut open at this step ("yes I'm in", "credit")."""
        return any(self._listener.match(text, {"ready": list(r.examples)}, by_clause=False).score >= r.min_score
                   for r in self._open(state.step).values())

    def _interrupt(self, text, step, state, opened, asking, answers=True):
        """An everyday interruption, product question or objection - only when it clearly beats
        reading the reply as an answer to the step's own question, like a human closer would. `answers`
        False: the step's answers are not in the running (one was taken back beside it)."""
        # "not sure" alone is not knowing, not asking what we meant: no sense that rephrases hears a hedge, and
        # "let me think" is thinking out loud, not a pause: no sense that waits does (whole calls: "take your time" forever)
        unsure = 0.0 if asking else self._shrugs.unsure(text)
        hedge = unsure >= self.sense.unclear_min_score
        senses = {k: i for k, i in self.sense.interruptions.items()
                  if (state.waiting or not i.after_wait) and not (hedge and i.after in ("rephrase", "wait"))
                  and (asking or not i.only_asked)}
        labels = {f"sense:{k}": i.examples for k, i in senses.items()}
        floors = {f"sense:{k}": i.min_score for k, i in senses.items()}  # lowest score a label counts at
        if asking:
            labels.update({f"fact:{k}": f.examples for k, f in self.offer.facts.items()})
        objections = self.method.objections.items()
        if not opened and not asking and (step.doubts_answer or self._reason(text)):
            objections = ()  # "money's tight" answers "what holds you back", "because money is tight" any step;
            # "is this a scam?" still asks
        elif not opened and asking:
            objections = [(k, o) for k, o in objections if o.early]  # "is this a scam?" gets an honest early line
        if not opened and not asking:  # parked once, said again: an answer. Asked again ("how do I know this
            objections = [(k, o) for k, o in objections if k not in state.parked]  # isn't a scam?"): still the worry
        if hedge and objections:  # "I don't know" (0.74 to "I don't trust this") is not knowing, not a worry; one
            # nearer a worry than not knowing is the worry ("let me think about it": 1.0 to it, 0.96 to "let me think")
            worry = self._listener.match(text, {k: o.heard(opened) for k, o in objections}, by_clause=False)
            objections = [(k, o) for k, o in objections if k == worry.label and worry.score > unsure]
        handled = set()  # a worry already being handled, or one the step asks about ("the money?"), answers the step.
        if opened:  # Past its talk, a step that keeps any reply would keep it as their answer: it is the worry again
            # (whole calls: "he decides the money stuff" to "What makes you say that?" was their reason, then payment)
            talking = state.step in self.method.talks or not any(r.label == ANY for r in step.listen)
            handled = {k for k, _ in objections if (k in state.raised and talking) or k in {r.label for r in step.listen}}
        labels.update({f"objection:{k}": o.heard(opened) for k, o in objections})
        objections = [(k, o) for k, o in objections if k not in handled]
        if not opened and not asking:  # "money", "scared", "risk" before the price are answers, not objections
            floors.update({f"objection:{k}": self.cfg["early_objection_min_score"] for k, _ in objections})
        for k, r in self._open(state.step).items():
            labels[f"ready:{k}"], floors[f"ready:{k}"] = r.examples, r.min_score
        # the catch-all keeps any reply only if it has the step's shape: "I don't have time for this" to "how
        # long?" can't be the answer, so nothing has to out-score it there (live: the frustration went unheard)
        takes_any = any(r.label == ANY for r in step.listen) and self.shaped(text, step)
        won = self._listener.interruption(text, labels, answer_labels(step) if answers else {}, takes_any, asking, floors)
        if won and won.split(":", 1)[1] in handled:  # still kept as a label so a near worry can't win in its place
            # live: "I don't have 5k lying around" in the money talk was heard as "think it over". Asked again
            # ("how do I know this isn't a scam?" in the scam talk) it answers the step too, never "I'll find out"
            won = "answer:" if asking else None
        if not won and not opened and not asking:
            won = self._judged_objection(text, step, dict(objections))
        return tuple(won.split(":", 1)) if won else (None, "")

    def _judged_objection(self, text, step, objections):
        """An objection that scored in the grey band before the price ("10k seems like a lot", 0.81): too close
        to the step's answers for the embedder alone, so the AI picks objection or answer. AI down = answer."""
        found = self._listener.match(text, {k: o.heard(False) for k, o in objections.items()})
        if not found.label or found.score < self.cfg["early_objection_judge_score"]:
            return None
        answers = [f"answering '{question_of(step.say_plain or step.say)}'"]  # the question asked, so the AI judges in context
        examples = objections[found.label].heard(False)
        nearest = self._listener.match(text, {e: [e] for e in examples}).candidates  # the AI sees the closest ones
        pick = self._judge(text, {f"{found.label} objection": list(nearest) or examples, "answer": answers})
        return f"objection:{found.label}" if pick == f"{found.label} objection" else None

    def _answers(self, text, step):
        """The reply matches one of the step's own answers, even with a question in it ("yeah makes
        sense, what's next?" at the temp check), only when sure: "what happens to the card?" asks about the
        card, it doesn't choose it. Two answers too close to call are judged as usual."""
        labels = answer_labels(step)
        if not labels or self._listener.answer_score(text, labels, asking=True) <= 0:
            return False
        found = self._listener.match(text, labels)
        return not found.label or found.close or self._names(text, labels[found.label])
