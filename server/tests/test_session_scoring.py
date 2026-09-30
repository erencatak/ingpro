import asyncio

import numpy as np
import pytest

from ingpro.agents.provider import TokenUsage
from ingpro.brain import usage
from ingpro.brain.service import BrainService
from ingpro.brain.store import Store
from ingpro.voice.session import VoiceSession

from test_brain import Clock, course


class FakeWS:
    def __init__(self):
        self.sent = []

    async def send_json(self, data):
        self.sent.append(data)

    async def send_bytes(self, data):
        pass


class FakeChat:
    def __init__(self):
        self.usage = TokenUsage()

    async def start(self): ...
    async def interrupt(self): ...
    async def close(self): ...

    async def send(self, text):
        yield "Nice"  # no sentence boundary, no speech needed


class FakeTTS:
    def synthesize(self, text, lang, speed):
        return np.zeros(0, dtype=np.float32)


class FakeJudge:
    def __init__(self, judgement=None, boom=False):
        self.judgement, self.boom, self.calls = judgement, boom, 0

    async def evaluate(self, topic, text):
        self.calls += 1
        if self.boom:
            raise RuntimeError("judge down")
        return self.judgement, TokenUsage()


def words(prob):
    return [{"text": "I", "start": 0, "end": 1, "prob": prob}, {"text": "agree", "start": 1, "end": 2, "prob": prob}]


def make(judge, topic=True):
    store = Store(":memory:")
    brain = BrainService(store, None, Clock())
    c = course()
    c["topics"][0]["band"] = "A1-A2"
    brain.seed(c)
    ws = FakeWS()
    unit = c["topics"][0] if topic else None
    session = VoiceSession(ws, FakeChat(), None, FakeTTS(), asyncio.Lock(), asyncio.Lock(), 0.9, None,
                           topic=unit, brain=brain, judge=judge if topic else None)
    return session, ws, brain


async def turn(session, text, lang="en", w=None):
    await session._start_turn(text, lang, w, 0)
    await asyncio.gather(session._reply_task, *session._scoring)


def usage_events(ws):
    return [m for m in ws.sent if m["type"] == "usage"]


GOOD = usage.Judgement(True, "correct", (usage.Word("garden", "A1"),), "iyi")


@pytest.mark.asyncio
async def test_a_spoken_correct_sentence_earns_points_beside_the_reply():
    session, ws, brain = make(FakeJudge(GOOD))
    await turn(session, "He is reluctant to leave", w=words(0.95))
    (u,) = usage_events(ws)
    assert (u["valid"], u["rule"], u["points"], u["unit_points"]) == (True, 1, 3, 3)
    assert any(m["type"] == "assistant_end" for m in ws.sent)  # the reply was not blocked


@pytest.mark.asyncio
async def test_typed_messages_unclear_speech_and_turkish_never_reach_the_judge():
    judge = FakeJudge(GOOD)
    session, ws, brain = make(judge)
    await turn(session, "He is reluctant to leave", w=None)  # typed
    await turn(session, "He is reluctant to stay", w=words(0.3))  # unclear
    await turn(session, "Bugün çok yorgunum", lang="tr", w=words(0.95))
    assert judge.calls == 0
    assert [u["valid"] for u in usage_events(ws)] == [False, False, False]
    assert all(u["points"] == 0 and u["reason"] for u in usage_events(ws))
    assert brain.unit_info("c:01")["points"] == 0


@pytest.mark.asyncio
async def test_a_single_word_goes_to_the_judge_so_a_one_word_imperative_can_score():
    judge = FakeJudge(usage.Judgement(False, "absent", (), "kelime"))
    session, ws, brain = make(judge)
    await turn(session, "Pizza", w=words(0.95))
    (u,) = usage_events(ws)
    assert (u["valid"], u["rule"], u["points"]) == (True, 4, 0) and judge.calls == 1

    session, ws, brain = make(FakeJudge(usage.Judgement(True, "correct", (usage.Word("stop", "A1"),), "iyi")))
    await turn(session, "Stop.", w=words(0.95))
    assert usage_events(ws)[0]["points"] == 3  # an imperative is a sentence; "stop" is a new A1 word


@pytest.mark.asyncio
async def test_speech_with_no_recognizer_confidence_earns_nothing():
    judge = FakeJudge(GOOD)
    session, ws, brain = make(judge)
    await turn(session, "He is reluctant to leave", w=[])  # spoken, but nothing was recognized with a confidence
    (u,) = usage_events(ws)
    assert u["valid"] is False and u["points"] == 0 and judge.calls == 0


@pytest.mark.asyncio
async def test_a_good_average_cannot_hide_garbage_words():
    judge = FakeJudge(GOOD)
    session, ws, brain = make(judge)
    mixed = [{"prob": 0.98}] * 5 + [{"prob": 0.2}] * 3  # mean 0.71, but 3 of 8 words were guesses
    await turn(session, "He is reluctant to leave now", w=mixed)
    assert usage_events(ws)[0]["valid"] is False and judge.calls == 0


@pytest.mark.asyncio
async def test_rejected_results_still_carry_the_unit_total_for_the_meter():
    session, ws, brain = make(FakeJudge(GOOD))
    await turn(session, "He is reluctant to leave", w=words(0.95))
    await turn(session, "typed hello there", w=None)
    typed = usage_events(ws)[1]
    assert typed["valid"] is False and typed["unit_points"] == 3 and typed["required"] == 30 and typed["spoken"] is False


@pytest.mark.asyncio
async def test_a_failing_judge_gives_no_points_and_does_not_break_the_session():
    session, ws, brain = make(FakeJudge(boom=True))
    await turn(session, "He is reluctant to leave", w=words(0.95))
    (u,) = usage_events(ws)
    assert u["valid"] is False and u["points"] == 0
    assert brain.unit_info("c:01")["points"] == 0


@pytest.mark.asyncio
async def test_a_session_without_a_topic_scores_nothing():
    session, ws, brain = make(FakeJudge(GOOD), topic=False)
    await turn(session, "He is reluctant to leave", w=words(0.95))
    assert usage_events(ws) == []
