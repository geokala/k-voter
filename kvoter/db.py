from datetime import datetime
from sqlalchemy.orm.exc import NoResultFound
from kvoter.app import app
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.login import UserMixin
import hashlib
from random import choice
from string import ascii_letters, digits

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///kvoter.db"

db = SQLAlchemy(app)

roles_users = db.Table(
    'user_roles',
    db.Column('user_id', db.Integer(), db.ForeignKey('users.id')),
    db.Column('role_id', db.Integer(), db.ForeignKey('roles.id'))
)

conditions_election_rounds = db.Table(
    'conditions_election_rounds',
    db.Column('condition_id', db.Integer(), db.ForeignKey('conditions.id')),
    db.Column('election_round_id',
              db.Integer(),
              db.ForeignKey('election_rounds.id')),
)


class Candidate(db.Model):
    # TODO: This model could do with being improved... significantly
    __tablename__ = 'candidates'
    __tableargs__ = (
        db.UniqueConstraint('election_id', 'candidate'),
    )

    id = db.Column(db.Integer(), primary_key=True)
    user_id = db.Column(db.Integer(), db.ForeignKey('users.id'))
    election_id = db.Column(db.Integer(), db.ForeignKey('elections.id'))
    candidate = db.Column(db.String(255))

    def __init__(self, user_id, election_id, candidate):
        self.user_id = user_id
        self.election_id = election_id
        self.candidate = candidate

    @staticmethod
    def create(user_id, election_id, candidate=None):
        try:
            Candidate.query.filter(
                Candidate.user_id == user_id,
                Candidate.election_id == election_id,
                Candidate.candidate == candidate,
            ).one()
            return None
        except NoResultFound:
            candidate = Candidate(user_id, election_id, candidate)
            db.session.add(candidate)
            db.session.commit()
            return candidate


class Location(db.Model):
    __tablename__ = 'locations'

    id = db.Column(db.Integer(), primary_key=True)
    parent_location_id = db.Column(db.Integer(),
                                   db.ForeignKey('locations.id'))
    name = db.Column(db.String(255))

    def __init__(self, name, parent_location_id=None):
        self.name = name
        self.parent_location_id = parent_location_id

    @staticmethod
    def create(name, parent_location_id=None):
        try:
            Vote.query.filter(
                Location.name == name,
                Location.parent_location_id == parent_location_id,
            ).one()
        except NoResultFound:
            location = Location(name, parent_location_id)
            db.session.add(location)
            db.session.commit()
            return location


class Vote(db.Model):
    __tablename__ = 'votes'
    id = db.Column(db.Integer(), primary_key=True)
    voter_id = db.Column(db.Integer(), db.ForeignKey('voters.id'))
    candidate_id = db.Column(db.Integer(), db.ForeignKey('candidates.id'))

    def __init__(self, voter_id, candidate_id):
        self.voter_id = voter_id
        self.candidate_id = candidate_id

    @staticmethod
    def create(voter_id, election_id):
        try:
            results = Vote.query.filter(
                Vote.voter_id == voter_id,
                Vote.election_id == election_id,
            )
            # TODO: Check whether we've got too many votes from this voter
            # for the election they're voting for
            max_votes_for_election = 1
            if len(results) > max_votes_for_election:
                return None
        except NoResultFound:
            # No results means they can vote
            pass

        vote = Vote(voter_id, election_id)
        db.session.add(vote)
        db.session.commit()
        return vote


class Voter(db.Model):
    __tablename__ = 'voters'

    id = db.Column(db.Integer(), primary_key=True)
    user_id = db.Column(db.Integer(), db.ForeignKey('users.id'))
    election_id = db.Column(db.Integer(), db.ForeignKey('elections.id'))

    def __init__(self, user_id, election_id):
        self.user_id = user_id
        self.election_id = election_id

    @staticmethod
    def create(user_id, election_id):
        try:
            Voter.query.filter(
                Voter.user_id == user_id,
                Voter.election_id == election_id
            ).one()
            return None
        except NoResultFound:
            voter = Voter(user_id, election_id)
            db.session.add(voter)
            db.session.commit()
            return voter


class Condition(db.Model):
    __tablename__ = 'conditions'

    condition_types = db.Enum(
        'top n votes',
        'bottom n votes',
        'over n %',
        'below n %',
        'over n',
        'below n',
        name='condition_types',
    )

    id = db.Column(db.Integer(), primary_key=True)
    condition = db.Column(condition_types)
    threshold = db.Column(db.Integer())

    def __init__(self, condition, threshold):
        self.condition = condition
        self.threshold = threshold

    @staticmethod
    def create(condition, threshold):
        try:
            Condition.query.filter(
                Condition.condition == condition,
                Condition.threshold == threshold,
            ).one()
            return None
        except NoResultFound:
            condition = Condition(condition, threshold)
            db.session.add(condition)
            db.session.commit()
            return condition


class ElectionRound(db.Model):
    __tablename__ = 'election_rounds'

    id = db.Column(db.Integer(), primary_key=True)
    next_round_id = db.Column(db.Integer(),
                              db.ForeignKey('election_rounds.id'))
    # This is really a 'make it to the next round' condition unless there is
    # no next round.
    win_condition = db.Column(db.Integer(), db.ForeignKey('conditions.id'))
    description = db.Column(db.String(255))
    other_conditions = db.relationship(
        'Condition',
        secondary=conditions_election_rounds,
        backref=db.backref('election_rounds', lazy='dynamic'),
    )

    def __init__(self, win_condition, description, next_round_id=None):
        self.win_condition = win_condition
        self.next_round_id = next_round_id
        self.description = description

    @staticmethod
    def create(win_condition, description, next_round_id=None):
        try:
            # We could filter just by win condition and next round ID,
            # but it may make it harder to use if we force all elections
            # with the same rules to have the same name, especially if this
            # were to be used in locations with different languages
            ElectionRound.query.filter(
                ElectionRound.win_condition == win_condition,
                ElectionRound.description == description,
                ElectionRound.next_round_id == next_round_id,
            ).one()
            return None
        except NoResultFound:
            election_round = ElectionRound()
            db.session.add(election_round)
            db.session.commit()
            return election_round


class Election(db.Model):
    __tablename__ = "elections"

    id = db.Column(db.Integer(), primary_key=True)
    first_round = db.Column(db.Integer(), db.ForeignKey('election_rounds.id'))
    location = db.Column(db.Integer(), db.ForeignKey('locations.id'))
    potential_voters = db.Column(db.Integer())
    date_of_vote = db.Column(db.DateTime())

    def __init__(self, election_type, location, potential_voters,
                 date_of_vote):
        self.election_type = election_type
        self.location = location
        self.potential_voters = potential_voters
        self.date_of_vote = date_of_vote

    @staticmethod
    def create(election_type, location, potential_voters, date_of_vote):
        try:
            Election.query.filter(Election.election_type == election_type,
                                  Election.location == location).one()
            return None
        except NoResultFound:
            election = Election(election_type, location, potential_voters,
                                date_of_vote)
            db.session.add(election)
            db.session.commit()
            return election


class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))
    location = db.Column(db.Integer(), db.ForeignKey('locations.id'))

    def __init__(self, name, description="", location=None):
        self.name = name
        self.description = description
        self.location = location

    @staticmethod
    def get_or_create(name, description="", location=None):
        try:
            role = Role.query.filter(Role.name == name,
                                     Role.location == location).one()
            return role
        except NoResultFound:
            role = Role(name, description, location)
            db.session.add(role)
            db.session.commit()
            return role


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    email = db.Column(db.String(255), unique=True)
    _password = db.Column(db.String(255))
    active = db.Column(db.Boolean(), default=True)
    confirmed_at = db.Column(db.DateTime())
    created_on = db.Column(db.DateTime())
    confirmation_code = db.Column(db.String(255))
    roles = db.relationship('Role', secondary=roles_users,
                            backref=db.backref('users', lazy='dynamic'))

    def __init__(self, name, email, password, roles=("voter",)):
        self.name = name
        self.email = email
        self.password = password
        self.active = True
        self.confirmed_at = None
        self.created_on = datetime.now()
        self.confirmation_code = "".join(choice(ascii_letters + digits)
                                         for _ in range(32))
        for role in roles:
            role_obj = Role.get_or_create(role)
            self.roles.append(role_obj)

    @property
    def password(self):
        return self._password

    @property
    def salt(self):
        return hashlib.md5(bytes(self.name, 'utf8')).digest()

    def hash_password(self, password):
        return hashlib.pbkdf2_hmac(
            hash_name='sha256',
            password=bytes(password, 'utf8'),
            salt=self.salt,
            iterations=100000,
        )

    @password.setter
    def password(self, password):
        self._password = self.hash_password(password)

    def is_active(self):
        # TODO: Use self.confirmed_at <= datetime.now() again?
        return self.active

    def validate_password(self, password):
        return self.password == self.hash_password(password)

    @staticmethod
    def create(name, email, password):
        try:
            User.query.filter(User.name == name).one()
            return None
        except NoResultFound:
            user = User(name, email, password)
            db.session.add(user)
            db.session.commit()
            return user
