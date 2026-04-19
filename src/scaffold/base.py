from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

from scaffold.db.conventions import NAMING_CONVENTION


class CoreBase(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
