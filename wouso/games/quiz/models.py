from random import shuffle
from datetime import datetime

from django.db import models

from wouso.core.user.models import Player
from wouso.core.game.models import Game
from wouso.core.qpool import register_category, get_questions_with_tag_and_category
from wouso.core.qpool.models import Question


class QuizException(Exception):
    pass


class Quiz(models.Model):
    CHOICES = {
        ('A', 'ACTIVE'),
        ('I', 'INACTIVE'),  # Active in future
        ('E', 'EXPIRED')
    }
    name = models.CharField(max_length=100)
    number_of_questions = models.IntegerField(default=5)
    time_limit = models.IntegerField(default=300)
    questions = models.ManyToManyField(Question)

    start = models.DateTimeField()
    end = models.DateTimeField()

    owner = models.ForeignKey(Game, null=True, blank=True)

    status = models.CharField(max_length=1, choices=CHOICES)

    def set_active(self):
        self.status = 'A'
        self.save()

    def set_inactive(self):
        self.status = 'I'
        self.save()

    def set_started(self):
        self.status = 'S'
        self.save()

    def set_played(self):
        self.status = 'P'
        self.save()

    def set_expired(self):
        self.status = 'E'
        self.save()

    def is_active(self):
        return self.status == 'A'

    def is_inactive(self):
        return self.status == 'I'

    def is_started(self):
        return self.status == 'S'

    def is_played(self):
        return self.status == 'P'

    def is_expired(self):
        return self.status == 'E'

    @property
    def elapsed(self):
        if self.end < datetime.now():
            return True
        return False
    #
    # @property
    # def is_active(self):
    #     now = datetime.now()
    #     if self.end < now:
    #         return False
    #     elif self.start > now:
    #         return False
    #     return True

    # @property
    # def active_quizzes(self):
    #     active_quizzes = [q for q in self.objects.all() if q.is_active()]
    #     return active_quizzes

    @classmethod
    def played_quizzes(self):
        played_quizzes = [q for q in self.objects.all() if q.time_for_user() == 0]
        return played_quizzes

    @classmethod
    def calculate_points(cls, responses):
        """ Response contains a dict with question id and checked answers ids.
        Example:
            {1 : [14,], ...}, - has answered answer with id 14 at the question with id 1
        """
        points = 0
        results = {}
        for r, v in responses.iteritems():
            checked, missed, wrong = 0, 0, 0
            q = Question.objects.get(id=r)
            correct_count = len([a for a in q.answers if a.correct])
            wrong_count = len([a for a in q.answers if not a.correct])
            for a in q.answers.all():
                if a.correct:
                    if a.id in v:
                        checked += 1
                    else:
                        missed += 1
                elif a.id in v:
                    wrong += 1
            if correct_count == 0:
                qpoints = 1 if (len(v) == 0) else 0
            elif wrong_count == 0:
                qpoints = 1 if (len(v) == q.answers.count()) else 0
            else:
                qpoints = checked - wrong
            qpoints = qpoints if qpoints > 0 else 0
            points += qpoints
            results[r] = (checked, correct_count)
        # return {'points': int(100.0 * points), 'results' : results}
        return {'points': points, 'results' : results}

    def add_player(self, player):
        """ Add player to the list of players which have played the quiz
        """
        # self.players.add(player)

    def set_start(self, user):
        """ Set quiz start time for user
        """
        user.start = datetime.now()
        user.quiz.set_started()
        user.save()

    def is_started_for_user(self, user):
        """ Check if user has already started quiz
        """
        if user.start is None:
            return False
        return True

    def time_for_user(self, user):
        """ Return seconds left for answering quiz
        """
        now = datetime.now()
        return self.time_limit - (now - user.start).seconds

    def reset(self, user):
        """ Reset quiz start time and ID of current started quiz
        """
        if user.start is not None:
            user.start = None
        if user.started_quiz_id != 0:
            user.started_quiz_id = 0
        user.save()


class QuizGame(Game):
    """ Each game must extend Game"""
    class Meta:
        proxy = True
    QPOOL_CATEGORY = 'quiz'

    def __init__(self, *args, **kwargs):
        self._meta.get_field('verbose_name').default = "Quiz"
        self._meta.get_field('short_name').default = ""
        self._meta.get_field('url').default = "quiz_index_view"
        super(QuizGame, self).__init__(*args, **kwargs)

register_category(QuizGame.QPOOL_CATEGORY, QuizGame)


class QuizUser(Player):
    """ Extension of the User object, customized for quiz """
    # quiz = models.ForeignKey(Quiz, null=True)

    # time when user started quiz
    start = models.DateTimeField(null=True, blank=True)
    # ID of current started quiz
    started_quiz_id = models.IntegerField(default=0)
    quizzes = models.ManyToManyField(Quiz, through='UserToQuiz')
    # score = models.IntegerField(default=0)
    # quizzes = models.ForeignKey(Quiz, null=True, blank=True)

    @property
    def active_quizzes(self):
        active_quizzes = [q for q in Quiz.objects.all() if q.is_active()]
        return active_quizzes


Player.register_extension('quiz', QuizUser)


class UserToQuiz(models.Model):
    CHOICES = {
        ('P', 'PLAYED'),
        ('R', 'RUNNING'),
        ('N', 'NOT STARTED')
    }
    user = models.ForeignKey(QuizUser)
    quiz = models.ForeignKey(Quiz)
    state = models.CharField(max_length=1, choices=CHOICES, default='N')
    score = models.IntegerField(default=-1)
