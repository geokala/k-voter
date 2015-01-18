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

location_admin_users = db.Table(
    'location_admin_users',
    db.Column('user_id', db.Integer(), db.ForeignKey('users.id')),
    db.Column('location_id', db.Integer(), db.ForeignKey('locations.id')),
)

election_admin_users = db.Table(
    'election_admin_users',
    db.Column('user_id', db.Integer(), db.ForeignKey('users.id')),
    db.Column('election_id', db.Integer(), db.ForeignKey('elections.id')),
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
            Location.query.filter(
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
        'Top n votes received',
        'Bottom n votes received',
        'More than n% of votes',
        'Less than n% of votes',
        'More than n votes',
        'Less than n votes',
        name='condition_types',
    )

    id = db.Column(db.Integer(), primary_key=True)
    condition = db.Column(condition_types)
    threshold = db.Column(db.Integer())

    def __init__(self, condition, threshold):
        self.condition = condition
        self.threshold = threshold

    @staticmethod
    def get_or_create(condition, threshold):
        try:
            condition = Condition.query.filter(
                Condition.condition == condition,
                Condition.threshold == threshold,
            ).one()
            return condition
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
    # TODO: This actually needs to map to a sub table with descriptions of
    # what meeting the condition(s) causes- e.g. 5% of votes: Deposit returned
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
    def get_or_create(win_condition, description, next_round_id=None):
        try:
            # We could filter just by win condition and next round ID,
            # but it may make it harder to use if we force all elections
            # with the same rules to have the same name, especially if this
            # were to be used in locations with different languages
            election_round = ElectionRound.query.filter(
                ElectionRound.win_condition == win_condition,
                ElectionRound.description == description,
                ElectionRound.next_round_id == next_round_id,
            ).one()
            return election_round
        except NoResultFound:
            election_round = ElectionRound(
                win_condition=win_condition,
                description=description,
                next_round_id=next_round_id,
            )
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
    name = db.Column(db.String(255))

    def __init__(self, name, location, potential_voters, date_of_vote,
                 first_round):
        self.name = name
        self.location = location
        self.potential_voters = potential_voters
        self.date_of_vote = date_of_vote
        self.first_round = first_round

    @staticmethod
    def create(name, location, potential_voters, date_of_vote,
               first_round=None):
        try:
            # Having an election with the same name, location, and date wuld
            # just be confusing.
            Election.query.filter(
                Election.name == name,
                Election.location == location,
                Election.date_of_vote == date_of_vote,
            ).one()
            return None
        except NoResultFound:
            election = Election(
                name=name,
                location=location,
                potential_voters=potential_voters,
                date_of_vote=date_of_vote,
                first_round=first_round,
            )
            db.session.add(election)
            db.session.commit()
            return election


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
    is_admin = db.Column(db.Boolean(), default=False)
    locations_admin = db.relationship(
        'Location',
        secondary=location_admin_users,
        backref=db.backref('locations', lazy='dynamic'),
    )
    elections_admin = db.relationship(
        'Election',
        secondary=election_admin_users,
        backref=db.backref('elections', lazy='dynamic'),
    )

    def __init__(self, name, email, password):
        self.name = name
        self.email = email
        self.password = password
        self.active = True
        self.confirmed_at = None
        self.created_on = datetime.now()
        self.confirmation_code = "".join(choice(ascii_letters + digits)
                                         for _ in range(32))

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
        # After we have a confirmation method.
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

    def promote_admin(self):
        if not self.is_admin:
            self.is_admin = True
            db.session.commit()
        return self

    def demote_admin(self):
        if self.is_admin:
            self.is_admin = False
            db.session.commit()
        return self

    def promote_location_admin(self, location):
        if location not in self.locations_admin:
            self.locations_admin.append(location)
            db.session.commit()
        return self

    def demote_location_admin(self, location):
        if location in self.locations_admin:
            self.locations_admin.remove(location)
            db.session.commit()
        return self

    def promote_election_admin(self, election):
        if election not in self.elections_admin:
            self.elections_admin.append(election)
            db.session.commit()
        return self

    def demote_election_admin(self, election):
        if election in self.elections_admin:
            self.elections_admin.remove(election)
            db.session.commit()
        return self
