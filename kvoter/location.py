from flask.ext.login import login_required, current_user
from kvoter.db import Location, User
from flask import request, render_template, redirect, url_for, flash
from wtforms import Form, TextField, validators, SelectField
from kvoter.utils import user_not_authorised_to


def int_or_null(data):
    if data == 'None':
        return None
    else:
        print('not none')
        return int(data)


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
    locations_admin = User.query.filter(
        User.id == current_user.id,
    ).one().locations_admin
    if len(locations_admin) == 0 and not current_user.is_admin:
        # A standard user with no roles cannot be authorised to create any
        # locations
        return user_not_authorised_to('create locations')

    allowed_locations = [location.id for location in locations_admin]

    # Getting all locations means more memory usage but only one trip to the
    # DB. The alternative is multiple trips later, which is likely to cause
    # 'interesting' performance penalties with more than a few locations.
    # See location parent mapping for display_locations
    all_locations = {
        location.id: {
            'name': location.name,
            'parent': location.parent_location_id,
        }
        for location in Location.query.all()
    }

    can_create_top_level = False
    if current_user.is_admin:
        allowed_locations = all_locations
        can_create_top_level = True
    elif len(allowed_locations) > 0:
        allowed_locations = {location: details
                             for location, details in all_locations.items()
                             if location in allowed_locations}
    else:
        # With no location_admin or admin privs, the user cannot create
        # locations
        return user_not_authorised_to('create locations')

    # Format the allowed locations in a useful manner
    allowed_locations = [(location, details['name'])
                         for location, details in allowed_locations.items()]

    if can_create_top_level:
        allowed_locations.append((None, '-'))

    form = LocationForm(request.form)
    # Make the locations easier to read
    display_locations = []
    for location in allowed_locations:
        location_id = location[0]
        location_name = []
        next_id = location_id
        while next_id is not None:
            location_name.append(all_locations[next_id]['name'])
            next_id = all_locations[next_id]['parent']
        location_name = '/'.join(location_name)
        if location_name == '':
            location_name = '-'
        display_locations.append((location_id, location_name))

    form.parent_location.choices = display_locations
    if request.method == 'POST' and form.validate():
        parent_location_name = None
        for location in allowed_locations:
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
            return redirect(url_for('home'))
    else:
        return render_template("location.html", form=form)
