from flask.ext.login import login_required
from kvoter.db import Election
from flask import request, render_template, redirect, url_for, flash
from wtforms import (Form, TextField, IntegerField, DateField, validators,
                     SelectField)
from kvoter.utils import int_or_null, get_authorised_locations


class ElectionForm(Form):
    election_type = TextField(
        'Election type',
        [
            validators.Length(max=80),
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
    allowed_locations = get_authorised_locations()
    if 'error' in allowed_locations.keys():
        return allowed_locations['error']

    form = ElectionForm(request.form)
    form.location.choices = allowed_locations['display']
    if request.method == 'POST' and form.validate():
        new_election = Election.create(
            election_type=form.election_type.data,
            location=form.location.data,
            potential_voters=form.potential_voters.data,
            date_of_vote=form.date_of_vote.data,
        )

        if new_election is None:
            flash(
                '%s election in %s already created!' % (
                    form.election_type.data,
                    form.location.data,
                ),
                'danger',
            )
            return redirect(url_for('create_election'))
        else:
            flash(
                '%s election in %s created!' % (
                    form.election_type.data,
                    form.location.data,
                ),
                'success',
            )
            return redirect(url_for('home'))
    else:
        return render_template("election.html", form=form)
