from flask.ext.login import login_required, current_user
from kvoter.db import Location, User
from flask import request, render_template, redirect, url_for, flash
from wtforms import Form, TextField, validators, SelectField
from kvoter.utils import (user_not_authorised_to,
                          int_or_null,
                          get_authorised_locations)


class LocationForm(Form):
    location_name = TextField(
        'Location name',
        [
            validators.Length(max=255),
            validators.Required(),
        ],
    )
    parent_location = SelectField(
        'Parent location',
        coerce=int_or_null,
    )


@login_required
def create_location_view():
    allowed_locations = get_authorised_locations()
    if 'error' in allowed_locations.keys():
        return allowed_locations['error']

    form = LocationForm(request.form)
    form.parent_location.choices = allowed_locations['display']
    if request.method == 'POST' and form.validate():
        parent_location_name = None
        for location in allowed_locations['basic']:
            if form.parent_location.data == location[0]:
                parent_location_name = location[1]
                break

        if parent_location_name is None:
            # Give the same message if a non-admin user tries to create a top
            # level location or anyone tries to parent onto a location that is
            # not allowed or does not exist. Makes fishing harder.
            flash(
                'Parent location not found, cannot create location.',
                'danger',
            )
            return redirect(url_for('create_location'))

        new_location = Location.create(
            name=form.location_name.data,
            parent_location_id=form.parent_location.data,
        )

        if new_location is None:
            flash(
                'Location %s already exists under %s!' % (
                    form.location_name.data,
                    parent_location_name,
                ),
                'danger',
            )
            return redirect(url_for('create_location'))
        else:
            flash(
                'Location %s created under %s!' % (
                    form.location_name.data,
                    parent_location_name,
                ),
                'success',
            )
            current_user.promote_location_admin(new_location)
            return redirect(url_for('home'))
    else:
        return render_template("location.html", form=form)
