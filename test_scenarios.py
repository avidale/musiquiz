import pytest
import tgalice

from dialog_manager import QuizDialogManager


@pytest.fixture
def default_dialog_manager():
    return QuizDialogManager.from_yaml('texts/quiz.yaml')


def make_context(text='', prev_response=None, new_session=False):
    if prev_response is not None:
        user_object = prev_response.updated_user_object
    else:
        user_object = {}
    if new_session:
        metadata = {'new_session': True}
    else:
        metadata = {}
    return tgalice.dialog_manager.Context(user_object=user_object, metadata=metadata, message_text=text)


def test_start(default_dialog_manager):
    r0 = default_dialog_manager.respond(make_context(new_session=True))
    assert 'Йоу!' in r0.text  # substring in string
    assert 'да' in r0.suggests  # string in list of strings
    assert 'нет' in r0.suggests  # string in list of strings


def test_randomization(default_dialog_manager):
    r0 = default_dialog_manager.respond(make_context(new_session=True))
    r1 = default_dialog_manager.respond(make_context(text='да', prev_response=r0))
    chosen_options = set()
    for i in range(100):
        r2 = default_dialog_manager.respond(
            make_context(text='какая-то безумная хрень которая точно не матчится', prev_response=r1)
        )
        chosen_options.add(r2.updated_user_object['form']['sex'])
    assert chosen_options == {'м', 'ж'}
