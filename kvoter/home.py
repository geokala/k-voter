from flask import render_template, request
from kvoter import app
from kvoter.db import Election, Candidate, User
from wtforms import Form, IntegerField, validators


class VoteForm(Form):
    election_id = IntegerField(
        'Election ID',
        [
            validators.Required(),
        ],
    )


@app.route("/")
def home_view():
    form = VoteForm(request.form)

    candidates = Candidate.query.all()
    elections = Election.query.all()
    users = {
        user.id: user
        for user in User.query.all()
    }

    candidate_list = []
    for candidate in candidates:
        if candidate.candidate is None:
            candidate_list.append({
                'election_id': candidate.election_id,
                'candidate': users[candidate.user_id],
                'id': candidate.id,
            })
        else:
            candidate_list.append({
                'election_id': candidate.election_id,
                'candidate': candidate.candidate,
                'id': candidate.id,
            })

    elections = [
        {
            'type': election.name,
            'location': election.location,
            'candidates': [candidate['candidate']
                           for candidate in candidate_list
                           if candidate['election_id'] == election.id],
        }
        for election in elections
    ]

    if request.method == 'POST' and form.validate():
        pass

    return render_template("home.html", elections=elections)
