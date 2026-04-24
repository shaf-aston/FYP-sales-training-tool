from core.analysis import analyse_state, detect_ack_context


def test_terse_follow_up_after_validation_skips_repeat_ack():
    history = [
        {"role": "user", "content": "full time coz i get sad in my current job and need transition"},
        {
            "role": "assistant",
            "content": "Transitioning to a new career can be challenging. What aspects of your current job make you feel sad?",
        },
    ]

    user_message = "nothing really"
    state = analyse_state(history, user_message)

    assert detect_ack_context(user_message, history, state) == "none"


def test_short_agreement_after_emotional_context_skips_ack():
    history = [
        {"role": "user", "content": "i've been burnt out and need a change"},
        {"role": "assistant", "content": "That sounds exhausting. What feels most off right now?"},
        {"role": "user", "content": "nothing really"},
        {"role": "assistant", "content": "What would you want your next chapter to give you?"},
    ]

    user_message = "ok"
    state = analyse_state(history, user_message)

    assert detect_ack_context(user_message, history, state) == "none"


def test_literal_question_after_emotional_context_can_use_light_ack():
    history = [
        {"role": "user", "content": "i'm stressed and burnt out"},
        {"role": "assistant", "content": "That sounds draining. What part is weighing on you most?"},
    ]

    user_message = "how do i change that?"
    state = analyse_state(history, user_message)

    assert detect_ack_context(user_message, history, state) == "light"
