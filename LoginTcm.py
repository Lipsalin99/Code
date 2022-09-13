def login_for_access_token(db: Session = Depends(get_db),
                      	form_data: OAuth2PasswordRequestForm = Depends()):
   """generate access token for valid credentials"""
   user = authenticate_user(db, form_data.username, form_data.password)
   if not user:
   	raise HTTPException(
       	status_code=HTTP_401_UNAUTHORIZED,
       	detail="Incorrect email or password",
       	headers={"WWW-Authenticate": "Bearer"},
   	)
   access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
   access_token = create_access_token(data={"sub": user.email},
                                  	expires_delta=access_token_expires)
   return {"access_token": access_token, "token_type": "bearer"}

   def get_db():
   """provide db session to path operation functions"""
   try:
   	db = SessionLocal()
   	yield db
   finally:
   	db.close()
def get_current_user(db: Session = Depends(get_db),
                	token: str = Depends(oauth2_scheme)):
   return decode_access_token(db, token)
@app.get("/api/me", response_model=schemas.User)
def read_logged_in_user(current_user: models.User = Depends(get_current_user)):
   """return user settings for current user"""
   return current_user
Logged-in Users Can CRUD TODOs
Before we write the path operation functions for TODO Create, Read, Update, Delete (CRUD), we define the following helper functions to perform actual CRUD on the db.

def create_todo(db: Session, current_user: models.User, todo_data: schemas.TODOCreate):
   todo = models.TODO(text=todo_data.text,
                   	completed=todo_data.completed)
   todo.owner = current_user
   db.add(todo)
   db.commit()
   db.refresh(todo)
   return todo
def update_todo(db: Session, todo_data: schemas.TODOUpdate):
   todo = db.query(models.TODO).filter(models.TODO.id == id).first()
   todo.text = todo_data.text
   todo.completed = todo.completed
   db.commit()
   db.refresh(todo)
   return todo
def delete_todo(db: Session, id: int):
   todo = db.query(models.TODO).filter(models.TODO.id == id).first()
   db.delete(todo)
   db.commit()
 
def get_user_todos(db: Session, userid: int):
   return db.query(models.TODO).filter(models.TODO.owner_id == userid).all()

def get_db():
   """provide db session to path operation functions"""
   try:
   	db = SessionLocal()
   	yield db
   finally:
   	db.close()
def get_current_user(db: Session = Depends(get_db),
                	token: str = Depends(oauth2_scheme)):
   return decode_access_token(db, token)
@app.get("/api/me", response_model=schemas.User)
def read_logged_in_user(current_user: models.User = Depends(get_current_user)):
   """return user settings for current user"""
   return current_user

def create_todo(db: Session, current_user: models.User, todo_data: schemas.TODOCreate):
   todo = models.TODO(text=todo_data.text,
                   	completed=todo_data.completed)
   todo.owner = current_user
   db.add(todo)
   db.commit()
   db.refresh(todo)
   return todo
def update_todo(db: Session, todo_data: schemas.TODOUpdate):
   todo = db.query(models.TODO).filter(models.TODO.id == id).first()
   todo.text = todo_data.text
   todo.completed = todo.completed
   db.commit()
   db.refresh(todo)
   return todo
def delete_todo(db: Session, id: int):
   todo = db.query(models.TODO).filter(models.TODO.id == id).first()
   db.delete(todo)
   db.commit()
 
def get_user_todos(db: Session, userid: int):
   return db.query(models.TODO).filter(models.TODO.owner_id == userid).all()

def get_own_todos(current_user: models.User = Depends(get_current_user),
             	db: Session = Depends(get_db)):
   """return a list of TODOs owned by current user"""
   todos = crud.get_user_todos(db, current_user.id)
   return todos
@app.post("/api/todos", response_model=schemas.TODO)
def add_a_todo(todo_data: schemas.TODOCreate,
          	current_user: models.User = Depends(get_current_user),
          	db: Session = Depends(get_db)):
   """add a TODO"""
   todo = crud.create_meal(db, current_user, meal_data)
   return todo
@app.put("/api/todos/{todo_id}", response_model=schemas.TODO)
def update_a_todo(todo_id: int,
             	todo_data: schemas.TODOUpdate,
             	current_user: models.User = Depends(get_current_user),
             	db: Session = Depends(get_db)):
   """update and return TODO for given id"""
   todo = crud.get_todo(db, todo_id)
   updated_todo = crud.update_todo(db, todo_id, todo_data)
   return updated_todo
@app.delete("/api/todos/{todo_id}")
def delete_a_meal(todo_id: int,
             	current_user: models.User = Depends(get_current_user),
             	db: Session = Depends(get_db)):
   """delete TODO of given id"""
   crud.delete_meal(db, todo_id)
   return {"detail": "TODO Deleted"}


