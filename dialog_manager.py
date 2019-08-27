import random
import re
import tgalice
import yaml

from enum import Enum


class STATE(Enum):
    HELLO = 1
    ASK = 2
    RESULT = 3
    HELP = 4


def is_like_start(text):
    return bool(re.match('нач(ать|ни)( игру)?', tgalice.basic_nlu.fast_normalize(text)))


class QuizDialogManager(tgalice.dialog_manager.base.BaseDialogManager):
    class TEMPLATES:
        ARTIST_NAME = '{{artist_name}}'
        ARTIST_ID = '{{artist_id}}'

    def __init__(self, phrases, questions, artists, **kwargs):
        super(QuizDialogManager, self).__init__(**kwargs)
        self.phrases = phrases

        self._questions = {}
        for i, q in enumerate(questions):
            q['order'] = i
            matcher = tgalice.nlu.matchers.TextDistanceMatcher(
                metric='levenshtein', by_words=False, threshold=0.4
            )
            y = []
            x = []
            for a in q['answers']:
                y.append(a['value'])
                x.append(a['text'])
                for syn in a.get('synonyms', []):
                    y.append(a['value'])
                    x.append(syn)
            matcher.fit(x, y)
            q['matcher'] = matcher
            self._questions[q['key']] = q
        self._questions_order = {i: q['key'] for i, q in enumerate(questions)}

        self._artists = {a['artist_name']: a for a in artists}

    def respond(self, ctx: tgalice.dialog_manager.Context):
        message_text = ctx.message_text
        normalized_text = tgalice.basic_nlu.fast_normalize(message_text)
        response = tgalice.dialog_manager.Response(self.default_message, user_object=ctx.user_object)
        prev_state = ctx.user_object.get('state_name')
        prev_question = ctx.user_object.get('question')

        def set_state(state: STATE):
            response.updated_user_object['state_name'] = state.name

        def memorize(question_key, answer_key):
            if 'form' not in response.updated_user_object:
                response.updated_user_object['form'] = {}
            response.updated_user_object['form'][question_key] = answer_key

        def ask(question_key):
            q = self._questions[question_key]
            response.set_text(q['text'])
            response.suggests.extend([a['text'] for a in q['answers']])
            response.updated_user_object['question'] = question_key
            set_state(STATE.ASK)

        if message_text == '/start' or message_text == '' or message_text is None or ctx.metadata.get('new_session'):
            response.set_text(self.phrases['hello'])
            response.suggests = ['да', 'нет']
            set_state(STATE.HELLO)
        elif message_text == '/help' or tgalice.basic_nlu.like_help(normalized_text):
            response.set_text(self.phrases['help'])
        elif tgalice.nlu.basic_nlu.like_exit(normalized_text):
            response.set_text(self.phrases['exit'])
            response.commands.append(tgalice.dialog_manager.COMMANDS.EXIT)
        elif is_like_start(normalized_text):
            ask(self._questions_order[0])
        elif prev_state == STATE.HELLO.name or prev_state == STATE.HELP.name:
            if tgalice.basic_nlu.like_no(normalized_text):
                response.set_text(self.phrases['if_no'])
                response.commands.append(tgalice.dialog_manager.COMMANDS.EXIT)
                # todo: set some smart state
            elif tgalice.basic_nlu.like_yes(normalized_text):
                ask(self._questions_order[0])
            else:
                response.set_text(self.phrases['help'])
        elif prev_state == STATE.ASK.name:
            print('saving answer to {}'.format(prev_question))
            assert prev_question in self._questions  # todo: handle it

            q = self._questions[prev_question]
            choice, score = q['matcher'].match(normalized_text)
            if choice is None:
                choice = random.choice(q['answers'])['value']
                print('Answer selector had low score {} - chose the option "{}" randomly instead'.format(score, choice))
            memorize(prev_question, choice)
            next_q_index = q['order'] + 1
            if next_q_index not in self._questions_order:
                set_state(STATE.RESULT)
                form = response.updated_user_object['form']
                print(form)
                artist = self.match_artist(form)
                print(artist)
                artist_name = artist['artist_name']
                response.updated_user_object['best_artist'] = artist_name
                response.set_text(
                    self.phrases['finish'].replace(
                        self.TEMPLATES.ARTIST_NAME, artist_name
                    ).replace(
                        self.TEMPLATES.ARTIST_ID, str(artist['playlistnum'])
                    )
                )
                response.image_id = artist['photo']
            else:
                ask(self._questions_order[next_q_index])
        else:
            print('other reply')
            set_state(STATE.HELP)
            response.set_text(self.phrases['help'])
        return response

    def match_artist(self, form):
        best_artist = None
        best_score = -100500
        for artist_name, artist in self._artists.items():
            score = 0
            for key, value in form.items():
                if value == artist[key]:
                    score += 1
            if score >= best_score:
                best_score = score
                best_artist = artist
        assert best_artist is not None
        return best_artist

    @classmethod
    def from_yaml(cls, filename, **kwargs):
        with open(filename, 'r', encoding='utf8') as f:
            data = yaml.safe_load(f)
        return cls(**data, **kwargs)
