from tgutil import command, replyerrors, check_role, owner
from base import Role, User, with_session, make_session
import logging

_log = logging.getLogger(__name__)


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
def add_role(session, update, context):
    role = update.message.text.split(' ', 1)[1]
    session.add(Role(name=role))


@command('acl_init')
@owner('ssmike')
@replyerrors
def fix_acl(update, context):
    try:
        with make_session() as session:
            session.add(User(name='ssmike', id=update.message.from_user.id))
    except Exception as e:
        _log.exception(e)

    roles = ('watcher', 'admin', 'user', 'fetcher')
    for role in roles:
        try:
            with make_session() as session:
                session.add(Role(name=role))
        except Exception as e:
            _log.exception(e)

        try:
            with make_session() as session:
                user = session.query(User).filter(User.name == 'ssmike').one()
                role = session.query(Role).filter(Role.name == role).one()
                user.roles.append(role)
        except Exception as e:
            _log.exception(e)


@command('acl_add')
@check_role('admin')
@replyerrors
@with_session
def add_roles(session, update, context):
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
def del_roles(session, update, context):
    text = update.message.text
    names, role_names = parse_role_users(text)
    for user, role in session.query(User, Role) \
                             .filter(Role.name.in_(role_names)) \
                             .filter(User.name.in_(names)).all():
        user.roles.remove(role)


@command('acl_list')
@check_role('admin')
@with_session
def list_users(session, update, context):
    name = update.message.text.split(' ')[1]
    role = session.query(Role).filter(Role.name == name).one()
    result = []
    for user in role.users:
        result.append(user.name)
    if len(result) != 0:
        update.message.reply_text("\n".join(result), quote=True)
