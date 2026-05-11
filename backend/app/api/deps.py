import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import ACCESS_TOKEN_TYPE, decode_token
from app.models.user import User, UserRole
from app.services.user import get_user_by_id

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token, expected_type=ACCESS_TOKEN_TYPE)
        subject = payload.get("sub")
        if not subject:
            raise credentials_exc
        user_id = uuid.UUID(subject)
    except (JWTError, ValueError) as exc:
        raise credentials_exc from exc

    user = get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise credentials_exc
    return user


def require_roles(*allowed: UserRole) -> Callable[[User], User]:
    def _checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to perform this action",
            )
        return current_user

    return _checker


require_teacher = require_roles(UserRole.TEACHER, UserRole.ADMIN)
require_student = require_roles(UserRole.STUDENT)
