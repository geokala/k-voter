from flask.ext.login import login_required, current_user
from kvoter.db import Election, Condition, ElectionRound
from flask import request, render_template, redirect, url_for, flash
from wtforms import (Form, TextField, IntegerField, DateField, validators,
                     SelectField)
from kvoter.utils import int_or_null, get_authorised_locations


class ElectionForm(Form):
    election_title = TextField(
        'Election title',
        [
            validators.Length(max=100),
            validators.Required(),
        ],
    )
    win_condition_type = SelectField(
        'Win type',
    )
    win_condition_threshold = IntegerField(
        'Win threshold',
        [
            validators.Required(),
        ],
    )
    location = SelectField(
        'Election location',
        coerce=int_or_null,
    )
    potential_voters = IntegerField(
        'Potential voters',
        [
            validators.Required(),
        ],
    )
    date_of_vote = DateField(
        'Date of vote',
        [
            validators.Required(),
        ],
    )


@login_required
def create_election_view():
    win_condition_types = (
        (condition, condition)
        for condition in Condition.condition_types.enums
    )
    allowed_locations = get_authorised_locations(
       include_top_level=False,
       unauth_message='create elections in any existing locations',
    )
    if 'error' in allowed_locations.keys():
        return allowed_locations['error']

    if len(allowed_locations['basic']) == 0:
        flash('There are no locations in which you can create an election.',
              'danger')
        return redirect(url_for('home'))

    form = ElectionForm(request.form)
    form.location.choices = allowed_locations['display']
    form.win_condition_type.choices = win_condition_types
    if request.method == 'POST' and form.validate():
        location_name = None
        for location in allowed_locations['basic']:
            if form.location.data == location[0]:
                location_name = location[1]
                break

        if location_name is None:
            flash(
                'Parent location not found, cannot create location.',
                'danger',
            )
            return redirect(url_for('create_election'))

        win_condition = Condition.get_or_create(
            condition=form.win_condition_type.data,
            threshold=form.win_condition_threshold.data,
        )
        election_round = ElectionRound.get_or_create(
            win_condition=win_condition.id,
            description=form.election_title.data,
        )
        new_election = Election.create(
            name=form.election_title.data,
            location=form.location.data,
            potential_voters=form.potential_voters.data,
            date_of_vote=form.date_of_vote.data,
            # TODO: Support more than one round
            first_round=None,
        )
        if new_election is None:
            flash(
                '%s election in %s already created!' % (
                    form.election_title.data,
                    location_name,
                ),
                'danger',
            )
            return redirect(url_for('create_election'))
        else:
            flash(
                '%s election in %s created!' % (
                    form.election_title.data,
                    location_name,
                ),
                'success',
            )
            current_user.promote_election_admin(new_election)
            return redirect(url_for('home'))
    else:
        return render_template("election.html", form=form)
