from sqlalchemy import Column, ForeignKey, Integer, String, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy import create_engine
from contextlib import contextmanager

Base = declarative_base()

roles_association = Table('roles_association', Base.metadata,
    Column('role', String, ForeignKey('roles.name')),
    Column('user', Integer, ForeignKey('users.id'))
)


class Bookmark(Base):
    __tablename__ = 'urls'
    id = Column(Integer, primary_key=True, unique=True)
    shortname = Column(String)
    url = Column(String)
    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship("User", uselist=False, back_populates='bookmarks')


class Watch(Base):
    __tablename__ = 'watch'
    id = Column(Integer, primary_key=True, unique=True)
    chat_id = Column(Integer)
    filter = Column(String)


class Role(Base):
    __tablename__ = 'roles'
    name = Column(String, primary_key=True, unique=True)


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, unique=True)
    name = Column(String)
    roles = relationship(Role, secondary=roles_association, backref='users')
    bookmarks = relationship(Bookmark, back_populates='user')


engine = create_engine('sqlite:///chats.db', connect_args={'check_same_thread': False})
Base.metadata.create_all(engine)
Base.metadata.bind = engine

Session = sessionmaker(bind=engine)


def drop_all():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

def drop(tables):
    for name in tables:
        Base.metadata.tables[name].drop()
        Base.metadata.tables[name].create()


@contextmanager
def make_session():
    session = Session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()


def with_session(func):
    def result(*args, **kwargs):
        with make_session() as session:
            return func(session, *args, **kwargs)
    return result
