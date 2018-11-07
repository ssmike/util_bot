from tgutil import updater, broadcast_chats, TgHandler, command, guard, retry, replyerrors, check_role, owner
from base import Role, User, with_session


def parse_role_users(text):
    names, role_names = [], []
    for token in text.split(' ')[1:]:
        if token.startswith('@'):
            names.append(token[1:])
        else:
            role_names.append(token)
    return names, role_names


@command('new_role')
@check_role('admin')
@with_session
def add_role(session, bot, update):
    role = update.message.text.split(' ', 1)[1]
    session.add(Role(name=role))


@command('acl_init')
@owner('ssmike')
@replyerrors
@with_session
def clr_acl(session, bot, update):
    watch_role = Role(name='watcher')
    admin_role = Role(name='admin')
    user_role = Role(name='user')
    user = User(name='ssmike', id=update.message.from_user.id, roles=[admin_role, watch_role, user_role])
    session.add_all([user_role, admin_role, watch_role, user])


@command('acl_add')
@check_role('admin')
@replyerrors
@with_session
def add_roles(session, bot, update):
    text = update.message.text
    names, role_names = parse_role_users(text)
    for user, role in session.query(User, Role) \
                             .filter(Role.name.in_(role_names)) \
                             .filter(User.name.in_(names)).all():
        user.roles.append(role)


@command('acl_rm')
@check_role('admin')
@replyerrors
@with_session
def del_roles(session, bot, update):
    text = update.message.text
    names, role_names = parse_role_users(text)
    for user, role in session.query(User, Role) \
                             .filter(Role.name.in_(role_names)) \
                             .filter(User.name.in_(names)).all():
        user.roles.remove(role)


@command('acl_list')
@check_role('admin')
@with_session
def list_users(session, bot, update):
    name = update.message.text.split(' ')[1]
    role = session.query(Role).filter(Role.name == name).one()
    result = []
    for user in role.users:
        result.append(user.name)
    if len(result) != 0:
        update.message.reply_text("\n".join(result), quote=True)
