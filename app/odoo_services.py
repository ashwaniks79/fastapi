from app.odoo_client import get_odoo_connection
import logging

logger = logging.getLogger(__name__)

def create_odoo_user(user: dict) -> int:
    """
    Sync a user to Odoo. Creates the user in Odoo if not exists.

    Args:
        user (dict): must include:
            - first_name
            - last_name
            - email
            - plain_password ( unhashed password only for Odoo)

    Returns:
        int: Odoo user ID
    """
    try:
        odoo = get_odoo_connection()
        user_model = odoo.env['res.users']

        existing_users = user_model.search([('login', '=', user["email"])])
        if existing_users:
            logger.info(f"[Odoo Sync] User already exists in Odoo: {user['email']}")
            return existing_users[0]

        #  Ensure full name
        full_name = f"{user.get('first_name', '').strip()} {user.get('last_name', '').strip()}".strip()
        if not full_name:
            raise ValueError("User must have a non-empty full name for Odoo")

        #  Get Portal group ID from Odoo
        group_portal = odoo.env.ref('base.group_portal').id

        #  Create user in Odoo with Portal group
        user_id = user_model.create({
            'name': full_name,
            'login': user['email'],
            'email': user['email'],
            'password': user['plain_password'],  # 👈 plain password (not hashed)
            'groups_id': [(6, 0, [group_portal])],
        })

        logger.info(f"[Odoo Sync] User created in Odoo with ID: {user_id}")
        return user_id

    except Exception as e:
        logger.error(f"[Odoo Sync] Failed to sync user to Odoo: {e}")
        raise

