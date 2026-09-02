from sqlalchemy.orm import declarative_base

Base = declarative_base()

# import models so Alembic can find them via metadata
from . import audit_log  # noqa: F401
from . import business  # noqa: F401
from . import category  # noqa: F401
from . import media  # noqa: F401
from . import referral  # noqa: F401
from . import receipt  # noqa: F401
from . import reward  # noqa: F401
from . import user_profile  # noqa: F401
from . import subscriber  # noqa: F401
from . import beneficiary  # noqa: F401
