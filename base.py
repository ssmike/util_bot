from sqlalchemy import Column, ForeignKey, Integer, String, Boolean, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy import create_engine

Base = declarative_base()

roles_association = Table('roles_association', Base.metadata,
    Column('left_id', String, ForeignKey('roles.name')),
    Column('right_id', Integer, ForeignKey('users.id'))
)


class Bookmark(Base):
    __tablename__ = 'urls'
    id = Column(Integer, primary_key=True, unique=True)
    shortname = Column(String)
    url = Column(String)
    user_id = Column(Integer, ForeignKey('users.id'))


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


User.roles = relationship(Role, secondary=roles_association)
Role.users = relationship(User, secondary=roles_association)
Bookmark.user = relationship(User, uselist=False)
User.bookmarks = relationship(Bookmark)

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
