from flask import redirect, url_for, flash


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
