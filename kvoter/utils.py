from flask import redirect, url_for, flash
from flask.ext.login import current_user
from kvoter.db import User, Location


def int_or_null(data):
    if data == 'None':
        return None
    else:
        return int(data)


def user_not_authorised_to(action):
    """
        This will flash a warning for the user that they're not allowed to
        perform the action they just tried to perform.
        It will then return a redirect to the home page.

        Keyword arguments:
        action -- The action the user is not allowed to perform.
    """
    flash(
        'You are not authorised to create locations!',
        'danger',
    )
    return redirect(url_for('home'))


def get_authorised_locations(include_top_level=True):
    locations_admin = User.query.filter(
        User.id == current_user.id,
    ).one().locations_admin

    # Abort quickly if we can
    if len(locations_admin) and not current_user.is_admin:
        return {
            'error': user_not_authorised_to('create locations'),
        }

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
        return {
            'error': user_not_authorised_to('create locations'),
        }

    # Format the allowed locations in a useful manner
    allowed_locations = [(location, details['name'])
                         for location, details in allowed_locations.items()]

    if can_create_top_level and include_top_level:
        allowed_locations.append((None, '-'))

    # Make the locations easier to read
    display_locations = []
    for location in allowed_locations:
        location_id = location[0]
        location_name = []
        next_id = location_id
        while next_id is not None:
            location_name.append(all_locations[next_id]['name'])
            next_id = all_locations[next_id]['parent']
        location_name.reverse()
        location_name = '/'.join(location_name)
        if location_name == '':
            location_name = '-'
        display_locations.append((location_id, location_name))

    return {
        'basic': allowed_locations,
        'display': display_locations,
    }
