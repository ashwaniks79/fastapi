from app.odoo_client import get_odoo_connection
import logging



logger = logging.getLogger(__name__)

def _find_group_id(odoo, xml_id=None, name=None):
    """Fetch the Group ID safely; if xml_id fails, then search by name."""
    gid = None
    if xml_id:
        try:
            gid = odoo.env.ref(xml_id).id
        except Exception:
            gid = None
    if not gid and name:
        recs = odoo.env['res.groups'].search([('name', '=', name)], limit=1)
        gid = recs[0] if recs else None
    return gid

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
    # try:
    #     odoo = get_odoo_connection()
    #     user_model = odoo.env['res.users']

    #     existing_users = user_model.search([('login', '=', user["email"])])
    #     if existing_users:
    #         logger.info(f"[Odoo Sync] User already exists in Odoo: {user['email']}")
    #         return existing_users[0]

    #     #  Ensure full name
    #     full_name = f"{user.get('first_name', '').strip()} {user.get('last_name', '').strip()}".strip()
    #     if not full_name:
    #         raise ValueError("User must have a non-empty full name for Odoo")

    #     #  Get Portal group ID from Odoo
    #     group_portal = odoo.env.ref('base.group_portal').id

    #     #  Create user in Odoo with Portal group
    #     user_id = user_model.create({
    #         'name': full_name,
    #         'login': user['email'],
    #         'email': user['email'],
    #         'password': user['plain_password'],  # 👈 plain password (not hashed)
    #         'groups_id': [(6, 0, [group_portal])],
    #     })

    #     logger.info(f"[Odoo Sync] User created in Odoo with ID: {user_id}")
    #     return user_id

    # except Exception as e:
    #     logger.error(f"[Odoo Sync] Failed to sync user to Odoo: {e}")
    #     raise
    try:
        odoo = get_odoo_connection()
        U = odoo.env['res.users']

        existing = U.search([('login', '=', user["email"])])
        if existing:
            logger.info(f"[Odoo Sync] User already exists in Odoo: {user['email']}")
            return existing[0]

        full_name = f"{user.get('first_name','').strip()} {user.get('last_name','').strip()}".strip()
        if not full_name:
            raise ValueError("User must have a non-empty full name for Odoo")

        # ---- groups we need ----
        g_employee = _find_group_id(odoo, xml_id='base.group_user')  # Internal Users
        # plan groups by name (change names if yours differ)
        g_free   = _find_group_id(odoo, name='Plan: Free')
        g_silver = _find_group_id(odoo, name='Plan: Silver')
        g_gold   = _find_group_id(odoo, name='Plan: Gold')

        plan = (user.get("plan_type") or "free").lower()
        plan_group = {"free": g_free, "silver": g_silver, "gold": g_gold}.get(plan, g_free)

        group_ids = [gid for gid in (g_employee, plan_group) if gid]
        if not group_ids:
            raise RuntimeError("No valid groups found (base.group_user or plan groups missing).")

        user_id = U.create({
            'name': full_name,
            'login': user['email'],
            'email': user['email'],
            'password': user['plain_password'],
            # IMPORTANT: portal group mat do; internal + plan hi dena hai
            'groups_id': [(6, 0, group_ids)],
        })

        logger.info(f"[Odoo Sync] User created in Odoo id={user_id} with plan={plan}")
        return user_id

    except Exception as e:
        logger.error(f"[Odoo Sync] Failed to sync user to Odoo: {e}")
        raise

def update_odoo_user_plan(email: str, plan_type: str) -> bool:
    """
    plan_type: 'free' | 'silver' | 'gold'
    """
    try:
        odoo = get_odoo_connection()
        U = odoo.env['res.users']

        uid = U.search([('login', '=', email)], limit=1)
        if not uid:
            logger.warning(f"[Odoo Sync] No Odoo user found for {email}")
            return False

        g_employee = _find_group_id(odoo, xml_id='base.group_user')
        g_free   = _find_group_id(odoo, name='Plan: Free')
        g_silver = _find_group_id(odoo, name='Plan: Silver')
        g_gold   = _find_group_id(odoo, name='Plan: Gold')

        plan = (plan_type or 'free').lower()
        plan_group = {'free': g_free, 'silver': g_silver, 'gold': g_gold}.get(plan, g_free)

        group_ids = [gid for gid in (g_employee, plan_group) if gid]
        odoo.env['res.users'].browse(uid[0]).write({'groups_id': [(6, 0, group_ids)]})

        logger.info(f"[Odoo Sync] Updated plan for {email} -> {plan}")
        return True

    except Exception as e:
        logger.error(f"[Odoo Sync] Failed to update plan for {email}: {e}")
        return False
