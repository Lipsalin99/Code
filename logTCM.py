import jwt
from fastapi.security import OAuth2PasswordBearer
 
SECRET_KEY = os.environ['SECRET_KEY']
ALGORITHM = os.environ['ALGORITHM']
 
def create_access_token(*, data: dict, expires_delta: timedelta = None):
   to_encode = data.copy()
   if expires_delta:
   	expire = datetime.utcnow() + expires_delta
   else:
   	expire = datetime.utcnow() + timedelta(minutes=15)
   to_encode.update({"exp": expire})
   encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
   return encoded_jwt
def decode_access_token(db, token):
   credentials_exception = HTTPException(
   	status_code=HTTP_401_UNAUTHORIZED,
   	detail="Could not validate credentials",
   	headers={"WWW-Authenticate": "Bearer"},
   )
   try:
   	payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
   	email: str = payload.get("sub")
   	if email is None:
       	raise credentials_exception
   	token_data = schemas.TokenData(email=email)
   except PyJWTError:
   	raise credentials_exception
   user = crud.get_user_by_email(db, email=token_data.email)
   if user is None:
   	raise credentials_exception
   return user
