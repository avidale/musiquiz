import pandas as pd
import random
import tgalice

from enum import Enum


class STATE(Enum):
    HELLO = 1
    ASK = 2
    RESULT = 3
    HELP = 4


def make_unique(seq):
    seen = set()
    seen_add = seen.add
    return [x for x in seq if not (x in seen or seen_add(x))]


def sample_at_most(seq, n=1):
    seq = list(set(seq))
    random.shuffle(seq)
    return seq[:n]


class QuizDialogManager(tgalice.dialog_manager.base.BaseDialogManager):
    class TEMPLATES:
        ARTIST_NAME = '{{artist_name}}'
        ARTIST_ID = '{{artist_id}}'

    def __init__(self, filename, **kwargs):
        super(QuizDialogManager, self).__init__(**kwargs)
        self._data = pd.read_excel(filename, sheet_name=None)

        # parse meta
        meta = self._data['META']
        meta.set_index(meta.columns[0], inplace=True)

        self._TEXT_HELLO = meta.loc['Приветственная фраза', 'Text']
        self._TEXT_NO = meta.loc['Приветствие нет', 'Text']
        self._TEXT_HELP = meta.loc['Справка', 'Text']
        self._TEXT_FINISH = meta.loc['Окончание', 'Text']

        # parse questions
        qdata = self._data['Q&A']

        q_order = {}
        for k in qdata['key']:
            if k not in q_order:
                q_order[k] = len(q_order)

        self._questions = {}
        self._questions_order = {o: k for k, o in q_order.items()}

        for key, df in qdata.groupby('key'):
            q = {
                'key': key,
                'order': q_order[key],
                'text': df['q_custom'].iloc[0],
                'answers': []
            }
            for j, row in df.iterrows():
                q['answers'].append({
                    'text': row['text_custom'],
                    'value': row['a']
                })
            matcher = tgalice.nlu.matchers.TextDistanceMatcher(
                metric='levenshtein', by_words=False, threshold=0.5
            )
            matcher.fit([a['text'] for a in q['answers']], [a['value'] for a in q['answers']])
            q['matcher'] = matcher
            self._questions[key] = q

        # parse artists
        self._artists = {
            row['artist_name']: row.to_dict()
            for i, row in self._data['artists'].iterrows()
        }

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
            response.set_text(self._TEXT_HELLO)
            response.suggests = ['да', 'нет']
            set_state(STATE.HELLO)
        elif prev_state == STATE.HELLO.name or prev_state == STATE.HELP.name:
            if tgalice.basic_nlu.like_no(normalized_text):
                response.set_text(self._TEXT_NO)
                # todo: set some smart state
            elif tgalice.basic_nlu.like_yes(normalized_text):
                ask(self._questions_order[0])
            else:
                response.set_text(self._TEXT_HELP)
        elif prev_state == STATE.ASK.name:
            print('saving answer to {}'.format(prev_question))
            assert prev_question in self._questions  # todo: handle it

            q = self._questions[prev_question]
            choice, score = q['matcher'].match(normalized_text)
            if choice is None:
                # todo: reask smarter
                ask(prev_question)
            else:
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
                        self._TEXT_FINISH.replace(
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
            response.set_text(self._TEXT_HELP)
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
